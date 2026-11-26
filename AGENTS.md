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
  Deploy plan + schema decisions: `.agents/docs/docker-postgres.md`;
  runbook: `.agents/docs/deploy-gcp.md`. **Deployed 2026-11-23** — GCP
  `e2-small` behind Cloudflare Tunnel (`https://api.olavostauros.com`),
  daily ingest via systemd timer; state + open determinações in
  `.agents/docs/pericias/2026-11-24_fiscalizacao-vm.md`. Image changes
  are built in CI (`.github/workflows/image.yml` — pushes to AR once
  WIF is provisioned, deploy-gcp.md §CI—imagem); the VM stays pull-based.

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
   `job.json`. Eventos confirmados não-ingeríveis (prova discursiva,
   sem arquivos, API 500 permanente) vão em `crawler/jobs/_skip.json`
   (`{evento: motivo}`) — `done_eventos()` os trata como feitos e o
   `next` não os reprova a cada run.
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

Subagent profiles are markdown charters. The Devin CLI discovers
project-level profiles from `agents/` dirs: `.agents/agents/` (tracked —
present in **every** clone, including the VM checkout and the image build
context) and `.devin/agents/` (local-only, gitignored). Layout here:

- `.agents/agents/` — profiles valid in every environment. Only `auditor`
  lives here: the VM must see exactly one agent — the one that administers
  it — and it is also the only profile `COPY`ed into the image.
- `.agents/host-agents/` — host-only charters (`perito`, `sentinela`,
  `arquivista`, `escriba`, `iluminista`, `papiro-logo`), tracked for versioning but NOT auto-discovered. On the
  host, activate them once per clone:
  `mkdir -p .devin/agents && cd .devin/agents && ln -sf ../../.agents/host-agents/*.md .`

For Codex, the `papiro-logo` adapter also lives in
`.agents/host-agents/papiro-logo.toml` and loads the Markdown charter as its
source of instructions. After unlocking/deobfuscating `.agents/`, activate
it locally from the repository root:

```bash
mkdir -p .codex/agents
ln -s ../../.agents/host-agents/papiro-logo.toml .codex/agents/papiro-logo.toml
```

`.codex/` is local-only and gitignored, including the symlink. Never stage
or force-add its contents; version the charter and adapter under `.agents/`
through the notes pipeline. In Codex, delegate logo work to `papiro-logo`;
the Devin equivalent is `run_subagent(profile: "papiro-logo", ...)`.

Spawn the host profiles with `run_subagent(profile: ...)`. `auditor` is
the exception: `run_subagent` always executes on the host, and the
charter forbids it there — delegate via the herdr bridge (next section)
instead.

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
  profile under `.agents/agents/` and the only one shipped in the image
  (`COPY .agents/agents/auditor.md` → `/app/.agents/agents/`); administers the compose
  stack on the VM **as the non-root `papiro` user** (uid 10001 — bind
  mounts `data/`/`crawler/jobs/` must be writable by it), runs the
  scheduled ingest via `compose run`, verifies posture (no db port, no
  secret dumps), and **owns the VM git lifecycle** — watches the
  `papiro-git-sync` timer, resolves rebase CONFLITOs, and decides when
  local commits ship to the host via `git bundle` + `gcloud scp`. Emits
  a **relatório de fiscalização** com não conformidades + determinações.
  Reach it through the herdr bridge below — never `run_subagent`.
- `escriba` — frontend engineer scribe. Owns `web/` (Astro + Tailwind v4,
  custom elements, design system) and wires it to the
  read-only API through `web/src/data/questions.ts`. Enforces
  `web/src/design/README.md` (semantic tokens, `data-*` contracts,
  a11y mechanics, no UI framework); `api/`/`crawler/` are read-only
  reference — needed contract changes come back as devoluções, never
  edits. The words are iluminista's: escriba ships functional pt-BR
  copy and flags it for refinement. Emits
  a **colofão** (obra, materiais, integração, verificações,
  devoluções). Spawn it for new pages/components/elements,
  question-browser work, or design-system extensions.
- `iluminista` — UX copywriter, the voice of `web/`. Owns every word
  the concurseiro reads: pt-BR titles/descriptions, flavor text,
  empty states, status/feedback messages, labels, `aria-*`/`alt`
  wording — strictly text, never markup, logic, styles, or `data-*`
  contracts (those stay with escriba). Maintains the voz-e-tom guide
  (`web/src/design/copy.md`). Emits a **rubrica** (textos, voz,
  verificações, devoluções). Spawn it for copywriting, microcopy,
  empty-state/error wording, and copy review of new UI.
- `papiro-logo` — visual identity designer. Owns `brand/`: the papiro
  symbol and wordmark, SVG sources, light/dark and monochrome variants,
  previews, and usage documentation. Preserves existing work, validates
  SVG geometry and legibility at small sizes, and records font/color
  provenance. Site integration goes to `escriba`, interface wording to
  `iluminista`. Reports as a **memorial de marca**. Spawn it for logo
  creation, refinement, exports, and visual identity review.
- `arquivista` — data-operations archivist on the **host**. Runs the whole
  ingest workflow — `next/files/fetch`, job.json curation, `audit`,
  `assemble --write`, shard hygiene scan, `crawler.db sync`, batch
  commits — and edits only job configs/`crawler/jobs/` (pipeline code bugs
  get handed back). Also **launches the GCP deploy** host-side via
  `gcloud` per `.agents/docs/deploy-gcp.md`, then hands the VM to
  `auditor` (it never administers it). Emits a **guia de remessa**
  (acervo, irregularidades, destino, devoluções). Spawn it to ingest an
  evento, reconcile the dataset, or launch the deploy.

## Reaching the VM agent (herdr)

A Devin session lives on `papiro-vm` inside a pane of the VM's own
`herdr` server. The host reaches it through herdr's machine forwarding
(saved profile `papiro-vm`, SSH over IAP) — this is the delegation path
for `auditor` work:

```
herdr --machine papiro-vm agent list                # discover the pane id
herdr --machine papiro-vm agent prompt <PANE> "..." --wait --timeout 90000
herdr --machine papiro-vm agent read <PANE> --lines 80
```

- Agent commands take a live name or pane ID (`w2:p1`), never the agent
  kind — `agent prompt devin` fails `agent_not_found`. The remote agent
  is unnamed; optionally name it once per session
  (`agent rename <PANE> auditor`) or rediscover the pane id each time.
- Omitting `--machine` targets the *local* session — where the only
  agent is the host Devin itself.
- Forwarding never installs or starts the remote server. The VM's
  `herdr server` is an unsupervised daemon and the devin pane is
  ephemeral — after a VM reboot the channel is dead until restarted
  over SSH (`ssh papiro-vm-iap`, then start herdr + a devin pane).
- `agent prompt` rejects a `blocked` agent (`agent_blocked`); `--wait`
  needs `working`/`blocked` within 5 s or returns `agent_prompt_stalled`.
  IAP drops are transient — retry, but check remote state first: a lost
  connection doesn't prove the prompt wasn't applied.

## Encrypted `.agents/` (notes + git-crypt)

Since 2026-11-24 `.agents/**` is git-crypt-encrypted with filenames
obfuscated via [`notes`](https://github.com/KnickKnackLabs/notes)
(`--dir .agents`, notes `0.10.3`, rudi `0.5.4`). Git stores
`.agents/<8-hex>` ciphertext blobs; unlocked clones see readable names.
History was rewritten (filter-repo) — plaintext .agents exists in no
reachable commit; old SHAs may linger in GitHub caches — treat
pre-2026-11-24 content as previously public.

On unlocked machines (host, VM) files just work — read/write normally.
Commit changes through the notes pipeline so blobs stay encrypted and
names opaque:

```
notes stage --all --dir .agents          # or let the pre-commit hook auto-obfuscate
git commit -m "..."                       # hooks obfuscate + verify
notes changes --dir .agents              # readable diffs
notes verify-blobs --ref HEAD --strict --dir .agents   # before pushing
```

Joining an existing clone: `git crypt unlock` (needs a collaborator
GPG key in the local keyring) → `notes install-hooks --yes --dir
.agents` → `notes deobfuscate --dir .agents`. Plain `git pull` then
auto-deobfuscates via the post-merge hook. The VM (`~/papiro`) is a GPG
collaborator — add users with `notes add-user --gpg-key <fpr>` from the
host; symmetric break-glass key at `.env/git-crypt/papiro.key` +
1Password doc "papiro git-crypt symmetric key" (vault Agents).

**Caveat (notes 0.10.3):** the package's hook templates drop `--dir` on
`run_notes obfuscate|deobfuscate`, breaking custom dirs. Patched
locally at
`~/.local/share/mise/installs/shiv-notes/0.10.3/packages/notes/hooks/*.template`
(and on the VM). Reinstalling/upgrading notes reverts it — re-apply:
`sed -i 's/run_notes deobfuscate/run_notes deobfuscate --dir
"$NOTES_ROOT"/g; s/run_notes obfuscate/run_notes obfuscate --dir
"$NOTES_ROOT"/g' <pkg>/hooks/*.template` then `notes install-hooks
--yes --dir .agents`. Also `notes unlock`'s deobfuscation check is
hardcoded to `notes/` — run `notes deobfuscate --dir .agents` manually.

## Development

Host: Omarchy (Arch) — editor padrão é `nvim`. A VM `papiro-vm`
(Debian 12) também tem neovim instalado via apt (0.7.2) — prefira-o
a vim/nano em edições remotas.

The site lives in `web/` — run all npm/Astro commands from that directory.

```
cd web && npm run dev                # dev server (long-running — background it)
npm run build && npm run preview     # production build check
```

Tokens and base components live in `web/src/design/` — read
`web/src/design/README.md` before writing UI. Showcase: `/papiro/design/`.

## Secrets

Secrets live in `.env/` at the repo root — fully gitignored, never
committed or pasted into chat. Rules:

- NEVER read, cat, grep, print, or quote `.env/`, `*.local.json`, `*.pem`,
  or `*.key` files. A local `.devin/config.json` denies Read/Write on them
  (recreated per clone — see `.agents/docs/SECURITY.md` §7); do not work
  around this with shell commands echoing values into the transcript.
- Refer to secrets by name/path only ("the keys in `.env/docker.env`",
  "`.env/cloudflared/creds.json`").
- Wire secrets into config via shell indirection so the value never reaches
  the transcript, e.g. `jq --arg k "$(tr -d '[:space:]' < .env/KEY)" ...`;
  compose takes the aggregate via `--env-file .env/docker.env`.
- Upload to Devin Cloud with `devin cloud drs secret-create --from-file
  .env/<file>`; to GitHub Actions with `gh secret set <NAME> < .env/<file>`.
