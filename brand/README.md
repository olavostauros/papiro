# papiro — identidade visual

**Miolo** é a identidade do papiro. Os arquivos canônicos estão neste
diretório, com o desenho e a composição exatos da versão adotada.

![Assinatura do papiro](papiro.png)

## Arquivos

| Arquivo | Uso |
| --- | --- |
| [papiro.svg](papiro.svg) | Assinatura oliva para fundos claros |
| [papiro-reverse.svg](papiro-reverse.svg) | Assinatura clara para fundos escuros |
| [papiro-mono.svg](papiro-mono.svg) | Assinatura preta em uma cor |
| [papiro-mark.svg](papiro-mark.svg) | Símbolo oliva |
| [papiro-mark-reverse.svg](papiro-mark-reverse.svg) | Símbolo claro |
| [papiro-mark-mono.svg](papiro-mark-mono.svg) | Símbolo preto em uma cor |
| [papiro.png](papiro.png) | Assinatura transparente, 1200 × 279 px |
| [papiro-mark.png](papiro-mark.png) | Símbolo transparente, 416 × 416 px |

Os SVGs têm fundo transparente, geometria editável, letras em contornos e
nenhuma dependência de fontes ou recursos externos. A cor é definida por
`color` na raiz e aplicada por `currentColor`. Assinatura: `viewBox` de
568 × 132; símbolo: 104 × 104. Preservar a proporção e todo o respiro dessas
caixas. Os PNGs são cópias exatas dos apresentados no estudo.

## Desenho e procedência

Dois planos sólidos com bordas curvas formam um livro aberto. O intervalo
central de 12 unidades mantém a abertura visível em redução. O lettering
geométrico original vem integralmente da proposta
[01 — Nome](studies/2026-11-26/01-nome/papiro.svg), sem substituição por fonte.

A versão adotada aparece na terceira coluna da
[prancha da rodada 03](studies/2026-11-26-round-03-recraft/comparison.png).
Seu símbolo foi desenhado localmente na
[rodada 02](studies/2026-11-26-round-02/03-miolo/papiro.svg) e reapresentado
sem alterações na rodada 03. Nesta adoção foram alterados apenas título e
descrição acessíveis dos SVGs canônicos; toda a geometria, composição e cor
foram preservadas.

| Cor | Hex | Origem |
| --- | --- | --- |
| Oliva | `#2c471c` | Conversão sRGB de `accent` claro / `olive-700` |
| Claro | `#e6ece1` | Conversão sRGB de `ink` escuro |
| Preto | `#000000` | Reprodução monocromática |

As pranchas usam papel `#f4f6ee` e fundo escuro `#0d1609`, derivados dos
respectivos tokens `paper`. Esses fundos não fazem parte dos logos.
O lettering é vetorial próprio, não Source Serif 4. Os rótulos históricos
nas pranchas usam Inter sob SIL OFL 1.1; nenhum arquivo de fonte é distribuído.

## Uso e verificações

As [reduções da rodada 02](studies/2026-11-26-round-02/reductions.png)
mostram Miolo em 16, 24, 32 e 48 px nos fundos claro e escuro. O intervalo
central permanece visível a 16 px nesta renderização. Para a assinatura,
manter mínimo provisório de 160 px de largura e preferir 176 px no cabeçalho.
Manter provisoriamente espaço externo equivalente a metade da altura visível
do `o`. Esses limites vêm da inspeção em tela; não houve teste com usuários,
impressão ou integração real no site.

Foram conferidos XML, caixas, ausência de scripts, eventos, imagens embutidas,
fontes e recursos externos, identidade da geometria com o estudo e PNGs RGBA
transparentes. As pranchas existentes foram inspecionadas em temas claro e
escuro, monocromia e reduções; não foram observados recortes acidentais.

A integração em `web/src/design/components/Logo.astro` e favicons cabe ao
escriba, usando estes arquivos canônicos e respeitando os tamanhos acima.
Os SVGs independentes incluem título e descrição; na integração, o nome
acessível e a eventual redundância com texto devem seguir o contexto.
Nenhuma alteração no site foi feita nesta adoção.

## Histórico

- [Rodada 01](studies/2026-11-26/README.md): exploração original.
- [Rodada 02](studies/2026-11-26-round-02/README.md): origem do símbolo Miolo.
- [Rodada 03 / Recraft](studies/2026-11-26-round-03-recraft/README.md):
  apresentação na qual a opção 03 foi escolhida.
- A primeira proposta de pergaminho foi rejeitada. Ela não é a marca atual.

As pranchas, geradores e registros de execução permanecem como histórico da
exploração e podem conter rótulos de estado anteriores à adoção.
