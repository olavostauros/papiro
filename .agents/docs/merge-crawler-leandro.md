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
