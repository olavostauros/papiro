# Divergências PF 2025: dataset × PDF oficial

Gerado em 2026-11-21 por `python -m crawler.divergencias` a partir do benchmark do extrator local (`crawler/bench_local.py`). Nenhum registro do dataset foi alterado.

**Critério:** o trecho do dataset **não existe** no texto do PDF oficial (`pdftotext`) e o trecho correspondente do PDF existe. Casos marcados como “conferido manualmente” não passaram nesse critério automático e foram verificados à mão no PDF.

**Coluna “muda o sentido?” (heurística, revisar):** *sim* quando a diferença envolve negação (não/nem/sem…) ou número; *possível* quando a palavra do dataset é uma palavra real (aparece em ≥ 3 registros do dataset) trocada por outra; *não (grafia)* quando a palavra do dataset não aparece em outros registros — provável erro de digitação.

**Total:** 65 itens — não: 48, possível: 16, sim: 1 (mais 8 só de notação, listados ao final). Como os cadernos de conhecimentos básicos são compartilhados por vários cargos, cada item pode corresponder a mais de um registro (coluna *registros*).

## Destaque

- **106_PF_005_01 item 108** (`cebraspe-2025-pf-perito-geologia-108`, gabarito no dataset: **certo**): o dataset diz “de obra especializada e”, o PDF diz “de obra não especializada e”. **SIM** (negação) — conferido manualmente.

## Todos os itens

| prova | item | texto no dataset | texto no PDF | muda o sentido? | registros | exemplo de id |
|---|---:|---|---|---|---:|---|
| 106_PF_CG1_01 | 65 | (a primeira defina a rede | (a primeira define a rede | possível (palavra trocada por outra) | 3 | `cebraspe-2025-pf-escrivao-065` |
| 106_PF_CG1_01 | 70 | e velocidade características desse ambiente. | e velocidade característicos desse ambiente. | possível (palavra trocada por outra) | 3 | `cebraspe-2025-pf-escrivao-070` |
| 106_PF_CG1_01 | 74 | de sistemas biómetricos ao se | de sistemas biométricos ao se | não (grafia) | 3 | `cebraspe-2025-pf-escrivao-074` |
| 106_PF_CG1_01 | 86 | multifator (MFA), hardware tokens equivalem | multifator (MFA), hardwares tokens equivalem | possível (palavra trocada por outra) | 3 | `cebraspe-2025-pf-escrivao-086` |
| 106_PF_CG1_01 | 96 | necessária a completou oriunda de | necessária a completude oriunda de | possível (palavra trocada por outra) | 3 | `cebraspe-2025-pf-escrivao-096` |
| 106_PF_001_01 | 16 | Considera que uma | Considere que uma | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-delegado-016` |
| 106_PF_001_01 | 25 | diz respeito à direitos e | diz respeito a direitos e | não (grafia) | 1 | `cebraspe-2025-pf-delegado-025` |
| 106_PF_001_01 | 26 | refugiados despesas físicas, a exemplo | refugiados despesas fiscais, a exemplo | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-delegado-026` |
| 106_PF_001_01 | 28 | direito de pleitar, perante os | direito de pleitear, perante os | não (grafia) | 1 | `cebraspe-2025-pf-delegado-028` |
| 106_PF_001_01 | 29 | de proteção e cuja aplicabilidade | de proteção a cuja aplicabilidade | não (grafia) | 1 | `cebraspe-2025-pf-delegado-029` |
| 106_PF_001_01 | 59 | casos de hometransfobia os tipos | casos de homotransfobia os tipos | não (grafia) | 1 | `cebraspe-2025-pf-delegado-059` |
| 106_PF_001_01 | 70 | Considerando que Marcelino, … ação policial. Considerando, ainda, que, | Considere que Marcelino, … ação policial. Considere, ainda, que, | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-delegado-070` |
| 106_PF_001_01 | 89 | de prejuízo concorreto. | de prejuízo concreto. | não (grafia) | 1 | `cebraspe-2025-pf-delegado-089` |
| 106_PF_001_01 | 118 | O principio da responsabilidade | A CF consagra o princípio da responsabilidade | não (grafia) | 1 | `cebraspe-2025-pf-delegado-118` |
| 106_PF_002_01 | 62 | causado ao errário. | causado ao erário. | não (grafia) | 1 | `cebraspe-2025-pf-perito-contabil-062` |
| 106_PF_002_01 | 63 | de repasse relativa à transferência | de repasse relativo à transferência | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-contabil-063` |
| 106_PF_002_01 | 69 | de obter os assegurar vantagem | de obter ou assegurar vantagem | não (grafia) | 1 | `cebraspe-2025-pf-perito-contabil-069` |
| 106_PF_003_01 | 70 | a decisão d_j é tomada … a hipótese h_i, busca-se minimizar … decidindo-se por d_j se, dado … condicional de h_i ser verdadeira … condicional de h_k ser verdadeira, … para k ≠ i. | a decisão dj é tomada … a hipótese hi, busca-se minimizar … decidindo-se por dj se, dado … condicional de hi ser verdadeira … condicional de hk ser verdadeira, … para k i. | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-eletrica-070` |
| 106_PF_003_01 | 80 | Quanto mais à área sob | Quanto mais a área sob | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-eletrica-080` |
| 106_PF_003_01 | 87 | a frequência coossenoidal da portadora; | a frequência cossenoidal da portadora; | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-eletrica-087` |
| 106_PF_003_01 | 114 | como o gradientado descendente e | como o gradiente descendente e | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-eletrica-114` |
| 106_PF_005_01 | 51 | de formações ferriferas bandadas. | de formações ferríferas bandadas. | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-051` |
| 106_PF_005_01 | 53 | de espectroscopia Môssbauer, é possível | de espectroscopia Mössbauer, é possível | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-053` |
| 106_PF_005_01 | 56 | Os derrames basalticos da Formação | Os derrames basálticos da Formação | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-056` |
| 106_PF_005_01 | 60 | microfósseis e incofósseis. | microfósseis e icnofósseis. | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-060` |
| 106_PF_005_01 | 72 | A geoostatística pode ser | A geoestatística pode ser | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-072` |
| 106_PF_005_01 | 85 | de imagens bidimensionalais da superfície | de imagens bidimensionais da superfície | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-085` |
| 106_PF_005_01 | 93 | sistema de fluorescentência de raios | sistema de fluorescência de raios | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-093` |
| 106_PF_005_01 | 102 | na fácies anfíbolito, com pacote … com níveis manganésíferos e quartzitos. | na fácies anfibolito, com pacote … com níveis manganesíferos e quartzitos. | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-102` |
| **106_PF_005_01** | **108** | de obra especializada e | de obra não especializada e | **SIM** (negação) — conferido manualmente | 1 | `cebraspe-2025-pf-perito-geologia-108` |
| 106_PF_005_01 | 114 | o agente dolorosamente deixar de | o agente dolosamente deixar de | não (grafia) | 1 | `cebraspe-2025-pf-perito-geologia-114` |
| 106_PF_006_01 | 69 | deve ser limitad a subclasse ARCO | deve ser limitada à subclasse ARCO | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-civil-069` |
| 106_PF_006_01 | 80 | que o gradiento de velocidade | que o gradiente de velocidade | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-civil-080` |
| 106_PF_006_01 | 82 | para o gradiento de velocidade | para o gradiente de velocidade | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-civil-082` |
| 106_PF_006_01 | 103 | em uma história de entrega | em uma vistoria de entrega | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-eng-civil-103` |
| 106_PF_006_01 | 105 | Uma história pode ser … de causas (ou) soluções. | Uma vistoria pode ser … de causas e(ou) soluções. | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-eng-civil-105` |
| 106_PF_006_01 | 106 | avaliação deve, complementamente, identificar e | avaliação deve, complementarmente, identificar e | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-civil-106` |
| 106_PF_007_01 | 83 | Ortretificação é o … das distorções decorretas da geometria … geometria de imagemato e do | Ortorretificação é o … das distorções decorrentes da geometria … geometria de imageamento e do | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-cartografica-083` |
| 106_PF_007_01 | 89 | de reflectância característica, com baixa | de reflectância característico, com baixa | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-eng-cartografica-089` |
| 106_PF_007_01 | 91 | do infravermelho terminal. | do infravermelho termal. | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-eng-cartografica-091` |
| 106_PF_007_01 | 96 | equalização de histogram, os valores | equalização de histograma, os valores | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-cartografica-096` |
| 106_PF_007_01 | 100 | a base cartográfica, vetorial é | a base cartográfica vetorial é | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-cartografica-100` |
| 106_PF_007_01 | 103 | mercado para afecção do valor | mercado para aferição do valor | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-cartografica-103` |
| 106_PF_008_01 | 55 | vontade da vitima. | vontade da vítima. | não (grafia) | 1 | `cebraspe-2025-pf-perito-medicina-legal-055` |
| 106_PF_008_01 | 105 | A prodigialidade, condição elencada | A prodigalidade, condição elencada | não (grafia) | 1 | `cebraspe-2025-pf-perito-medicina-legal-105` |
| 106_PF_008_01 | 113 | transtornos mentais refratórios a tratamento | transtornos mentais refratários a tratamento | não (grafia) | 1 | `cebraspe-2025-pf-perito-medicina-legal-113` |
| 106_PF_009_01 | 63 | proporcional a v 2, em que … em que v é a … da velocidade 0 0 inicial. | proporcional a v02, em que … em que v0 é a … da velocidade inicial. | não (grafia) | 1 | `cebraspe-2025-pf-perito-fisica-063` |
| 106_PF_010_01 | 72 | tipo com realizes autoportantes, em | tipo com realces autoportantes, em | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-minas-072` |
| 106_PF_010_01 | 78 | dos elementos via em função | dos elementos pode variar em função | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-eng-minas-078` |
| 106_PF_010_01 | 87 | Paracatu e Araxão, no estado | Paracatu e Araxá, no estado | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-minas-087` |
| 106_PF_010_01 | 90 | pode apresentar ocorrência de ouro | pode apresentar ocorrências de ouro | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-eng-minas-090` |
| 106_PF_010_01 | 91 | a zonas silificadas. | a zonas silicificadas. | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-minas-091` |
| 106_PF_010_01 | 97 | O aquífero Uruquia, de idade | O aquífero Urucuia, de idade | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-minas-097` |
| 106_PF_010_01 | 100 | áreas com predominio de solos | áreas com predomínio de solos | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-minas-100` |
| 106_PF_010_01 | 101 | como balanço hidrico e flutuadores. | como balanço hídrico e flutuadores. | não (grafia) | 1 | `cebraspe-2025-pf-perito-eng-minas-101` |
| 106_PF_010_01 | 114 | penalidade de muita simples em | penalidade de multa simples em | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-eng-minas-114` |
| 106_PF_013_01 | 55 | um traço morfoscópio relevante para | um traço morfoscópico relevante para | não (grafia) | 1 | `cebraspe-2025-pf-perito-antropologia-055` |
| 106_PF_013_01 | 56 | endócrinas e hematopoietic. | endócrinas e hematopoiéticas. | não (grafia) | 1 | `cebraspe-2025-pf-perito-antropologia-056` |
| 106_PF_013_01 | 59 | de fusão epifissária e desenvolvimento | de fusão epifisária e desenvolvimento | não (grafia) | 1 | `cebraspe-2025-pf-perito-antropologia-059` |
| 106_PF_013_01 | 61 | cartilaginoso nas epifises dos ossos | cartilaginoso nas epífises dos ossos | não (grafia) | 1 | `cebraspe-2025-pf-perito-antropologia-061` |
| 106_PF_013_01 | 99 | a junção cimento-esmalte e a | a junção cemento-esmalte e a | possível (palavra trocada por outra) | 1 | `cebraspe-2025-pf-perito-antropologia-099` |
| 106_PF_014_01 | 66 | outros seres autótofos fotossintetizadores formam | outros seres autótrofos fotossintetizadores formam | não (grafia) | 1 | `cebraspe-2025-pf-perito-meio-ambiente-066` |
| 106_PF_014_01 | 70 | uma floresta ombrofílla densa, uma | uma floresta ombrófila densa, uma | não (grafia) | 1 | `cebraspe-2025-pf-perito-meio-ambiente-070` |
| 106_PF_014_01 | 71 | menores áreas baseais e maiores | menores áreas basais e maiores | não (grafia) | 1 | `cebraspe-2025-pf-perito-meio-ambiente-071` |
| 106_PF_015_01 | 110 | A Lei n.º 6.404/1976 aplica-se | A Lei n.o 6.404/1976 aplica-se | não (grafia) | 1 | `cebraspe-2025-pf-escrivao-110` |

*Fora da tabela:* 8 item(ns) em que a diferença é só de notação (subscrito/expoente escrito com `_`/`^` no dataset): 106_PF_017_01 item 115, 106_PF_001_01 item 105, 106_PF_003_01 item 85, 106_PF_003_01 item 107, 106_PF_003_01 item 112, 106_PF_006_01 item 74, 106_PF_010_01 item 62, 106_PF_010_01 item 64.
