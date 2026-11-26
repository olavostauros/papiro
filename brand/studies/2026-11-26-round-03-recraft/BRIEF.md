# papiro — rodada 03 / briefing Recraft

**Estado:** briefing de planejamento preservado. A execução posterior gerou
Margens e Lombada; Miolo ficou pendente por saldo insuficiente. Ver
[resultado](README.md) e [registro real](RUN-approved.md).
O pedido é melhorar as escolhas da rodada 02 com o melhor modelo do Recraft
e contexto da marca. As três rotas são preservadas como estudos; não há
aprovação de versão final. Os arquivos anteriores permanecem como referência.

## Contexto em português

O **papiro**, sempre em minúsculas, reúne questões e provas oficiais de
concursos públicos brasileiros. Permite encontrar material por banca, órgão,
cargo, ano e assunto, resolver questões, conferir o gabarito definitivo e
consultar o PDF oficial, gratuitamente e sem cadastro. A identidade deve
servir a quem estuda, com clareza, confiança e acesso ao conhecimento. Não há
pesquisa de público que autorize inventar idade, renda, região ou preferências.

A voz é sóbria e direta. A marca não precisa explicar todas as funções;
o livro aberto concentra a ideia de acesso ao estudo. A ligação com provas
oficiais depende também do contexto do produto. Não sugerir um órgão público,
certificação, garantia de aprovação ou selo oficial.

A primeira tentativa, um pergaminho formando um pê, foi rejeitada. Na rodada
01 foram explorados três caminhos. O usuário depois pediu para melhorar o
livro da proposta 02 e manter a tipografia e o lettering da proposta 01.
A rodada 02 resultou em **Margens, Lombada e Miolo**, todas acompanhadas do
mesmo lettering geométrico original. Esta rodada refina esses três livros.

O lettering é geometria própria, não uma fonte comercial: pês repetidos,
bojos arredondados, a de um andar, ponto quadrado e cortes diagonais nas
descendentes. A anatomia, o espaçamento e a proporção das seis letras devem
permanecer exatos. O master é
[`../2026-11-26/01-nome/papiro.svg`](../2026-11-26/01-nome/papiro.svg).
O lettering será recomposto localmente a partir desse grupo vetorial;
**a geração deve produzir apenas o símbolo**, evitando redesenhar o nome.

Paleta constante para comparação: oliva `#2c471c`, claro `#e6ece1`, papel
`#f4f6ee` e fundo escuro `#0d1609`, derivados dos tokens do site. A paleta
não é uma decisão final aprovada. O símbolo deve funcionar em uma única cor,
sem depender de sombras, gradientes ou fundo.

## Referências visuais a fornecer

| Referência | Finalidade |
| --- | --- |
| [`../2026-11-26-round-02/comparison.png`](../2026-11-26-round-02/comparison.png) | Contexto do conjunto; informar que rótulos e composição da prancha não pertencem ao símbolo |
| [`../2026-11-26-round-02/01-margens/mark.png`](../2026-11-26-round-02/01-margens/mark.png) | Referência da chamada Margens |
| [`../2026-11-26-round-02/02-lombada/mark.png`](../2026-11-26-round-02/02-lombada/mark.png) | Referência da chamada Lombada |
| [`../2026-11-26-round-02/03-miolo/mark.png`](../2026-11-26-round-02/03-miolo/mark.png) | Referência da chamada Miolo |
| [`../2026-11-26-round-02/reductions.png`](../2026-11-26-round-02/reductions.png) | Avaliação local de redução; não pedir ao gerador que reproduza a prancha |

Para cada chamada, fornecer prioritariamente o símbolo correspondente e a
assinatura dessa mesma rota como contexto, se a ferramenta aceitar imagens
de referência. Não tratar uma imagem como anexada sem confirmação da chamada.
Se o modelo aceitar somente texto, registrar essa limitação e usar a
descrição geométrica de cada rota abaixo. Não colocar credenciais no prompt.

## Seleção de modelo e formato

O identificador exato do modelo deve vir das ferramentas/documentação
autenticadas do Recraft disponíveis na execução. A descoberta autenticada
`suggest_model` recomendou `recraftv4_1_pro_vector` (Recraft V4.1 Vector Pro)
para logo SVG com referência; esse é o modelo selecionado para a execução.
A referência oficial é a
[documentação V4.1](https://www.recraft.ai/docs/recraft-models/recraft-v4-1.md).
Para esta tarefa, priorizar
o modelo de maior qualidade que produza **vetor editável** e aceite os
recursos de referência necessários. Não presumir que o melhor modelo raster
é o melhor para um logo SVG. Se nenhum modelo vetorial aceitar referências,
registrar a escolha e o motivo, preservando o master das letras localmente.

Registrar em `RUN.md`, após executar: modelo e versão exatos; ferramenta;
data; prompt completo; referências realmente enviadas; parâmetros de saída;
IDs e URLs de resultado; créditos/custo apenas quando informados pelo serviço;
arquivos baixados e alterações locais. Nunca registrar tokens OAuth.

Executar uma chamada por rota, com duas alternativas (`n=2`) por chamada,
totalizando seis SVGs. Usar `image_to_image`, força entre 0,35 e 0,45 e
`input_style=vector_illustration`, conforme o contrato confirmado do MCP.
Uma nova iteração deve responder a um problema observado, com o novo prompt documentado.
Preservar o original recebido e distinguir eventuais ajustes locais.

## Context block — English

Prepend this block to each route prompt. Use a single route per generation.

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
```

## 01 — Margens / angular open pages

**O que aparece hoje:** dois quadriláteros vazados espelhados, separados por
uma fenda vertical. Arestas externas verticais; bordas superiores e inferiores
inclinadas. No SVG de 104 unidades, os planos ocupam x=8–45 e x=59–96,
com vão central de 14; as contraformas têm cerca de 11 unidades de largura.

**Refinamento:** abrir os miolos sem enfraquecer os contornos, reduzir a
sensação de duas portas independentes e reforçar a dobra central do livro
pela relação entre bordas. Manter a precisão angular que conversa com os
cortes dos pês. Não migrar para o contorno curvo de Lombada.

```text
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

## 02 — Lombada / continuous open book

**O que aparece hoje:** um contorno de livro contínuo, duas contraformas
arredondadas e espelhadas, junção central maciça. No SVG de 104 unidades,
a lombada tem 12 unidades entre x=46 e x=58. As bordas superiores descem ao
centro e as inferiores formam um encontro central pronunciado.

**Refinamento:** simplificar a quantidade de inflexões, regularizar a
espessura aparente das curvas e aliviar a ponta inferior central. Dar
respiração às contraformas sem fragilizar a lombada. Preservar a leitura
imediata de livro e a afinidade dos bojos com as letras; evitar a leitura
isolada de M ou escudo. É a rota mais promissora na recomendação anterior,
mas essa preferência é avaliação do Publicitário, não escolha do usuário.

```text
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

## 03 — Miolo / solid facing pages

**O que aparece hoje:** dois planos sólidos separados por uma fenda vertical
de 12 unidades, de x=46 a x=58. As bordas de topo curvam-se para o centro;
as inferiores repetem essa curvatura. O símbolo é robusto, mas o peso escuro
e as pontas internas podem sugerir asas ou bandeiras.

**Refinamento:** conter a expansão lateral e a subida das extremidades,
equilibrar a massa com o lettering e tornar a relação entre páginas e dobra
mais legível. Preservar os dois planos sólidos e o vão aberto a 16 px;
não transformar a rota num contorno vazado.

```text
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

## Continuidade e composição local

1. Preservar os resultados brutos e tratar toda saída como estudo.
2. Inspecionar SVG antes de renderizar: sem scripts, eventos,
   `foreignObject`, recursos remotos, imagens embutidas ou dependência de
   fontes. Se a saída for raster, identificá-la como raster; não renomear
   PNG como SVG nem embutir bitmap para simular master vetorial.
3. Recompor cada novo símbolo com o grupo exato das letras da rodada 01.
   Comparar o grupo com o original, incluindo caminhos e transformações
   internas. Não usar a reinterpretação tipográfica de um modelo.
4. Partir da composição da rodada 02: altura do livro perto da altura
   dos bojos; centro óptico próximo ao eixo das letras, sem acompanhar a
   profundidade dos pês. Ajustar escala e intervalo externo por aparência,
   mantendo igual critério entre rotas. Documentar valores efetivos.
5. Apresentar cada versão ao lado da respectiva anterior, com a mesma
   área de exibição e mesma paleta. Renderizar símbolo isolado, assinatura,
   preto/branco, positivo/negativo e 16, 24, 32 e 48 px. Inspecionar também
   assinaturas de 160, 176 e 208 px sem ampliar artificialmente.

## Critérios de avaliação

| Critério | Evidência a observar |
| --- | --- |
| Continuidade | A rota original permanece identificável e o lettering é exato |
| Leitura | O livro é reconhecível antes da explicação; registrar associações alternativas |
| Redução | Aberturas continuam abertas e massas não se fundem em 16–48 px |
| Equilíbrio | O símbolo não domina as letras nem parece leve demais |
| Geometria | Curvas limpas, espessuras aparentes coerentes, sem recortes |
| Uma cor | Mesma estrutura funciona em preto e reverso, sem efeitos |
| Vetor | Saída editável verdadeira, sem raster embutido ou recursos externos |

As observações são inspeção visual, não pesquisa com concurseiros ou prova
de exclusividade. Não declarar que houve melhoria só porque o modelo é mais
recente; comparar os resultados com as referências.

## Fontes internas e responsabilidade

Briefing derivado de [`../../PUBLIC.md`](../../PUBLIC.md),
[`../../SEMI-OPTICS.md`](../../SEMI-OPTICS.md),
[`../../README.md`](../../README.md) e
[`../2026-11-26-round-02/README.md`](../2026-11-26-round-02/README.md).
Pranchas e os três SVGs de símbolo da rodada 02 foram inspecionados durante
a preparação. Nenhuma geração, nova validação de SVG ou alteração de logo
foi realizada nesta etapa. Integração em `web/` pertence ao escriba após
adoção; este estudo permanece em `brand/`.
