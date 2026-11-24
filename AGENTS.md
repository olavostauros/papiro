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
- `api/` — read-only FastAPI over the DB (`/questoes`, `/questoes/{id}`, `/filtros`,
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
adapter (default `cebraspe`). Unified CLI `python -m crawler`.
Job-driven workflow (run
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
stack (`python -m crawler discover` + `crawler ingest` + `validate.py`)
runs entirely over the adapter — selection policy, local parsers and
record labels come from `job["banca"]` via `crawler/bancas/`.

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

## Subagents

Specialized subagent profiles live in `.agents/agents/<name>.md` (tracked;
`.devin/` is local-only). Spawn them with `run_subagent(profile: ...)`:

- `perito` — cybersecurity examiner (Perito Criminal Federal Área 14). Audits
  code/config/pipeline against `.agents/docs/SECURITY.md` — secrets handling,
  injection (SQL/subprocess/path/SSRF), stored XSS via dataset content, API
  posture, supply chain, CI. Read-only + exec; emits a **laudo pericial**
  (achados table, severity, `file:line` evidence, recommended fixes). Spawn it
  to review new banca adapters, API/web surface changes, Docker/CI changes, or
  on demand — it never edits source; the main agent remediates.
- `sentinela` — security remediation engineer, the write counterpart to
  `perito`. Implements each *correção recomendada* from a laudo pericial
  (validation at adapter boundaries, `resolve()`/`is_relative_to` at sinks,
  API/Docker hardening, dependency pins) — fail-closed fixes, minimal diff,
  full read/write/exec on source but never commits and never edits
  `SECURITY.md`/laudos. Emits a **relatório de remediação** (FIX/FIX-PARCIAL/
  ADIADO per achado + verifications + pendências). Spawn it to remediate a
  laudo — not to audit (that is perito).
- `auditor` — VM operations auditor (TCU/Receita do roster). The **only**
  profile shipped in the image (`COPY .agents/agents/auditor.md` →
  `/app/.agents/agents/`); administers the compose
  stack on the VM **as the non-root `papiro` user** (uid 10001 — bind
  mounts `data/`/`crawler/jobs/` must be writable by it), runs the
  scheduled ingest via `compose run`, verifies posture (no db port, no
  secret dumps). Emits a **relatório de fiscalização** com não
  conformidades + determinações.
- `arquivista` — data-operations archivist on the **host**. Runs the whole
  ingest workflow — `next/files/fetch`, job.json curation, `audit`,
  `assemble --write`, shard hygiene scan, `crawler.db sync`, batch
  commits — and edits only job configs/`crawler/jobs/` (pipeline code bugs
  get handed back). Also **launches the GCP deploy** host-side via
  `gcloud` per `.agents/docs/deploy-gcp.md`, then hands the VM to
  `auditor` (it never administers it). Emits a **guia de remessa**
  (acervo, irregularidades, destino, devoluções). Spawn it to ingest an
  evento, reconcile the dataset, or launch the deploy.

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
