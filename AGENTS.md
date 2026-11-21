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
