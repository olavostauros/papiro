# Rodada 03 — registro de execução Recraft

**Estado:** execução bloqueada no upload; nenhuma geração realizada. Todas as propostas deste briefing são explorações não aprovadas.

- Data/hora: 2026-11-26T18:15:22-03:00.
- Serviço: MCP Recraft autenticado; ferramentas consultadas: `get_user` e `request_upload_url`.
- Modelo solicitado: `recraftv4_1_pro_vector`. Nenhum modelo chegou a ser executado.
- Gerações bem-sucedidas: **0 de 3**. Chamadas a `image_to_image`: **0**.
- SVGs recebidos, baixados ou validados: **0 de 6**.
- Créditos antes: saldo numérico não obtido.
- Créditos depois: não consultados; nenhuma chamada de geração foi iniciada.
- Custo: não informado; nenhum valor estimado.

## Bloqueio observado

O MCP forneceu um endpoint de upload. O envio da referência Margens por `curl`, método PUT e `Content-Type: image/png`, falhou por resolução de nome (código de saída 6). Uma segunda tentativa apenas do upload confirmou o mesmo erro. Nenhuma dessas tentativas chamou geração. O ambiente permite acesso de rede restrito e não permite elevação de permissões.

Não houve resposta de upload contendo `image_url`; nenhuma referência foi entregue com sucesso ao gerador. URLs assinadas, tokens, dados pessoais e respostas de perfil foram omitidos deste registro. Não houve timeout de geração, repetição de geração, troca de modelo, compra, upgrade, commit, renderização ou alteração dos originais.

As três referências locais foram verificadas como PNG com dimensão de 1024 px. Os destinos esperados estavam livres. Para completar a execução, será necessário um ambiente em que o PUT ao endpoint fornecido pelo MCP possa resolver o nome e alcançar o serviço.

## Parâmetros preparados, não executados

- Ferramenta de geração: `image_to_image`.
- `model="recraftv4_1_pro_vector"`.
- `strength=0.4`.
- `n=2` por rota.
- `input_style="vector_illustration"`.
- `input_image_url`: indisponível, pois o upload falhou.
- Uma chamada bem-sucedida por rota; máximo total de três. Não houve adaptação de parâmetros.

## 01-margens

- Referência local: `brand/studies/2026-11-26-round-03-recraft/references/01-margens.png`.
- Estado do upload: falhou por resolução de nome, duas tentativas de PUT.
- `image_url` pública da referência: indisponível.
- Geração: não chamada.
- IDs e URLs de saída: indisponíveis.
- Destinos previstos, **não criados**: `raw/01-margens-a.svg` e `raw/01-margens-b.svg`.
- MIME, XML e sucesso do download: não verificáveis, sem saída recebida.

Prompt completo preparado (contexto compartilhado seguido da rota):

```text
You are refining an existing visual identity for papiro, a free Brazilian
public-service examination study archive. It brings together official past
exam questions, definitive answer keys and links to the source PDFs. People
can find and practise questions without a subscription or an account. The
brand should feel clear, calm, trustworthy, accessible and useful to someone
studying. This is a study service, not a government institution or a school
promising success. The central visual idea for this refinement is open access
to study through an open book.

Refine the specific round-02 symbol described below. Preserve its conceptual
family and recognisable silhouette while improving optical balance and small
size performance. Our existing wordmark is custom lowercase geometric
lettering: rounded p/a/o bowls, a single-storey a, a square i dot, and diagonal
cuts in the two p descenders. The original six letters will be added back
from their exact vector paths after generation. Generate the SYMBOL ONLY,
without text, letters, labels, captions or a new wordmark. The book should
visually belong beside that rounded geometric lettering.

Deliver one considered flat vector symbol, centred with generous clear space,
using a single solid dark olive colour #2c471c on a transparent background
when the output supports it. It must also work in pure black and reversed
white. Use a compact, visually balanced construction, few purposeful paths,
clean contours and generous negative space. Design for recognition at 24px
and evaluate whether the structure can survive 16px; do not fake a pixel test.
No shading, gradients, texture, shadows, bevels, 3D, perspective mockups,
decorative page lines, tiny details, pencils, graduation caps, checkmarks,
laurels, shields, official seals, literal papyrus scrolls or app-icon tiles.
Do not output a collage, contact sheet or multiple alternatives in one image.

ROUTE 01 — MARGENS / ANGULAR OPEN PAGES
The reference is a pair of mirrored angular page frames. Each page is a
hollow quadrilateral with a vertical outer edge and slanted top and bottom
edges; the two pages are separated by a clear central vertical opening.
Keep the two independent outlined page shapes and their angular rhythm.
Refine this into a more convincing open book with more generous, balanced
interior apertures. Improve the relationship between the inner edges so the
pair reads together as facing pages, rather than as two disconnected doors.
Keep the geometry simple and almost symmetrical, with intentional diagonal
edge relationships that echo the diagonal cuts in our wordmark. Explore a
slightly broader and calmer proportion, with an opening that remains clear
at small sizes. Avoid tall narrow window-like holes. Keep the pages hollow;
do not turn this route into solid leaves or a soft curved book outline.
```

## 02-lombada

- Referência local: `brand/studies/2026-11-26-round-03-recraft/references/02-lombada.png`.
- Estado do upload: não iniciado após o bloqueio da primeira rota.
- `image_url` pública da referência: indisponível.
- Geração: não chamada.
- IDs e URLs de saída: indisponíveis.
- Destinos previstos, **não criados**: `raw/02-lombada-a.svg` e `raw/02-lombada-b.svg`.
- MIME, XML e sucesso do download: não verificáveis, sem saída recebida.

Prompt completo preparado (contexto compartilhado seguido da rota):

```text
You are refining an existing visual identity for papiro, a free Brazilian
public-service examination study archive. It brings together official past
exam questions, definitive answer keys and links to the source PDFs. People
can find and practise questions without a subscription or an account. The
brand should feel clear, calm, trustworthy, accessible and useful to someone
studying. This is a study service, not a government institution or a school
promising success. The central visual idea for this refinement is open access
to study through an open book.

Refine the specific round-02 symbol described below. Preserve its conceptual
family and recognisable silhouette while improving optical balance and small
size performance. Our existing wordmark is custom lowercase geometric
lettering: rounded p/a/o bowls, a single-storey a, a square i dot, and diagonal
cuts in the two p descenders. The original six letters will be added back
from their exact vector paths after generation. Generate the SYMBOL ONLY,
without text, letters, labels, captions or a new wordmark. The book should
visually belong beside that rounded geometric lettering.

Deliver one considered flat vector symbol, centred with generous clear space,
using a single solid dark olive colour #2c471c on a transparent background
when the output supports it. It must also work in pure black and reversed
white. Use a compact, visually balanced construction, few purposeful paths,
clean contours and generous negative space. Design for recognition at 24px
and evaluate whether the structure can survive 16px; do not fake a pixel test.
No shading, gradients, texture, shadows, bevels, 3D, perspective mockups,
decorative page lines, tiny details, pencils, graduation caps, checkmarks,
laurels, shields, official seals, literal papyrus scrolls or app-icon tiles.
Do not output a collage, contact sheet or multiple alternatives in one image.

ROUTE 02 — LOMBADA / CONTINUOUS OPEN BOOK
The reference is one continuous open-book silhouette with two generous
mirrored hollow page interiors and a solid central spine. Its top page
edges curve gently down towards the middle; its lower edges join at the
central fold. Keep this exact conceptual family: one connected outlined
book, two clear apertures, one stable central spine.
Refine the curvature into fewer, calmer transitions that relate to the round
p/a/o bowls of the existing geometric wordmark. Balance apparent thickness
on the curved top edges, vertical sides, lower edges and centre. Open the
interior spaces and soften the overly pointed lower central meeting without
adding small details. Keep the book broad, grounded and optically centred.
The result should read first as an open book, with less resemblance to a
letter M, a shield or a decorative crest. No stacked pages, extra outlines,
thin interior strokes or isolated flying leaves.
```

## 03-miolo

- Referência local: `brand/studies/2026-11-26-round-03-recraft/references/03-miolo.png`.
- Estado do upload: não iniciado após o bloqueio da primeira rota.
- `image_url` pública da referência: indisponível.
- Geração: não chamada.
- IDs e URLs de saída: indisponíveis.
- Destinos previstos, **não criados**: `raw/03-miolo-a.svg` e `raw/03-miolo-b.svg`.
- MIME, XML e sucesso do download: não verificáveis, sem saída recebida.

Prompt completo preparado (contexto compartilhado seguido da rota):

```text
You are refining an existing visual identity for papiro, a free Brazilian
public-service examination study archive. It brings together official past
exam questions, definitive answer keys and links to the source PDFs. People
can find and practise questions without a subscription or an account. The
brand should feel clear, calm, trustworthy, accessible and useful to someone
studying. This is a study service, not a government institution or a school
promising success. The central visual idea for this refinement is open access
to study through an open book.

Refine the specific round-02 symbol described below. Preserve its conceptual
family and recognisable silhouette while improving optical balance and small
size performance. Our existing wordmark is custom lowercase geometric
lettering: rounded p/a/o bowls, a single-storey a, a square i dot, and diagonal
cuts in the two p descenders. The original six letters will be added back
from their exact vector paths after generation. Generate the SYMBOL ONLY,
without text, letters, labels, captions or a new wordmark. The book should
visually belong beside that rounded geometric lettering.

Deliver one considered flat vector symbol, centred with generous clear space,
using a single solid dark olive colour #2c471c on a transparent background
when the output supports it. It must also work in pure black and reversed
white. Use a compact, visually balanced construction, few purposeful paths,
clean contours and generous negative space. Design for recognition at 24px
and evaluate whether the structure can survive 16px; do not fake a pixel test.
No shading, gradients, texture, shadows, bevels, 3D, perspective mockups,
decorative page lines, tiny details, pencils, graduation caps, checkmarks,
laurels, shields, official seals, literal papyrus scrolls or app-icon tiles.
Do not output a collage, contact sheet or multiple alternatives in one image.

ROUTE 03 — MIOLO / SOLID FACING PAGES
The reference has two solid mirrored book-page shapes divided by a vertical
negative-space opening. Each page has a straight outer side and a gently
curved top and bottom edge leading towards the central fold. There are no
interior holes or page lines. Preserve the bold two-solid-page construction
and its clear open centre.
Refine the silhouette to read more confidently as the facing pages of an
open book, with less resemblance to spreading wings, flags or a butterfly.
Make the proportions calmer and visually less heavy beside our rounded
geometric wordmark. Keep the outer page ends restrained rather than flared;
make the central relationship intentional, with a generous continuous open
fold that survives reduction. Use broad simple curves, a stable vertical
structure and balanced solid areas. Do not add an outline, holes, extra
leaves or fine page strokes. Retain the strength of the original silhouette
while bringing it closer in visual weight to the other two routes.
```
