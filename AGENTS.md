## Operação papiro — autonomous operation

This is an **ongoing dataset-building campaign**. The agent operates
autonomously: do NOT stop to ask which concurso to ingest next or wait for
confirmation between batches. Keep going until told to stop.

Loop:

1. Pick the next target from the Cebraspe events API
   (`https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos`, then
   `.../eventos/<ID>` for `arquivosGabarito`). Prefer recent, high-audience
   concursos and ones that add depth to cargos already in the dataset
   (e.g. previous editions of PF/PRF/IBAMA exams).
2. Download prova + gabarito PDFs from the CDN with `curl` (free).
3. Extract with the zero-credit local pipeline (see "Structured
   extraction"): `pdftohtml -xml` coordinate parse for items,
   `pdftotext -layout` for gabaritos. Audit dropped lines between items —
   comandos and base texts are dropped on purpose (dataset convention:
   enunciado = item statement only); anything else needs a fix — render
   the page to PNG and transcribe by hand when necessary.
4. Skip `X` (anulado) items, dedup by `id`, append to
   `web/src/data/questions.json` via `crawler.models.to_questao()`.
5. Verify (counts match gabarito ranges, no id collisions, gabaritos
   valid) and commit each concurso batch with a message describing cargo
   coverage and anulados. Log Firecrawl calls in `FIRECRAWL_USAGE.md` if
   any are made (the local path should need none).

Working scripts from previous batches live in `/tmp/pf25/`, `/tmp/ibama25/`
and `/tmp/pf21/` (`local_parse.py`, `assemble.py`, `parse_gab.py`) — copy
and adapt them per concurso; `/tmp` may not survive reboots, so rebuild
from this document if gone. Known layout variants: some provas print
numbered instructions before the `-- PROVA OBJETIVA` marker (gate parsing
on the marker and require sequential item numbers — see `/tmp/pf21/`).
PF_18-era provas use a harder two-column variant: the base text sits in
the left column with its own lone line-number markers (1,4,7,...) at the
column edge while the item number is a separate edge-aligned element that
merges at the START of the item's first line. Fix: require item-start
lines to have non-empty text after the number, ignore lone-number lines
entirely, and treat situação/command first-lines that got appended to an
item's end as dropped (truncate at the last complete sentence) — see
`/tmp/pf18/` (`parse3.py`, `assemble.py`).

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

crawler-olavo extracts exam questions (provas/questões) as structured JSON
straight from the Firecrawl API — it does NOT work with markdown. Never scrape
a prova into markdown and parse it by hand; use the `json` format with an
explicit schema and prompt instead.

The MCP `firecrawl_scrape` tool has no `json` format — for structured
extraction, call the API/Python SDK directly. Canonical schemas and helpers
live in `crawler/` (`pip install -r crawler/requirements.txt`):

- `crawler/models.py` — `ProvaExtraida`/`QuestaoExtraida` (extraction
  schema), `ProvaMeta` (per-job metadata), `Questao` (dataset record matching
  `web/src/data/questions.json` exactly), `to_questao()` normalization and id
  slug generation (`<banca>-<ano>-<orgao>-<cargo>-NNN`).
- `crawler/extract.py` — `make_app()` (loads the key from
  `.env/FIRECRAWL_API_KEY`, never printed) and `extract_prova()` (one scrape
  → validated `ProvaExtraida`, credits auto-logged).
- `crawler/usage.py` — `log_call()` appends to `FIRECRAWL_USAGE.md` and
  refreshes its totals.

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
  for numero/enunciado. Working scripts live in `/tmp/pf25/` and `/tmp/ibama25/`
  (`local_parse.py`, `assemble.py`, `parse_gab.py`); rebuild from those if
  still present, and audit dropped lines between items before assembling.
- Cebraspe URL discovery is free: the SPA calls
  `https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos` (list) and
  `.../eventos/<ID>` (detail with `arquivosGabarito`, which holds provas and
  gabaritos). Files download from
  `https://cdn.cebraspe.org.br/concursos/<ID>/arquivos/<nomeArquivo>` —
  `curl` works directly, no Firecrawl needed. Prova objetiva files follow
  `<seq>_<EVENTO>_<cargo>_01.pdf` (e.g. `106_PF_015_01.pdf`).
- For multi-page provas, prefer `app.crawl`/`batch_scrape` with the same
  `formats` over looping single `scrape` calls.

### Credit control

Operação papiro runs on a limited Firecrawl credit budget. Every Firecrawl
call — MCP tool or Python SDK — MUST be logged in `FIRECRAWL_USAGE.md` at the
repo root: date, task, tool, item count, and `creditsUsed` from the response,
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
