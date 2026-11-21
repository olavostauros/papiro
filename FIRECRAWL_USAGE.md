# Firecrawl credit usage — operação papiro

Ledger of Firecrawl credit consumption for the papiro pipeline (prova
extraction via crawler-olavo and any exploratory scraping).

**Rule:** every agent that calls the Firecrawl API or MCP server MUST append a
row to the log below after each call (or batch) and update the totals. Take the
count from the `creditsUsed` field in the response — MCP tools return it at top
level; the Python SDK exposes it on the scrape/crawl response metadata.
`crawler/usage.py::log_call()` does this automatically for SDK calls; keep the
`## Log` section last in this file so rows append cleanly at EOF.

## Totals

| Period       | Credits used |
| ------------ | ------------ |
| All time     | 38            |
| Current week | 38            |

## Cost guide (approximate — check the docs before big runs)

- `scrape`: ~1 credit/page; PDF parsing ~1 credit/page
- `json` format extraction: billed on top of the scrape (LLM extraction) — log
  whatever `creditsUsed` reports
- `search`: ~2 credits/query
- `map`: ~1 credit/site
- `crawl` / `batch_scrape`: ~1 credit/page fetched
- Stealth/enhanced proxy, screenshots, and actions add extra credits — only
  use them when the basic path fails.

Cost-conscious defaults: discover URLs with `map` or the banca's index pages
before scraping; reuse cache via `maxAge` when re-running; `onlyMainContent`
where possible; never retry blindly — log failures and pick a cheaper path.

Rate card reference: https://docs.firecrawl.dev/

## Log

| Date       | Task / caller          | Tool (MCP or SDK)  | Items   | Credits | Notes                                             |
| ---------- | ---------------------- | ------------------ | ------- | ------- | ------------------------------------------------- |
| 2026-11-21 | MCP connectivity check | `firecrawl_search` | 1 query | 2       | Verified API key auth — returned Alexandria tools |
| 2026-11-21 | cebraspe-2025-pf-escrivao-especificos | sdk:scrape[json] | 1 | 5 | https://cdn.cebraspe.org.br/concursos/PF_25/arquivos/106_PF_015_01.pdf |
| 2026-11-21 | cebraspe-2025-pf-escrivao-especificos-gabarito | sdk:scrape[json] | 1 | 5 | https://cdn.cebraspe.org.br/concursos/PF_25/arquivos/570C8865F7DDA1651ED10E330A6297A95466A2393EEEC633290FE754912D6143.pdf |
| 2026-11-21 | cebraspe-2025-pf-escrivao-bas-bloco1 | sdk:scrape[json] | 1 | 8 | https://cdn.cebraspe.org.br/concursos/PF_25/arquivos/106_PF_CB2_01.pdf |
| 2026-11-21 | cebraspe-2025-pf-escrivao-bas-bloco2 | sdk:scrape[json] | 1 | 6 | https://cdn.cebraspe.org.br/concursos/PF_25/arquivos/106_PF_CG1_01.pdf |
| 2026-11-21 | cebraspe-2025-pf-cargo016-especificos | sdk:scrape[json] | 1 | 6 | https://cdn.cebraspe.org.br/concursos/PF_25/arquivos/106_PF_016_01.pdf |
| 2026-11-21 | cebraspe-2025-pf-cargo017-especificos | sdk:scrape[json] | 1 | 6 | https://cdn.cebraspe.org.br/concursos/PF_25/arquivos/106_PF_017_01.pdf |
