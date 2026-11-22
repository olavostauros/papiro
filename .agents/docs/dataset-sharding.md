# Particionamento do dataset (`questions.json` → shards por evento)

Plano registrado em 2026-11-22. Complementa `merge-crawler-leandro.md` —
a decisão arquitetural que destrava o push e simplifica o merge.

## Problema

GitHub rejeita qualquer **blob > 100 MB** em qualquer commit enviado
(pre-receive hook; avisa a partir de 50 MB). `web/src/data/questions.json`
cresceu de 17,7 MB (`a00fd22`, onde `origin/crawler-olavo` está parado) para
169 MB — cruzou o limite no commit `69e9fb4` (TJ-ES 2023). Dos 207 commits
não enviados, ~94 carregam blobs de 100–161 MB e **jamais subirão** — mesmo
que o arquivo atual encolhesse, os blobs grandes já estão gravados na
história. `.git` local já tem 4,2 GB de snapshots acumulados.

## Por que o arquivo é tão grande

219.073 registros (~770 B/registro) num array plano desnormalizado:

| campo | ~MB | observação |
|---|---|---|
| `enunciado` | ~46 | conteúdo real, insubstituível |
| `fonte` | ~20 | URL completa (~90 chars) repetida ~86×/prova (2.547 URLs) |
| `alternativas` | ~17 | `["Certo","Errado"]` idêntico nos 168.870 `certo_errado` |
| `cargo`+`orgao`+`assunto` | ~26 | rótulos repetidos (248 órgãos, 2.039 cargos) |
| `id` | ~12 | slug redundante com os demais campos |
| `banca`+`tipo` | ~10 | "Cebraspe"/"certo_errado" em quase tudo |
| `gabarito`+`ano` | ~7 | |

Minificar economiza só ~8%; gzip cai a ~25 MB (piso de entropia).

## Alternativas avaliadas

- **Postgres com o mesmo schema plano**: ~150–180 MB — *não* economiza
  espaço (overhead de tupla ~30 B/linha + índices). Normalizado: ~80–100 MB.
- **SQLite normalizado**: idem ~80 MB, arquivo único, zero infra. Bom
  upgrade se quisermos constraints/dedup nativos (`UNIQUE(fonte,cargo,item)`
  resolveria o dedup do merge por schema).
- **JSON normalizado + shards por evento** ✅ — solução mínima que resolve
  tamanho, git e merge ao mesmo tempo, sem adicionar infra e mantendo o
  site estático.

Conclusão: quem economiza espaço é a **normalização** (dimensões fora dos
fatos); quem resolve o git é o **particionamento** (nenhum blob > ~2 MB).

## Modelo novo (executado 2026-11-22)

```
data/questions/           ← raiz do repo (fora de web/)
  PF_24.json              ← banca + orgaos/cargos/assuntos/provas internadas
  TJ_ES_23.json              + itens referenciando por índice
  EXTERNO_FGV_...json     ← fontes não-Cebraspe
  ...                     ← 294 shards, ~115 MB total, máx ~2,6 MB
```

Decisões tomadas na execução:

- **Shard = evento** (`/concursos/<ID>/` do `fonte`), não por URL de
  prova — 294 arquivos (não ~2.500). Casa com `crawler/jobs/<EVENTO>.json`
  e com a semântica de merge ("conflito só se ingerirem o mesmo evento").
- **Sem `index.json` commitado** — seria ponto de contenção de merge; a
  listagem de eventos é o glob dos arquivos (`done_eventos()` usa os
  stems diretamente).
- **Dataset fora do site**: `web/` não empacota dados. O site será
  servido por uma **API na VM** (mesmo deploy do crawler Docker);
  `web/src/data/questions.ts` é stub vazio até o client existir. Isso
  também resolve o build do Astro, que estourava heap/string renderizando
  219k cards em `/index.html` — página única com tudo é inviável nessa
  escala, independente do formato de armazenamento.
- `id` mantido por item (dedup + debugging); `alternativas` omitida só
  quando `["Certo","Errado"]`; `ano` por item (varia em 4 eventos —
  dados com anos mistos, ex. ANAC_23); `orgao` internado por shard
  (varia em PETROBRAS_23_NTJ).

## Correção da história (blobs grandes já gravados)

**A. Squash (recomendado)** — colapsar a faixa `a00fd22..HEAD`:

```bash
git reset --soft a00fd22          # mantém arquivos, desfaz 206 commits
# script: questions.json → web/src/data/questions/*.json
# commit separado para o código do crawler (cebraspe/ + jobs/)
git commit -m "Ingest 247 events as sharded dataset (~219k records)"
```

Perde o commit-por-batch passado, mas cada evento vira seu arquivo e
`crawler/jobs/` já documenta as ingestões — a proveniência se preserva.

**B. `git filter-repo`** — reescreve cada snapshot trocando o monólito por
shards; preserva um commit por ingest, mas reescreve todos os SHAs (o
merge-base `a00fd22` muda → diverge do `crawler-leandro` publicado) e faz
replay de 200+ snapshots ~160 MB. Descartado salvo necessidade real.

## Impacto no merge (fazer ANTES do merge)

1. Aplicar o mesmo tratamento ao `crawler-leandro` (squash dos 26 commits
   a partir de `a00fd22`, `questions.json` → shards).
2. Merge de dados vira união de diretórios: eventos exclusivos entram
   direto; os ~52 eventos compartilhados são merges por arquivo com dedup
   `(prova-fonte, item-normalizado, cargo)` — a análise de
   `merge-crawler-leandro.md` se aplica por arquivo.
3. As ~27 mil duplicatas de slug caem por dedup de item (identidade =
   `(evento, prova, cargo, item)`, não o slug de `id_cargo`).
4. Reaplicação TRT8: prova distinta no mesmo evento — registros marcados
   `reaplicacao` (id e/ou campo), conforme decisão já tomada.

## Mudanças de código — status

- [x] `crawler/shards.py` — schema, `evento_key`, `records_to_shard` /
      `shard_to_records`, conversor one-shot (`python -m crawler.shards`);
      round-trip byte-exato (219.073 registros, 0 diffs)
- [x] `crawler/cebraspe/` `assemble` escreve `data/questions/<EVENTO>.json`;
      `done_eventos()` lê stems dos shards
- [x] `web/` desacoplado: `questions.json` removido, stub `questions.ts`
      até a API da VM existir
- [ ] `crawler/` leandro `run.py`: mesma emissão de shard (após merge)
- [ ] API na VM para servir o dataset ao site
- [ ] Decisão de granularidade de cargo (ver merge-crawler-leandro.md)
- [ ] Squash olavo + leandro; push; retomar merge em `crawler-merge`
- [ ] `git gc --prune=now` ou re-clone: `.git` local continua ~4,2 GB até
      coletar os blobs antigos (o push funciona mesmo assim)
