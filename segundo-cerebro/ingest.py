#!/usr/bin/env python3
"""Adiciona um vídeo ao segundo cérebro: áudio -> transcrição -> nota no Obsidian.

Uso:
    python ingest.py video.mp4
    python ingest.py "https://www.youtube.com/watch?v=..." --titulo "Aula 1"
    python ingest.py video.mp4 --modelo large-v3 --device cuda
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAULT = Path(os.environ.get("VAULT_DIR", ROOT / "vault"))
DATA = ROOT / "data" / "transcricoes"
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()[:80] or "video"


def hms(segundos: float) -> str:
    s = int(segundos)
    return f"{s // 3600:02}:{s % 3600 // 60:02}:{s % 60:02}"


def eh_url(fonte: str) -> bool:
    return fonte.startswith(("http://", "https://"))


def extrair_audio(fonte: str, pasta: Path) -> Path:
    """Gera um mp3 mono 16 kHz (~15 MB/h), que é tudo que o Whisper precisa."""
    if eh_url(fonte):
        subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "-o", str(pasta / "audio.%(ext)s"), fonte],
            check=True,
        )
        return pasta / "audio.mp3"
    saida = pasta / "audio.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", fonte,
         "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(saida)],
        check=True,
    )
    return saida


def titulo_da_url(url: str) -> str | None:
    try:
        r = subprocess.run(["yt-dlp", "--print", "title", "--skip-download", url],
                           check=True, capture_output=True, text=True)
        return r.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def transcrever(audio: Path, modelo: str, device: str, idioma: str) -> tuple[list[dict], float]:
    from faster_whisper import WhisperModel

    compute = "float16" if device == "cuda" else "int8"
    whisper = WhisperModel(modelo, device=device, compute_type=compute)
    segmentos, info = whisper.transcribe(str(audio), language=idioma, vad_filter=True)

    resultado = []
    for seg in segmentos:
        resultado.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        pct = 100 * seg.end / info.duration if info.duration else 0
        print(f"\r  {hms(seg.end)} / {hms(info.duration)} ({pct:5.1f}%)", end="", flush=True)
    print()
    return resultado, info.duration


def paragrafos(segmentos: list[dict], janela: float = 60.0) -> list[tuple[float, str]]:
    """Agrupa os segmentos em parágrafos de ~1 min, cada um com o horário de início."""
    blocos, inicio, atual = [], None, []
    for seg in segmentos:
        if inicio is None:
            inicio = seg["start"]
        atual.append(seg["text"])
        if seg["end"] - inicio >= janela:
            blocos.append((inicio, " ".join(atual)))
            inicio, atual = None, []
    if atual:
        blocos.append((inicio, " ".join(atual)))
    return blocos


def resumir(titulo: str, transcricao: str) -> str | None:
    """Gera resumo, tópicos e pontos-chave com o Claude (opcional)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=(
            "Você organiza transcrições de vídeos em notas do Obsidian, em português. "
            "Responda só com Markdown, sem preâmbulo, contendo exatamente as seções: "
            "'## Resumo' (1-3 parágrafos), '## Tópicos' (lista com o horário [hh:mm:ss] "
            "em que cada tópico começa) e '## Pontos-chave' (ideias, decisões, números, "
            "referências e recomendações citadas, com horário). "
            "Por fim, uma linha 'tags: a, b, c' com 3-8 tags em minúsculas, sem espaços."
        ),
        messages=[{"role": "user", "content": f"Título: {titulo}\n\n<transcricao>\n{transcricao}\n</transcricao>"}],
    )
    return resp.content[0].text.strip()


def escrever_nota(titulo, fonte, duracao, modelo, blocos, resumo) -> Path:
    tags = ["video", "transcricao"]
    if resumo:
        m = re.search(r"^tags:\s*(.+)$", resumo, re.MULTILINE | re.IGNORECASE)
        if m:
            tags += [slugify(t) for t in m.group(1).split(",") if t.strip()]
            resumo = resumo[: m.start()].rstrip()

    destino = VAULT / "Videos"
    destino.mkdir(parents=True, exist_ok=True)
    nome_arquivo = re.sub(r'[\\/:*?"<>|#^\[\]]', "", titulo).strip() or slugify(titulo)
    caminho = destino / f"{nome_arquivo}.md"

    titulo_yaml = titulo.replace('"', "'")
    linhas = [
        "---",
        f'title: "{titulo_yaml}"',
        "type: video",
        f'source: "{fonte}"',
        f"date_added: {datetime.date.today().isoformat()}",
        f'duration: "{hms(duracao)}"',
        f"whisper_model: {modelo}",
        f"tags: [{', '.join(dict.fromkeys(tags))}]",
        "---",
        "",
        f"# {titulo}",
        "",
        f"> [!info] Fonte: {fonte} · Duração: {hms(duracao)}",
        "",
    ]
    if resumo:
        linhas += [resumo, ""]
    linhas += ["## Transcrição", ""]
    linhas += [f"**[{hms(inicio)}]** {texto}\n" for inicio, texto in blocos]
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    return caminho


def main():
    p = argparse.ArgumentParser(description="Transcreve um vídeo e salva como nota no vault do Obsidian.")
    p.add_argument("fonte", help="arquivo de vídeo/áudio ou URL (YouTube etc.)")
    p.add_argument("--titulo", help="título da nota (padrão: nome do arquivo ou título do vídeo)")
    p.add_argument("--modelo", default=os.environ.get("WHISPER_MODEL", "medium"),
                   help="modelo Whisper: tiny, base, small, medium, large-v3 (padrão: medium)")
    p.add_argument("--device", default=os.environ.get("WHISPER_DEVICE", "auto"), help="cpu, cuda ou auto")
    p.add_argument("--idioma", default="pt")
    p.add_argument("--sem-resumo", action="store_true", help="não gerar resumo com o Claude")
    args = p.parse_args()

    if not eh_url(args.fonte) and not Path(args.fonte).exists():
        sys.exit(f"Arquivo não encontrado: {args.fonte}")

    titulo = args.titulo or (titulo_da_url(args.fonte) if eh_url(args.fonte) else None) \
        or Path(args.fonte).stem
    DATA.mkdir(parents=True, exist_ok=True)
    cache = DATA / f"{slugify(titulo)}.json"

    if cache.exists():
        print(f"Transcrição já existe em {cache}, reaproveitando (apague o arquivo para refazer).")
        dados = json.loads(cache.read_text(encoding="utf-8"))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            print("1/3 Extraindo áudio...")
            audio = extrair_audio(args.fonte, Path(tmp))
            print(f"2/3 Transcrevendo com Whisper '{args.modelo}' (pode demorar)...")
            segmentos, duracao = transcrever(audio, args.modelo, args.device, args.idioma)
        dados = {"titulo": titulo, "fonte": args.fonte, "duracao": duracao,
                 "modelo": args.modelo, "segmentos": segmentos}
        cache.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    blocos = paragrafos(dados["segmentos"])
    resumo = None
    if not args.sem_resumo:
        print("3/3 Gerando resumo e tópicos com o Claude...")
        texto = "\n".join(f"[{hms(i)}] {t}" for i, t in blocos)
        resumo = resumir(titulo, texto)
        if resumo is None:
            print("  ANTHROPIC_API_KEY não definida; nota salva só com a transcrição.")

    nota = escrever_nota(titulo, dados["fonte"], dados["duracao"], dados["modelo"], blocos, resumo)
    print(f"Pronto: {nota}")
    print("Rode `python ask.py` para atualizar o índice e fazer perguntas.")


if __name__ == "__main__":
    main()
