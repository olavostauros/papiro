## Operação papiro — dataset-building campaign

Ongoing effort: ingest concurso provas into the question dataset. The agent
operates autonomously — do NOT stop to ask which concurso to ingest next.
Keep going until told to stop.

## Architecture

```
sites das bancas → crawler → PDFs → extração → shards (backup) → Postgres → api → site
```

- `data/questions/<EVENTO>.json` — one shard per concurso, transport/backup
  format owned by `crawler/shards.py` (interned dimensions; `alternativas`
  omitted iff `["Certo","Errado"]`; `shard_to_records()` flattens back to the
  flat `Questao` shape). Identity for dedup is `id`
  (`<banca>-<ano>-<orgao>-<cargo>-NNN`).
- Postgres is the query store — schema + idempotent sync in `crawler/db.py`
  (`python -m crawler.db sync`). When `DATABASE_URL` is set, the ingest
  pipeline upserts new records after writing the shard (DB failure never
  blocks the shard write).
- `api/` — read-only FastAPI over the DB (`/questoes`, `/filtros`,
  `/eventos`, `/provas`, `/health`).
- `web/` — Astro site; consumes the API via `web/src/data/questions.ts`
  (`PUBLIC_API_URL`) + `<question-browser>`. Never bundle the dataset.
- `compose.yaml` + `Dockerfile` — one `papiro` image backs `api` and
  `crawler` (compose profile, one-shot commands) next to `postgres:17-alpine`.
  Deploy plan + schema decisions: `.agents/docs/docker-postgres.md`.
  **Docker local first, then the cloud VM.**

## Crawler

The crawler is being reworked into a banca-agnostic pipeline — audit +
phased plan in `.agents/docs/crawler-rework.md`. Layout: generic core in
`crawler/` (models/shards/db/validate/gabarito/pdf/pipeline) + per-banca
adapters in `crawler/bancas/` (`base.py` = `BancaAdapter` contract;
`cebraspe/` = api/prova/textparse/selecao). `job["banca"]` resolves the
adapter (default `cebraspe`). Unified CLI `python -m crawler` (the old
`python -m crawler.cebraspe` still forwards). Job-driven workflow (run
from the repo root with `.venv/bin/python`):

1. `.venv/bin/python -m crawler next --probe 30` — ranks
   un-ingested events (shard filenames = Cebraspe `eventoURL`) by ano/vagas
   and probes each detail for provas.
2. `... files <EVENTO_URL>` shows cargos + prova/gabarito classification;
   `... fetch <EVENTO_URL>` downloads to `/tmp/<evento>/` and drafts
   `job.json`.
3. Fix `job.json`: assign unmatched/shared provas to cargos, set `meta`
   (orgao/id_orgao/ano), `tipo: ce|mc`, `variant`, `skip`, `patch`. Commit a
   copy to `crawler/jobs/<EVENTO>.json`.
4. `... audit --workdir /tmp/<evento>` — parses every prova + gabarito,
   writes `dropped_<key>.txt`. Comandos/base texts are dropped on purpose
   (dataset convention: enunciado = item statement only); anything else
   needs a fix — render the page to PNG and transcribe by hand.
5. `... assemble --workdir /tmp/<evento>` then `--write` — skips `X`
   (anulado), dedups by `id`, writes the shard and upserts the DB.
6. Commit each concurso batch describing cargo coverage and anulados.

Parsers: `crawler/bancas/cebraspe/prova.py` — the authoritative coordinate
parser (`pdftohtml -xml`): `tipo="ce"` certo/errado (`variant="old"` for
PF_18-era provas), `tipo="mc"` (Questão N + alternativas A-E + per-item
`assunto`). `crawler/gabarito.py` — `Gabarito` dataclass (`Item/Gabarito`
C/E and `Questão` A-E/X). `bancas/cebraspe/textparse.py` — secondary
`pdftotext -layout` engine for PDF cross-checks. The automated manifest
stack (`python -m crawler discover` → `run.py` via `crawler ingest` +
`validate.py`) shares the same adapter — being merged into the unified
pipeline per the rework doc.

## Firecrawl

Docs: https://docs.firecrawl.dev/ (index: https://docs.firecrawl.dev/llms.txt)

- Local PDF parsing (poppler `pdftotext`/`pdftohtml`) is the authoritative,
  zero-credit path. Firecrawl `json` extraction is a fallback for sources
  the local parser cannot reach — it has hallucinated gabaritos and
  misnumbered items on Cebraspe provas; never trust `QuestaoExtraida
  .gabarito`, always override with the official gabarito document.
- `X` in a gabarito = item anulado: skip it, emit no record.
- Every Firecrawl call (MCP or SDK) MUST be logged in
  `.agents/docs/FIRECRAWL_USAGE.md` — `crawler/usage.py::log_call()` does it
  for SDK calls. Prefer cheap paths (`map`, `maxAge`, basic proxy).
- MCP server: `devin mcp add firecrawl https://mcp.firecrawl.dev/v2/mcp`;
  full tool surface needs `Authorization: Bearer` (key in
  `.devin/mcp_config.local.json`) or the OAuth endpoint + `devin mcp login`.

## Development

The site lives in `web/` — run all npm/Astro commands from that directory.

```
cd web && astro dev --background      # dev server in background
astro dev stop | status | logs        # manage it
```

Tokens and base components live in `web/src/design/` — read
`web/src/design/README.md` before writing UI. Showcase: `/papiro/design/`.

## Secrets

Secrets live in `.env/` at the repo root — fully gitignored, never
committed or pasted into chat. Rules:

- NEVER read, cat, grep, print, or quote `.env/`, `*.local.json`, `*.pem`,
  or `*.key` files. `.devin/config.json` denies Read/Write on them; do not
  work around this with shell commands echoing values into the transcript.
- Refer to secrets by name/path only ("the key in `.env/FIRECRAWL_API_KEY`").
- Wire secrets into config via shell indirection so the value never reaches
  the transcript, e.g. `jq --arg k "$(tr -d '[:space:]' < .env/KEY)" ...`.
- Upload to Devin Cloud with `devin cloud drs secret-create --from-file
  .env/<file>`; to GitHub Actions with `gh secret set <NAME> < .env/<file>`.
