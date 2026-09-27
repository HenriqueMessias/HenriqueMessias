#!/usr/bin/env python3
"""Pergunte ao seu segundo cérebro (todas as notas do vault do Obsidian).

Uso:
    python ask.py                      # busca em todo o vault (RAG)
    python ask.py --nota "Aula 1"      # manda a nota inteira ao Claude (melhor para 1 vídeo)
    python ask.py --salvar             # grava perguntas e respostas em vault/Perguntas/
    python ask.py --reindexar          # reconstrói o índice do zero
"""
import argparse
import datetime
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAULT = Path(os.environ.get("VAULT_DIR", ROOT / "vault"))
CHROMA_DIR = ROOT / "data" / "chroma"
EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-base")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
CHUNK_CHARS = 1500
IGNORAR = {".obsidian", ".trash", "Perguntas"}

TIMESTAMP = re.compile(r"\*\*\[(\d{2}:\d{2}:\d{2})\]\*\*")

SYSTEM = (
    "Você é o assistente do segundo cérebro do usuário. Responda em português usando APENAS "
    "os trechos de notas fornecidos. Cite as fontes como [[Nome da nota]] e, quando houver, "
    "o horário (hh:mm:ss) em que o assunto aparece no vídeo. Se a informação não estiver nos "
    "trechos, diga claramente que não encontrou."
)


def notas() -> list[Path]:
    return sorted(p for p in VAULT.rglob("*.md")
                  if not IGNORAR.intersection(p.relative_to(VAULT).parts))


def sem_frontmatter(texto: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", texto, flags=re.DOTALL)


def pedacos(texto: str) -> list[tuple[str, str]]:
    """Divide a nota em trechos de ~CHUNK_CHARS, guardando o horário onde cada um começa."""
    resultado, atual, inicio, ultimo_ts = [], [], "", ""
    for par in re.split(r"\n\s*\n", sem_frontmatter(texto)):
        par = par.strip()
        if not par:
            continue
        m = TIMESTAMP.search(par)
        if m:
            ultimo_ts = m.group(1)
        if not atual:
            inicio = ultimo_ts
        atual.append(par)
        if sum(len(x) for x in atual) >= CHUNK_CHARS:
            resultado.append((inicio, "\n\n".join(atual)))
            atual = []
    if atual:
        resultado.append((inicio, "\n\n".join(atual)))
    return resultado


class Indice:
    def __init__(self, reindexar: bool = False):
        import chromadb
        from sentence_transformers import SentenceTransformer

        self.modelo = SentenceTransformer(EMBED_MODEL)
        cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
        if reindexar:
            try:
                cliente.delete_collection("vault")
            except Exception:
                pass
        self.col = cliente.get_or_create_collection("vault", metadata={"hnsw:space": "cosine"})

    def embed(self, textos: list[str], prefixo: str) -> list[list[float]]:
        # Os modelos e5 esperam os prefixos "query: " e "passage: "
        return self.modelo.encode([prefixo + t for t in textos], normalize_embeddings=True).tolist()

    def sincronizar(self):
        """Indexa só as notas novas ou alteradas e remove as apagadas."""
        existentes = {}
        for meta in self.col.get(include=["metadatas"])["metadatas"]:
            existentes[meta["nota"]] = meta["hash"]

        atuais = {}
        for caminho in notas():
            rel = str(caminho.relative_to(VAULT))
            texto = caminho.read_text(encoding="utf-8")
            h = hashlib.sha1(texto.encode()).hexdigest()
            atuais[rel] = h
            if existentes.get(rel) == h:
                continue
            print(f"  indexando {rel}")
            self.col.delete(where={"nota": rel})
            trechos = pedacos(texto)
            if not trechos:
                continue
            self.col.add(
                ids=[f"{rel}#{i}" for i in range(len(trechos))],
                documents=[t for _, t in trechos],
                embeddings=self.embed([t for _, t in trechos], "passage: "),
                metadatas=[{"nota": rel, "hash": h, "inicio": ts} for ts, _ in trechos],
            )
        for rel in set(existentes) - set(atuais):
            print(f"  removendo {rel}")
            self.col.delete(where={"nota": rel})

    def buscar(self, pergunta: str, k: int) -> str:
        r = self.col.query(query_embeddings=self.embed([pergunta], "query: "), n_results=k)
        blocos = []
        for doc, meta in zip(r["documents"][0], r["metadatas"][0]):
            nome = Path(meta["nota"]).stem
            quando = f" | a partir de {meta['inicio']}" if meta["inicio"] else ""
            blocos.append(f"<trecho nota=\"{nome}\"{quando}>\n{doc}\n</trecho>")
        return "\n\n".join(blocos)


def salvar(pergunta: str, resposta: str):
    pasta = VAULT / "Perguntas"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{datetime.date.today().isoformat()}.md"
    with arquivo.open("a", encoding="utf-8") as f:
        f.write(f"## {pergunta}\n\n{resposta}\n\n")


def main():
    p = argparse.ArgumentParser(description="Faça perguntas sobre as notas do vault.")
    p.add_argument("--nota", help="conversar com uma nota inteira (nome do arquivo, sem .md)")
    p.add_argument("-k", type=int, default=8, help="quantos trechos buscar por pergunta (padrão: 8)")
    p.add_argument("--salvar", action="store_true", help="salvar perguntas e respostas no vault")
    p.add_argument("--reindexar", action="store_true", help="reconstruir o índice do zero")
    args = p.parse_args()

    import anthropic
    client = anthropic.Anthropic()

    indice = None
    system = [{"type": "text", "text": SYSTEM}]
    if args.nota:
        encontradas = [n for n in notas() if n.stem.lower() == args.nota.lower()]
        if not encontradas:
            sys.exit(f"Nota não encontrada: {args.nota}")
        conteudo = sem_frontmatter(encontradas[0].read_text(encoding="utf-8"))
        # A nota inteira vai no prompt e fica em cache entre as perguntas
        system.append({"type": "text", "cache_control": {"type": "ephemeral"},
                       "text": f"<nota nome=\"{encontradas[0].stem}\">\n{conteudo}\n</nota>"})
    else:
        print("Atualizando índice...")
        indice = Indice(args.reindexar)
        indice.sincronizar()

    historico = []
    while True:
        try:
            pergunta = input("\nPergunta (enter para sair): ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not pergunta:
            break

        conteudo = pergunta
        if indice:
            conteudo = f"{indice.buscar(pergunta, args.k)}\n\nPergunta: {pergunta}"
        mensagens = historico[-6:] + [{"role": "user", "content": conteudo}]
        resp = client.messages.create(model=CLAUDE_MODEL, max_tokens=2000,
                                      system=system, messages=mensagens)
        resposta = resp.content[0].text
        print("\n" + resposta)

        # No histórico guardamos só a pergunta, para não acumular trechos antigos
        historico += [{"role": "user", "content": pergunta},
                      {"role": "assistant", "content": resposta}]
        if args.salvar:
            salvar(pergunta, resposta)


if __name__ == "__main__":
    main()
