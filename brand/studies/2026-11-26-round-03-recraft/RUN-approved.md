# papiro — rodada 03 / execução autorizada Recraft

Estado: execução parcial. Estudos exploratórios sem aprovação de adoção da marca. O nome deste registro indica autorização de execução, não aprovação dos desenhos.

Início (UTC): 2026-11-26T21:17:41.890Z
Fim das chamadas (UTC): 2026-11-26T21:18:57.729Z

## Resultado

Duas chamadas de geração bem-sucedidas, quatro SVGs originais baixados. A terceira chamada (Miolo) retornou saldo insuficiente; nenhum resultado foi fornecido para essa rota. Nenhuma chamada foi repetida, nenhuma compra foi realizada e nenhuma política foi alterada.

Modelo solicitado em todas as chamadas: `recraftv4_1_pro_vector`. Ferramenta: Recraft MCP `image_to_image`. O serviço aceitou os parâmetros de Margens e Lombada e retornou dois resultados por chamada; não forneceu metadado separado confirmando a versão do modelo.

Parâmetros: `strength=0.4`, `input_style=vector_illustration`, `n=2`; `input_image_url` específico por rota. Cada prompt real contém o bloco completo de contexto em inglês seguido do prompt da rota, conforme `BRIEF.md`. Não houve incompatibilidade de modelo ou parâmetros.

Créditos explicitamente informados: 24 por chamada bem-sucedida, 48 no total das duas. Saldos antes/depois não consultados. A falha de Miolo não informou custo. Não há estimativa monetária.

A referência Margens reutiliza a URL pública registrada em `/tmp/papiro-recraft-attempt02.json`, conforme instrução. Lombada e Miolo foram enviadas nesta execução por `request_upload_url` e `curl PUT`, com `Content-Type: image/png`. URLs de upload temporárias não são registradas.

## Verificação e preservação

Os quatro downloads retornaram MIME `image/svg+xml` e XML com raiz SVG. A inspeção estática não encontrou `script`, atributos de evento, `foreignObject`, imagens embutidas, texto, folhas de estilo, referências `href`/`src` ou valores `url(...)`. Os bytes originais foram preservados, com SHA-256 abaixo. Não houve renderização, avaliação visual, recomposição do lettering ou edição dos SVGs.

Escopo desta execução: apenas `raw/` e este `RUN-approved.md` no acervo, além de arquivos temporários em `/tmp`. `RUN.md` não foi editado.

## 01-margens

Início (UTC): 2026-11-26T21:17:41.890Z
Fim (UTC): 2026-11-26T21:18:03.350Z

Referência local: `brand/studies/2026-11-26-round-03-recraft/references/01-margens.png`
Referência pública: https://img.recraft.ai/qsYqHv7R4ypSpPcTn2gnmMfbaxDbLDI_zZNHISW1208/raw:1/plain/abs://prod/images/75287c78-8cfd-4b23-ac66-cb1dbf1f0dec

Status: sucesso; dois resultados originais.

Resposta textual do serviço:

```text
Generated 2 images.
Credits used: 24.
Original images are saved to:
- https://img.recraft.ai/y5JgA0xfHwL9DhFuPlwe1YQ6BRSFhKR-CyxG8-_OxYE/raw:1/plain/abs://prod/images/15d22079-b2e3-4dad-b615-6dd3d5f2ffa1
- https://img.recraft.ai/uOxpeQAAhPU_ksTqD8_Me5pTfanoVf8w6jUozkyWer8/raw:1/plain/abs://prod/images/544ceea9-8df2-4367-8564-20f9d13b0570
Below you can see lower quality previews of generated images.
```

Prompt completo efetivamente enviado:

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

### 01-margens-a.svg

Arquivo: `raw/01-margens-a.svg`
URL pública original: https://img.recraft.ai/y5JgA0xfHwL9DhFuPlwe1YQ6BRSFhKR-CyxG8-_OxYE/raw:1/plain/abs://prod/images/15d22079-b2e3-4dad-b615-6dd3d5f2ffa1
ID identificável na URL original: `15d22079-b2e3-4dad-b615-6dd3d5f2ffa1`
MIME HTTP: `image/svg+xml`; bytes: 9544; XML SVG válido.
SHA-256: `325fed8ff5797014174c948fc042a6c618f02d445cc3147b8c3ad54e96b337a6`

### 01-margens-b.svg

Arquivo: `raw/01-margens-b.svg`
URL pública original: https://img.recraft.ai/uOxpeQAAhPU_ksTqD8_Me5pTfanoVf8w6jUozkyWer8/raw:1/plain/abs://prod/images/544ceea9-8df2-4367-8564-20f9d13b0570
ID identificável na URL original: `544ceea9-8df2-4367-8564-20f9d13b0570`
MIME HTTP: `image/svg+xml`; bytes: 10409; XML SVG válido.
SHA-256: `9b2a68a098a88c62c8f7ab63476c67164d6476fc9464a03bcd1241c2c68e7f1a`

## 02-lombada

Início (UTC): 2026-11-26T21:18:14.608Z
Fim (UTC): 2026-11-26T21:18:33.944Z

Referência local: `brand/studies/2026-11-26-round-03-recraft/references/02-lombada.png`
Referência pública: https://img.recraft.ai/CWPD0z-rybvxRjRe33W96LDKdEQhqSqgoZ-hnaQv3Tk/raw:1/plain/abs://prod/images/596ac2cb-670d-434b-abe7-eb12c2032c8e

Status: sucesso; dois resultados originais.

Resposta textual do serviço:

```text
Generated 2 images.
Credits used: 24.
Original images are saved to:
- https://img.recraft.ai/3cOkYl1bSmtjf_aju2IafnpoEN0Wq6S43W6Us4E1u5A/raw:1/plain/abs://prod/images/ebe82120-ca2c-42b7-a587-3efc6c8c6c93
- https://img.recraft.ai/0Gt_srJdlvZnstH94Vcxtlof4sno5sP6E_0E8CZgSFw/raw:1/plain/abs://prod/images/4ba4fba5-6430-4431-bf9f-0cb3ebc36314
Below you can see lower quality previews of generated images.
```

Prompt completo efetivamente enviado:

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

### 02-lombada-a.svg

Arquivo: `raw/02-lombada-a.svg`
URL pública original: https://img.recraft.ai/3cOkYl1bSmtjf_aju2IafnpoEN0Wq6S43W6Us4E1u5A/raw:1/plain/abs://prod/images/ebe82120-ca2c-42b7-a587-3efc6c8c6c93
ID identificável na URL original: `ebe82120-ca2c-42b7-a587-3efc6c8c6c93`
MIME HTTP: `image/svg+xml`; bytes: 10706; XML SVG válido.
SHA-256: `d9ee920b155510aa2c3f6bd37ebb268a05a451ea7b81b11bb2158c843eaa835f`

### 02-lombada-b.svg

Arquivo: `raw/02-lombada-b.svg`
URL pública original: https://img.recraft.ai/0Gt_srJdlvZnstH94Vcxtlof4sno5sP6E_0E8CZgSFw/raw:1/plain/abs://prod/images/4ba4fba5-6430-4431-bf9f-0cb3ebc36314
ID identificável na URL original: `4ba4fba5-6430-4431-bf9f-0cb3ebc36314`
MIME HTTP: `image/svg+xml`; bytes: 10805; XML SVG válido.
SHA-256: `4d81193a5c47841e4dedf6a22d4b3446c0ce4959d43602a35438b2091b035ce7`

## 03-miolo

Início (UTC): 2026-11-26T21:18:43.599Z
Fim (UTC): 2026-11-26T21:18:47.514Z

Referência local: `brand/studies/2026-11-26-round-03-recraft/references/03-miolo.png`
Referência pública: https://img.recraft.ai/wLCPLHPB2cMP6tMsrIi1zegW_B36ZVXWBO8bghojGNg/raw:1/plain/abs://prod/images/b2849882-ec0f-4dbd-9279-5d2c24f9db08

Status: falha por saldo insuficiente; zero resultados.

Resposta textual do serviço:

```text
unable to transform image: Not enough credits for this operation. You can list the subscription plans with the subscription_plans tool, and buy a new subscription or a credit pack on https://www.recraft.ai/profile/subscription.
```

Prompt completo efetivamente enviado:

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

Arquivos pendentes, não criados: `raw/03-miolo-a.svg` e `raw/03-miolo-b.svg`. A execução parou após o erro; não houve nova tentativa nem consulta de planos ou compra.
