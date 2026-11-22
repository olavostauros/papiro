# Merge `crawler-olavo` + `crawler-leandro` → `crawler-merge`

Análise feita em 2026-11-22. Objetivo: unir as duas linhas de crawler num
branch `crawler-merge` que será empacotado numa imagem Docker para rodar numa
VM.

## Topologia

```
ea0b7b2 (base comum com master)
  └── a00fd22 ──► crawler-olavo: +206 commits
         └──► crawler-leandro: +26 commits
```

`crawler-leandro` nasceu de `crawler-olavo` em `a00fd22` ("PM_TO 2020 QPPM"),
não de master. Logo o merge é simples: criar `crawler-merge` na ponta de
`crawler-olavo` e `git merge origin/crawler-leandro` — só entram os 26 commits
próprios do leandro.

## O que cada lado adiciona

| | crawler-olavo | crawler-leandro |
|---|---|---|
| Pipeline | pacote `crawler/cebraspe/` — `next/files/fetch/audit/assemble`, dirigido por `job.json`, parser por coordenadas `pdftohtml -xml` | `crawler/run.py` — CLI dirigida por manifesto, `--extrator local\|firecrawl\|hibrido` |
| Módulos novos | `api.py items.py mc.py gabarito.py pipeline.py __main__.py` | `discover.py extract_local.py gabarito.py run.py validate.py bench_local.py divergencias.py` |
| Dados | 195.006 registros novos (questions.json 17,7 MB → 169 MB) | 32.068 registros novos (→ 44 MB) |
| Outros | `crawler/jobs/*.json` (~200 jobs), AGENTS.md | `crawler/tests/` (5 arquivos + fixtures), `crawler/manifests/cebraspe.json` (4 MB), `docs/divergencias-pf2025.md`, requirements +`httpx`/`pytest`, `.gitignore` +`crawler/.cache/` `crawler/reports/` |

**Conflitos de código: zero.** Merge teste em worktree scratch confirmou: o
único conflito é `web/src/data/questions.json` (1 bloco de conflito — a região
de append).

## Comparação dos dados

Ambos os lados são **estritamente append-only**: 0 deleções, 0 alterações nos
24.067 registros da base comum.

### Colisões de `id` (2.150 registros)

- 223 idênticos
- **0 divergências de gabarito dentro da mesma prova** — todas as 38 diferenças
  de gabarito estão nos 49 pares `trt8-tecnico` (provas diferentes, ver abaixo)
- 196 diffs de `enunciado` na mesma prova: 176 só de espaçamento/pontuação
  ("n.o" vs "n.º"), ~20 substanciais — **os dois lados têm registros quebrados**:
  - olavo quebrado: `cebraspe-2024-anm-analista-direito-029` (fragmento
    truncado), `cebraspe-2024-trf6-analista-contabilidade-023–029` (manteve o
    comando mas perdeu o conteúdo julgado), `cebraspe-2025-tcemg-*-019`
    (fragmentos)
  - leandro quebrado: `cebraspe-2022-trt8-analista-administrativa-044` (texto de
    colunas embaralhado), `cebraspe-2026-cbmma-praca-combatente-012/030`,
    `cebraspe-2024-pcdf-odontologo-110`, `cebraspe-2025-tjro-remocao-094`
- 65 diffs de `alternativas`, 64 cosméticas
- `cargo`/`orgao`: inconsistência de nomenclatura **nos dois lados** (sigla ↔
  nome completo varia por evento; p.ex. ANM: olavo="ANM", leandro="Agência
  Nacional de Mineração"; TRF6: olavo=nome completo, leandro="TRF6")
- `assunto`: leandro preenche 986 vazios, mas com rótulos genéricos
  ("Conhecimentos Gerais/Específicos"); onde olavo preenche, é por disciplina
  ("LÍNGUA PORTUGUESA") — mais informativo

### Duplicatas ocultas além das colisões de id

**27.374 dos 32.068 registros do leandro duplicam itens de prova que o olavo já
tem, sob ids diferentes.** O slug divergiu (commit leandro `5685a98` encurtou
`id_cargo`): `tjpa-analista-judiciario-arquitetura` ↔ `tjpa-arquitetura`,
`tce-rj-procurador` ↔ `tcerj-procurador-ministerio`. Union por `id` injetaria
~30 mil duplicatas.

Contribuição **realmente nova** do leandro: ~1.850 registros —

- 2 eventos que o olavo não tem: `PC_PE_23` (97), `TJ_SC_22_NOTARIOS` (100)
- ~1.614 registros cobrindo itens/cargos que o olavo perdeu dentro de provas
  compartilhadas (top: CBM_MA_26 574, PM_MA_26 243, POLC_AL_22 136, TC_DF_23
  105, TJ_RR_25 102, TRF6_24 93)
- 49 registros `trt8-tecnico` da **reaplicação** (ver decisão abaixo)

### Granularidade de cargo (conflito de convenção)

Leandro mapeia por vaga do edital (PM_MA: "Soldado do Quadro de Praças Músicos
(Qpmus) – Especialidade: Clarinete/Tuba/…" — 11 cargos); olavo agrupa em cargo
guarda-chuva ("Soldado Músico"). Mesma prova, granularidades diferentes — ~20
eventos afetados (ANM_24, TJ_PA_25, TCE_AC_24, CPNUJE_24, POLC_AL_22, CBM_MA_26,
PM_MA_26, AGER_MT_23, TCE_RN_25, CNJ_24, TRT10_24, TCE_RS_25, TCE_MG_25,
BANRISUL_25, ARSAL_26, BANCO_DO_NORDESTE_22, TC_DF_23, TJ_MT_25, TJ_RR_25,
TJ_PE_24).

## Decisões tomadas

1. **Reaplicação TRT8 (49 registros): manter os dois lados com ids
   distintos.** São provas diferentes (olavo usou `759_TRT8_CG2_01.PDF`, leandro
   usou `793_TRT8_REAPLICACAO_CB1_01.PDF`). Renomear os ids do leandro para
   `cebraspe-2022-trt8-tecnico-administrativa-reaplicacao-NNN` — a diferença
   fica visível no próprio id.
2. **Colisões de id: comparar antes de decidir** — análise acima; a política
   final de resolução campo a campo fica para a execução.

## Decisão pendente

**Convenção de granularidade de cargo** para os ~20 eventos com split
guarda-chuva × por-vaga: (a) granularidade do leandro por vaga (mais fiel ao
edital — recomendado), (b) guarda-chuva do olavo, (c) manter ambos (duplicação
visível na UI). Se (a): descartar os registros guarda-chuva do olavo nos
eventos afetados.

## Procedimento de merge recomendado

```bash
git checkout -b crawler-merge crawler-olavo
git merge --no-ff origin/crawler-leandro   # conflito só em questions.json
```

Resolver `web/src/data/questions.json` por script (não à mão):

1. Base = array do olavo.
2. Para cada registro do leandro:
   - `(fonte, enunciado normalizado)` já coberto por registro olavo de cargo
     equivalente → fazer merge de metadata no registro olavo e pular;
   - colisão de `id` na mesma prova → merge campo a campo (enunciado/gabarito/
     alternativas do lado íntegro; cargo/orgao do lado mais legível; assunto:
     preferir o de disciplina quando houver, senão o genérico);
   - senão → append (items novos, eventos novos, reaplicação renomeada).
3. Emitir lista de revisão: ~20 enunciados divergentes + 1 diff substantiva de
   alternativas para conferir no PDF.
4. Validar: contagem por evento, `id` único, schema `Questao`.

Pós-merge no código:

- Manter os dois pipelines; `crawler/cebraspe/` continua canônico (AGENTS.md),
  as ferramentas do leandro (`discover.py`, `validate.py`, `bench_local.py`,
  `tests/`) são complementares.
- Dedup pendente: dois parsers de gabarito (`crawler/gabarito.py` ×
  `crawler/cebraspe/gabarito.py`) e sobreposição `extract_local.py` ×
  `items.py`/`mc.py`.
- Atualizar AGENTS.md mencionando a tooling do leandro.

## Notas para a imagem Docker

- Base: `python:3.12-slim` + `poppler-utils` — os dois pipelines chamam
  `pdftotext -layout` e `pdftohtml -xml` via subprocess.
- `pip install -r crawler/requirements.txt` (firecrawl-py, pydantic, httpx).
  `pytest` só serve para `crawler/tests/` — candidato a requirements-dev
  separado para emagrecer a imagem.
- `FIRECRAWL_API_KEY` via env em runtime — nunca no build nem na imagem
  (segredo mora em `.env/`).
- Volumes: `data/questions/` + `crawler/jobs/` (o pipeline escreve shards
  por evento — o dataset precisa persistir fora do container),
  `crawler/.cache/` e `crawler/reports/` como scratch.
- Entrypoint provável: `python -m crawler.cebraspe ...` (loop autônomo do
  AGENTS.md) ou `python crawler/run.py` para rodadas por manifesto.

## Execução (2026-11-22)

Estado real divergiu da análise: `crawler-olavo` foi **squashado** a 2
commits pós-base (`5907b11` pipeline+layout + `15b5fd6` 294 shards,
~219k registros) e o monólito `web/src/data/questions.json` deixou de
existir — `web/src/data/questions.ts` é um stub vazio até a API da VM.

- Merge executado: `crawler-merge` @ `423e2cb`. Único conflito =
  **modify/delete** no monólito (leandro modificou → 44 MB/56.135
  registros; olavo deletou). Resolvido mantendo a deleção; o monólito
  do leandro foi preservado em `crawler/.cache/leandro_questions.json`
  (gitignored) e segue acessível via `git show
  origin/crawler-leandro:web/src/data/questions.json`.
- Todo o resto entrou limpo: `run.py`, `discover.py`, `extract_local.py`,
  `validate.py`, `bench_local.py`, `divergencias.py`, `tests/`,
  `manifests/`, `docs/divergencias-pf2025.md` + modificações em
  `.gitignore`, `FIRECRAWL_USAGE.md`, `crawler/requirements.txt` (lado
  olavo não tocou nenhum desses).
- `crawler/models.py` do olavo só mudou docstrings — nenhuma quebra
  para o código do leandro.
- Validação: 81/81 testes de `crawler/tests/` passam no branch
  (instalado com `uv pip install -r crawler/requirements.txt` — o
  `.venv` não tem `pip`).

### Merge de dados (2026-11-22) — executado

Script: `crawler/merge_leandro.py` (`report` classifica, `apply`
reescreve os shards). Reexecutável a partir de `git checkout --
data/questions/`. Relatório de revisão em
`crawler/.cache/merge_review.txt` (gitignored).

Classificação dos 56.135 registros do leandro contra os shards:

- **~24,3k idênticos** (mesmo id + mesmos campos) — ignorados.
- **1.927 colisões de id com diffs** — resolvidas campo a campo
  (enunciado mais longo/íntegro, gabarito/alternativas do leandro só
  quando o registro olavo estava quebrado — 14 casos "olavo-broken").
- **18.526 appends**: cobertura por-vaga (provas compartilhadas
  re-etiquetadas por cargo), gap-fills de itens faltantes, provas
  novas (PC_CE_25_DELEGADO, PC_MG_25_TPAG, ANATEL_24, BDMG_24,
  TRF6_24, TCU_25 etc.) e o evento novo `TJ_SC_22_NOTARIOS` (100
  registros → shard novo).
- **16.540 drops** de taxonomia suplantada: nos eventos de swap, os
  registros olavo sob cargos guarda-chuva caem quando o leandro cobre
  o mesmo item sob cargo mais específico (proteção: não dropa quando o
  leandro cobre o item sob o MESMO cargo normalizado — evita perda por
  fan-out de prova de Conhecimentos Básicos).
- **49 reaplicação TRT8** — ids reescritos para
  `...-tecnico-administrativa-reaplicacao-NNN`, fonte
  `793_TRT8_REAPLICACAO_CB1_01.PDF`, mantidos como registros
  distintos.
- **2 descartados** — registros não-Cebraspe com fonte de homepage
  (FGV IBAMA, FCC TRT15).

Granularidade de cargo aplicada por evento:

- **Swap por vaga** (`SWAP_ALL`, 23 eventos): PM_MA_26, POLC_AL_22,
  TCE_RN_25, TCE_MG_25, TCE_RS_25, CNJ_24, CPNUJE_24, TRT10_24,
  TJ_PA_25_SERVIDOR, TCE_AC_24, ANM_24, ARSAL_26, AGER_MT_23,
  TC_DF_23, TC_DF_24_AUDITOR, BANCO_DO_NORDESTE_22, PM_RO_22,
  PM_SC_23_SOLDADO, CBM_RO_22, CBM_PA_23_CFP, TCE_RJ_22_PROCURADOR,
  TCE_MS_25_CONSELHEIRO. Renames resolvidos por correspondência
  item-a-item (contenção fuzzy de tokens + par dominante com checagem
  mútua — o par dominante sozinho erra quando a prova CB de uma
  especialidade grande supera a prova específica do cargo).
- **Swap parcial**: CBM_MA_26 — só o guarda-chuva "Praça Especialista
  Músico" → 11 vagas; "Praça Combatente" preservado.
- **Labels olavo mantidos** (`KEEP_OLAVO_CARGO` + `CARGO_REMAP`
  explícito): TJ_MT_25_NOTARIOS, TJ_RR_25, TJ_PE_24_NOTARIOS,
  BANRISUL_25 — os labels do leandro ("Provimento"/"Remoção",
  especialidades truncadas) eram menos informativos.
- Leftovers com label antigo permanecem onde o leandro não cobre o
  item (cargos que ele não tem — ex.: AGER "Ciências da Computação",
  ANM "Curso de Formação"/"Correcional") — cobertura preservada.

Resultado: 50 shards alterados, **295 shards / 221.059 registros**
(+1.986 líquido), 0 ids duplicados, referências internas válidas,
round-trip `shard_to_records` OK, 81/81 testes.

### Pendências pós-merge

1. **`crawler/discover.py:42` hardcoda `DATASET =
   web/src/data/questions.json`** — o pipeline do leandro (`run.py`)
   lê e escreve o monólito. Adaptar para ler os shards
   (`load_shard_records`/`shard_to_records`) e escrever via
   `write_shard`, senão `run.py` recria o monólito.
2. Conferir nos PDFs os diffs substantivos flagados em
   `merge_review.txt` (~10 enunciados "kept olavo" + 1 alternativas)
   — os "olavo-broken" já foram corrigidos a partir do leandro.
3. Consolidar parsers duplicados (`crawler/gabarito.py` vs
   `crawler/cebraspe/gabarito.py`; `extract_local.py` vs
   `items.py`/`mc.py`) e documentar o tooling do leandro no AGENTS.md.
