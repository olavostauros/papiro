# papiro — rodada 02

**Atualização de 26/11/2026:** Miolo foi aprovado pelo usuário como opção 03
na apresentação da rodada 03. Os [arquivos canônicos](../../README.md)
preservam esta geometria. As pranchas e avaliações abaixo registram a fase
exploratória anterior à decisão.

O feedback do usuário
foi melhorar o livro da proposta 02 e manter a tipografia e o lettering 01.
Esta rodada compara somente os símbolos: as seis letras e seus espaçamentos
internos foram preservados integralmente em todas as variantes.

- [Prancha comparativa PNG](comparison.png) · [SVG](comparison.svg)
- [Reduções em tamanho real PNG](reductions.png) · [SVG](reductions.svg)

## Variantes

| Variante | O que mudou no livro | Trade-off observado |
| --- | --- | --- |
| [01 — Margens](01-margens/papiro.svg) | Mantém duas páginas separadas. Molduras de 13 unidades, intervalo central de 14 unidades e proporção mais larga tornam o desenho mais firme que o livro anterior. | A afinidade com o primeiro livro é clara, mas ainda pode parecer duas portas. As aberturas internas estreitas recomendam uso a partir de 24 px. |
| [02 — Lombada](02-lombada/papiro.svg) | Une o livro em um contorno contínuo. Duas contraformas mais largas e bordas curvas se relacionam com os bojos de p, a e o. A lombada tem 12 unidades. | Melhor afinidade com o lettering e leitura de livro mais imediata. É um símbolo figurativo e ainda pertence ao repertório comum de livros abertos. |
| [03 — Miolo](03-miolo/papiro.svg) | Substitui os contornos por dois planos sólidos com bordas curvas. Um intervalo central de 12 unidades constrói a abertura. | É o mais robusto a 16 px, mas pode sugerir asas ou duas bandeiras. Seu peso visual é maior que o dos outros dois. |

**Recomendação histórica do Publicitário, anterior à escolha: 02 — Lombada.** As curvas fazem o símbolo
conversar com o desenho das letras e os vazios são mais amplos que os da
rodada 01. A geometria foi desenhada para este estudo, mas isso não demonstra
exclusividade ou reconhecimento pelo público. O lettering próprio é parte
essencial da diferenciação do conjunto.

## Composição e reduções

O lettering original tem a mesma geometria, proporção e espaçamento da
rodada 01; não houve substituição por uma fonte. O livro aparece com altura
visível de aproximadamente 75 unidades, próxima à altura de 70 unidades
dos bojos. O intervalo até o primeiro pê é de 38 unidades. Essa composição
é a mesma nos três estudos; o centro óptico do livro fica próximo ao eixo
das letras sem acompanhar a profundidade das descendentes.

| Variante | Símbolo recomendado nesta inspeção | Assinatura horizontal |
| --- | --- | --- |
| 01 — Margens | 24 px; a 16 px os miolos ficam frágeis | mínimo provisório de 160 px; preferir 176 px |
| 02 — Lombada | 24 px; reconhecível a 16 px, com curvas comprimidas | mínimo provisório de 160 px; preferir 176 px |
| 03 — Miolo | 16 px; o intervalo central permanece visível | mínimo provisório de 160 px; preferir 176 px |

Foram inspecionadas as duas pranchas renderizadas: símbolos a 16, 24, 32 e
48 px em temas claro/escuro, assinaturas a 160, 176 e 208 px e reprodução
em preto/branco. Não foram observados cortes, cruzamentos ou desalinhamentos
acidentais. O espaço entre símbolo e nome mantém a separação no cabeçalho.
Nenhuma variante óptica especial foi criada; a mesma geometria é reduzida.

Os limites são observações nesta renderização de tela, sem testes adicionais
de impressão, navegadores, dispositivos ou usuários. Inspecionar
`reductions.png` a 100%, pois a reamostragem pode alterar os detalhes.
Preservar todo o `viewBox` e, provisoriamente, deixar ao redor da assinatura
espaço externo equivalente a metade da altura visível do `o`. A folga é uma
regra de composição proposta, sem teste em layouts reais do site.

## Arquivos e materiais

Cada subdiretório contém `papiro.svg` e `mark.svg`, as versões `-reverse`
(cor clara) e `-mono` (preta), mais `papiro.png` e `mark.png` transparentes.
As assinaturas PNG têm 1200 × 279 px; os símbolos, 416 × 416 px.
A prancha mede 1800 × 1500 px e a inspeção 1280 × 1030 px.
As pranchas têm fundo e não são arquivos de logo para produção.

Símbolos: geometria vetorial original desta rodada, definida no gerador.
Lettering: grupo vetorial extraído sem alterações de
`../2026-11-26/01-nome/papiro.svg`. Textos das pranchas: contornos de Inter
Regular, peso 400 e tamanho óptico padrão 14, a partir de
`web/node_modules/@fontsource-variable/inter/files/inter-latin-standard-normal.woff2`.
O pacote tem licença SIL OFL 1.1, lida na rodada anterior; nenhum arquivo de
fonte é distribuído. Os ativos independem de fontes instaladas.

A paleta permanece constante para avaliar as formas: oliva `#2c471c`
(`accent` claro), claro `#e6ece1` (`ink` escuro), papel `#f4f6ee` e fundo
`#0d1609` (tokens `paper` dos dois temas). Preto e branco puros na monocromia.
Usam-se as conversões já documentadas na rodada 01; isso não representa
aprovação final da paleta.

## Reprodução e verificação

```bash
node brand/studies/2026-11-26-round-02/generate.mjs
python3 brand/studies/2026-11-26-round-02/validate.py
```

Ferramentas locais: Node.js, `fontkitten` 1.0.3 já instalado no projeto,
`rsvg-convert`, Python padrão e ImageMagick. Nenhuma dependência nova.
O gerador lê o lettering e o símbolo de referência da rodada 01, sem
reescrevê-los, e usa Inter somente para os rótulos em contornos das pranchas.

A validação estrutural cobre os 20 SVGs: XML, caixas finitas e positivas,
IDs acessíveis únicos, elementos vetoriais permitidos e ausência de scripts,
eventos, imagens, `foreignObject`, referências externas e fontes. Confere
também que os nove SVGs de assinatura preservam o grupo original de letras
e que os seis PNGs de ativos são RGBA. Os PNGs de assinatura têm margens
transparentes em todos os lados.

Os estudos anteriores foram preservados. Nenhuma alteração no site, commit
ou publicação. Após uma decisão de direção, a integração vai ao `escriba`.
