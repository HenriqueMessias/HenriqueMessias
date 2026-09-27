# Segundo Cérebro — vídeos → Obsidian → perguntas

Transforma vídeos longos em notas pesquisáveis num vault do Obsidian e permite fazer
perguntas sobre tudo o que já foi adicionado. Cada vídeo novo alimenta a mesma base.

```
vídeo/URL ──ffmpeg/yt-dlp──▶ áudio ──Whisper──▶ transcrição ──Claude──▶ nota .md no vault
                                                                          │
                            ask.py ◀── índice vetorial (Chroma) ◀─────────┘
                            Hermes Agent / Obsidian ◀── lê o mesmo vault
```

## Estrutura

```
segundo-cerebro/
├── ingest.py          # adiciona um vídeo (transcreve + resume + cria a nota)
├── ask.py             # perguntas sobre o vault (RAG) ou sobre uma nota inteira
├── vault/             # ← abra esta pasta no Obsidian ("Open folder as vault")
│   ├── Videos/        # uma nota por vídeo: resumo, tópicos, pontos-chave, transcrição
│   ├── Notas/         # suas próprias anotações (também entram nas buscas)
│   └── Perguntas/     # perguntas e respostas salvas com --salvar
└── data/              # cache das transcrições e índice vetorial (gerado, não versionado)
```

O conteúdo de `vault/` e `data/` fica fora do git (veja `.gitignore`), para suas
transcrições não irem parar num repositório público.

## Instalação

```bash
# ffmpeg: sudo apt install ffmpeg  |  brew install ffmpeg  |  winget install ffmpeg
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...                 # Windows: set ANTHROPIC_API_KEY=...
```

## Uso

```bash
# 1. Adicionar um vídeo (arquivo local ou URL)
python ingest.py "/caminho/live.mp4" --titulo "Live sobre X - 2026-09"
python ingest.py "https://www.youtube.com/watch?v=..."

# 2. Perguntar sobre tudo que está no vault
python ask.py --salvar

# ou conversar com um vídeo específico (a nota inteira vai para o Claude)
python ask.py --nota "Live sobre X - 2026-09"
```

A primeira execução do `ask.py` baixa o modelo de embeddings (~1 GB). Depois disso,
ele só reindexa as notas novas ou alteradas.

### Escolhendo o modelo do Whisper

| Máquina                | Opção                                   | 3 h de vídeo leva aprox. |
|------------------------|-----------------------------------------|--------------------------|
| GPU NVIDIA             | `--modelo large-v3 --device cuda`       | 10–20 min                |
| CPU boa                | `--modelo medium` (padrão)              | 2–4 h                    |
| CPU fraca / teste      | `--modelo small`                        | 1–2 h                    |

A transcrição fica salva em `data/transcricoes/`. Se algo falhar depois dela (por
exemplo, o resumo), rodar o mesmo comando de novo reaproveita a transcrição.

### Variáveis de ambiente (opcionais)

| Variável         | Padrão                           | Para quê                        |
|------------------|----------------------------------|---------------------------------|
| `VAULT_DIR`      | `./vault`                        | usar um vault que já existe     |
| `WHISPER_MODEL`  | `medium`                         | modelo padrão do Whisper        |
| `WHISPER_DEVICE` | `auto`                           | `cpu` ou `cuda`                 |
| `CLAUDE_MODEL`   | `claude-sonnet-5`                | modelo usado no resumo/respostas|
| `EMBED_MODEL`    | `intfloat/multilingual-e5-base`  | modelo de embeddings            |

## Obsidian

O Obsidian é gratuito (inclusive para uso comercial). Pago é só o Sync e o Publish,
que não são necessários aqui. Abra a pasta `vault/` com **Open folder as vault**.
As notas já têm frontmatter (`type`, `tags`, `duration`, `date_added`), então funcionam
com Graph View, busca, tags e o plugin Dataview. Por exemplo:

````markdown
```dataview
TABLE duration, date_added FROM "Videos" SORT date_added DESC
```
````

## Conectando ao Hermes Agent (ou outro agente)

Como o vault é só uma pasta de arquivos Markdown, qualquer agente consegue usá-lo:

- **Acesso direto aos arquivos:** aponte o Hermes (ou qualquer ferramenta de
  filesystem/MCP) para a pasta `vault/`.
- **Via Obsidian:** instale o plugin da comunidade *Local REST API* (com suporte a MCP)
  e conecte o Hermes a esse servidor MCP. O agente passa a ler, buscar e criar notas
  pelo Obsidian aberto.

As notas que o agente criar em `vault/` entram automaticamente nas buscas do `ask.py`
na próxima execução.
