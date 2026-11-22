## Operação papiro — autonomous operation

This is an **ongoing dataset-building campaign**. The agent operates
autonomously: do NOT stop to ask which concurso to ingest next or wait for
confirmation between batches. Keep going until told to stop.

Loop (automated — the pipeline lives in `crawler/cebraspe/`, run from the
repo root with `.venv/bin/python`):

1. `.venv/bin/python -m crawler.cebraspe next --probe 30` — ranks
   un-ingested events (detected via shard filenames in
   `data/questions/`) by ano/vagas and probes each detail for provas.
   Prefer recent, high-audience concursos and ones that add depth to
   cargos already in the dataset (e.g. previous editions of
   PF/PRF/IBAMA exams).
2. `.venv/bin/python -m crawler.cebraspe files <EVENTO_URL>` shows
   cargos + prova/gabarito classification; then
   `.venv/bin/python -m crawler.cebraspe fetch <EVENTO_URL>` downloads
   everything to `/tmp/<evento>/` and drafts `job.json` (prova↔gabarito
   pairing and cargo mapping from `descricaoArquivo`/`eventoCargos`).
3. Fix `job.json`: assign unmatched/shared provas (e.g. Conhecimentos
   Básicos) to each cargo, set `meta` (orgao/id_orgao/ano),
   `tipo: ce|mc` per prova, `variant`, `skip` (un-extractable items),
   `patch` (hand-transcribed enunciados). Commit a copy to
   `crawler/jobs/<EVENTO>.json`.
4. `.venv/bin/python -m crawler.cebraspe audit --workdir /tmp/<evento>`
   — parses every prova + gabarito, writes `dropped_<key>.txt`. Check
   counts match gabarito ranges and review dropped lines: comandos and
   base texts are dropped on purpose (dataset convention: enunciado =
   item statement only); anything else needs a fix — render the page to
   PNG and transcribe by hand when necessary.
5. `.venv/bin/python -m crawler.cebraspe assemble --workdir
   /tmp/<evento>` (dry-run), then `--write` — skips `X` (anulado),
   dedups by `id`, writes `data/questions/<EVENTO>.json` via
   `to_questao()` + `crawler/shards.py` (one shard per evento, interned
   dimensions; `shard_to_records()` flattens back). With `DATABASE_URL`
   set it also upserts the new records into Postgres (`crawler/db.py`).
6. Commit each concurso batch with a message describing cargo coverage
   and anulados. Log Firecrawl calls in `.agents/docs/FIRECRAWL_USAGE.md`
   if any are made (the local path should need none).

Parsers: `crawler/cebraspe/items.py` (certo/errado; `variant="old"` for
PF_18-era provas where the item number merges at the END of the item's
first line and lone line-number markers sit at the column edge),
`mc.py` (Questão N + alternativas A-E, captures per-item `assunto` from
ALL-CAPS headers), `gabarito.py` (auto-detects `Item/Gabarito` C/E and
`Questão` A-E/X formats). Known layout variants: some provas print
numbered instructions before the `-- PROVA OBJETIVA` marker (the parser
gates on the marker and keeps only the longest run of consecutive item
numbers). Reference jobs: `crawler/jobs/`.

## Dataset layout

The dataset lives in `data/questions/<EVENTO>.json` at the repo root —
one shard per concurso (shard name = the Cebraspe `eventoURL`, or
`EXTERNO_<banca>_<orgao>_<ano>` for other bancas). `crawler/shards.py`
owns the schema: `banca` at the top; `orgaos`/`cargos`/`assuntos`/
`provas.fonte` interned per shard and referenced by index from `itens`;
`alternativas` omitted when `["Certo","Errado"]`. `shard_to_records()`
flattens a shard back to the flat `Questao` shape (round-trip verified
byte-exact vs. the old monolith). Identity for dedup is `id`
(`<banca>-<ano>-<orgao>-<cargo>-NNN`); the assemble step dedups per
shard.

The old monolithic `web/src/data/questions.json` is gone (it crossed
GitHub's 100 MB blob limit; history was squashed to unblock push — see
`.agents/docs/dataset-sharding.md`). **The site does NOT bundle the
dataset**: it is served by the API on the VM — `web/src/data/questions.ts`
is the typed client (`fetch*` over `PUBLIC_API_URL`). Do not re-add
dataset imports or `import.meta.glob` over the shards in `web/`.

**Postgres + Docker + API — implemented** (plan + implementation notes:
`.agents/docs/docker-postgres.md`): the shards are the transport/backup
format; the query store is a Postgres container populated by the
idempotent shard→DB sync in `crawler/db.py` (`python -m crawler.db sync`,
verified vs. SQLite — 221.059 itens, ~5 s). Single `papiro` image backs
`api` (FastAPI in `api/`) and `crawler` (compose profile — one-shot
commands) in `compose.yaml`, alongside `postgres:17-alpine`. Keep writing
shards via `write_shard`; when `DATABASE_URL` is set, `assemble --write`
and `run.py` also upsert the new records to the DB (failure never blocks
the shard write). The site consumes `PUBLIC_API_URL` via
`web/src/data/questions.ts` (client) + `<question-browser>` (element).

## Development

The site lives in `web/` — run all npm/Astro commands from that directory.

When starting the dev server, use background mode:

```
cd web && astro dev --background
```

Manage the background server with `astro dev stop`, `astro dev status`, and `astro dev logs`.

## Design system

Tokens and base components live in `web/src/design/`. Read
`web/src/design/README.md` before writing any UI — it documents the semantic
tokens, component props, dark mode, and conventions agents must follow.
Interactive showcase: `web/src/pages/design.astro` (route `/papiro/design/`).

## Documentation

Full documentation: https://docs.astro.build

Consult these guides before working on related tasks:

- [Adding pages, dynamic routes, or middleware](https://docs.astro.build/en/guides/routing/)
- [Working with Astro components](https://docs.astro.build/en/basics/astro-components/)
- [Using React, Vue, Svelte, or other framework components](https://docs.astro.build/en/guides/framework-components/)
- [Adding or managing content](https://docs.astro.build/en/guides/content-collections/)
- [Adding styles or using Tailwind](https://docs.astro.build/en/guides/styling/)
- [Supporting multiple languages](https://docs.astro.build/en/guides/internationalization/)

## Firecrawl

Full documentation: https://docs.firecrawl.dev/ (agent-friendly index:
https://docs.firecrawl.dev/llms.txt)

Firecrawl exposes a hosted MCP server (Streamable HTTP). Connect with:

```
devin mcp add firecrawl https://mcp.firecrawl.dev/v2/mcp
```

The keyless endpoint exposes `firecrawl_search`, `firecrawl_scrape`, and
`firecrawl_parse` within daily limits. For the full tool surface, either add an
`Authorization: Bearer <FIRECRAWL_API_KEY>` header (keep the key in
`.devin/mcp_config.local.json`, which is gitignored) or use the OAuth endpoint
`https://mcp.firecrawl.dev/v2/mcp-oauth` and run `devin mcp login firecrawl`.

See the tool reference for which tool to use when:
https://docs.firecrawl.dev/mcp-server/tools

### Structured extraction (crawler-olavo)

crawler-olavo extracts exam questions (provas/questões) as structured JSON.
Two paths exist — for Cebraspe provas the zero-credit local pipeline is the
preferred and authoritative one (see the bullet below); use the Firecrawl
`json` format path only for sources the local parser cannot reach. When
extracting via Firecrawl, never scrape a prova into markdown and parse it by
hand; use the `json` format with an explicit schema and prompt instead.

The MCP `firecrawl_scrape` tool has no `json` format — for structured
extraction, call the API/Python SDK directly. Canonical schemas and helpers
live in `crawler/` (`pip install -r crawler/requirements.txt`):

- `crawler/models.py` — `ProvaExtraida`/`QuestaoExtraida` (extraction
  schema), `ProvaMeta` (per-job metadata), `Questao` (dataset record matching
  `data/questions/` shards exactly), `to_questao()` normalization and id
  slug generation (`<banca>-<ano>-<orgao>-<cargo>-NNN`).
- `crawler/extract.py` — `make_app()` (loads the key from
  `.env/FIRECRAWL_API_KEY`, never printed) and `extract_prova()` (one scrape
  → validated `ProvaExtraida`, credits auto-logged).
- `crawler/usage.py` — `log_call()` appends to
  `.agents/docs/FIRECRAWL_USAGE.md` and refreshes its totals.

```python
from crawler.extract import make_app, extract_prova
from crawler.models import ProvaMeta, to_questao

app = make_app()
prova = extract_prova(app, url_da_prova, task="cebraspe-2024-pf-escrivao")
meta = ProvaMeta(
    banca="Cebraspe", orgao="Polícia Federal",
    cargo="Escrivão de Polícia Federal", ano=2024,
    fonte="https://cdn.cebraspe.org.br/concursos/PF_24/",
    id_orgao="pf", id_cargo="escrivao",
)
questoes = [to_questao(q, meta) for q in prova.questoes]  # needs gabaritos
```

- Gabaritos are usually published as a separate document — expect a second
  extraction pass to join answers onto questions (`to_questao` refuses to
  emit a record without a valid gabarito).
- NEVER trust `QuestaoExtraida.gabarito` from a prova scrape — the extractor
  hallucinates answers when none are printed (observed 2026-11-21: it
  invented mostly-wrong gabaritos on a Cebraspe prova). Always override with
  the official gabarito document via `to_questao(q, meta, gabarito=...)`.
- Cebraspe gabarito PDFs are simple text tables: parse them locally with
  `pdftotext -layout` — free and exact, whereas LLM extraction misread 3 of
  24 items on the first try. `X` means the item was anulado: skip it, do not
  emit a record.
- For Cebraspe provas the zero-credit path is preferred: download the PDF
  with `curl`, parse items with a coordinate-based `pdftohtml -xml` script
  (item numbers sit at the column edge, continuations are indented) and the
  gabarito with `pdftotext -layout`. The PF 2025 batch showed LLM `json`
  extraction is unreliable — it misnumbered items, pasted base text as
  enunciados and truncated statements — so the local parse is authoritative
  for numero/enunciado. Working scripts live in `/tmp/pf25/`, `/tmp/ibama25/`
  and `/tmp/pf18/` (`local_parse.py`, `assemble.py`, `parse_gab.py`,
  `parse3.py`); rebuild from those if still present, and audit dropped lines
  between items before assembling.
- Cebraspe URL discovery is free: the SPA calls
  `https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos` (list) and
  `.../eventos/<ID>` (detail with `arquivosGabarito`, which holds provas and
  gabaritos). Files download from
  `https://cdn.cebraspe.org.br/concursos/<ID>/arquivos/<nomeArquivo>` —
  `curl` works directly, no Firecrawl needed. Prova objetiva naming varies by
  event: `<seq>_<EVENTO>_<cargo>_01.pdf` (e.g. `106_PF_015_01.pdf`,
  `651_IBAMA_CB1_01.PDF`, `956_ANVISA_CC1_01.PDF`) or, for pre-2021 events,
  `MATRIZ_<seq>_<EVENTO>..._PAG_N.PDF` with `GAB_DEFINITIVO_*` gabaritos —
  always list `arquivosGabarito` and match files by `GAB_`/`MATRIZ`/`DISC`
  prefixes rather than assuming one pattern.
- For multi-page provas, prefer `app.crawl`/`batch_scrape` with the same
  `formats` over looping single `scrape` calls.

### Credit control

Operação papiro runs on a limited Firecrawl credit budget. Every Firecrawl
call — MCP tool or Python SDK — MUST be logged in
`.agents/docs/FIRECRAWL_USAGE.md`: date, task, tool, item count, and
`creditsUsed` from the response,
keeping the running totals current. See that file for the cost guide;
prefer cheap paths (`map` for URL discovery, `maxAge` cache, basic proxy)
before spending on stealth or retries.

## Secrets

Secrets live in the `.env/` directory at the repo root. It is fully
gitignored (see `.gitignore`), as are `*.local.json` configs — nothing in it
may ever be committed or pasted into the chat.

Rules for agents:

- NEVER read, cat, grep, print, or quote the contents of `.env/`,
  `*.local.json`, `*.pem`, or `*.key` files. Project permissions
  (`.devin/config.json`) deny Read/Write on them; do not work around this
  with shell commands that echo values into the transcript.
- Refer to secrets by name/path only (e.g. "the key in
  `.env/FIRECRAWL_API_KEY`").
- To wire a secret into local config without exposing it, use shell
  indirection so the value never reaches the transcript, e.g.:

  ```
  jq --arg k "$(tr -d '[:space:]' < .env/FIRECRAWL_API_KEY)" \
    '.mcpServers.firecrawl.headers.Authorization = "Bearer \($k)"' \
    .devin/mcp_config.local.json > /tmp/mcp.json \
    && mv /tmp/mcp.json .devin/mcp_config.local.json
  ```

- To upload secrets to Devin Cloud (for cloud sessions), use
  `devin cloud drs secret-create --from-file .env/<file>` or
  `--from-dotenv .env/<file>` — these read the value themselves and never
  print it.
- For GitHub Actions, add secrets via `gh secret set <NAME> < .env/<file>`
  (or the repo settings UI) — never in workflow files.
