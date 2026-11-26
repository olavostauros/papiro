# papiro — identidade visual

**Miolo** é a identidade final do papiro. Este diretório contém apenas os
arquivos canônicos da marca, com o desenho e a composição exatos da versão
adotada.

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
caixas. Os PNGs são exportações RGBA transparentes dos SVGs canônicos.

## Desenho e procedência

Dois planos sólidos com bordas curvas formam um livro aberto. O intervalo
central de 12 unidades mantém a abertura visível em redução. O lettering
geométrico é desenho próprio do projeto: pês repetidos, bojos arredondados,
`a` de um andar, ponto quadrado e cortes diagonais nas descendentes. Não é
uma fonte e não foi substituído por uma fonte na composição final.

A geometria Miolo foi desenhada localmente para o papiro e aprovada pelo
usuário em 26/11/2026. Os arquivos finais não incorporam lettering de fonte
de terceiros nem dependem de recursos remotos.

| Cor | Hex | Origem |
| --- | --- | --- |
| Oliva | `#227702` | Conversão sRGB de `accent` claro / `olive-600`, `oklch(0.5 0.16 140)` |
| Claro | `#eaece6` | Conversão sRGB de `ink` escuro, `oklch(0.94 0.008 120)` |
| Preto | `#000000` | Reprodução monocromática |

A cor da marca deriva dos tokens do site e pode ser re-derivada quando eles
mudam; a geometria permanece fixa. O `accent` do tema escuro do site converte
para `#68d54e` (`oklch(0.78 0.2 140)`), mas essa não é uma cor dos ativos
canônicos: em fundos escuros usa-se a versão clara (`reverse`). Medido em
sRGB, o contraste da oliva sobre o papel claro é de 5,3:1 e o do claro sobre
o papel escuro é de 15,4:1.

## Uso

- Usar a assinatura oliva sobre fundos claros e a assinatura reverse sobre
  fundos escuros. As versões mono são destinadas a reprodução em uma cor.
- Preservar proporção, margens internas do `viewBox` e espaço externo ao
  redor da marca. Como regra provisória, reservar espaço externo equivalente
  a metade da altura visível do `o` da assinatura.
- Não aplicar sombras, gradientes, contornos adicionais, fundos ou efeitos
  que não estejam nos arquivos canônicos.
- Não redesenhar o símbolo, não recriar o nome com uma fonte e não extrair
  partes da assinatura para formar outra composição.
- O símbolo pode ser usado isoladamente como favicon, avatar ou marca de
  redução. A assinatura não deve ser reduzida ao tamanho do favicon.

## Tamanhos verificados

O símbolo foi inspecionado em 16, 24, 32 e 48 px nos fundos claro e escuro.
A abertura central permanece distinguível a 16 px como uma faixa clara de
cerca de 2 px, com antisserrilhamento residual esperado nessa rasterização.
Para a assinatura, manter mínimo provisório de 160 px de largura e preferir
176 px em cabeçalhos. Esses limites vêm de inspeção em tela; não houve teste
com usuários, impressão ou dispositivos adicionais.

## Integração no site

A integração usa estes arquivos canônicos como referência:

- `web/src/design/components/Logo.astro` renderiza a assinatura por meio de
  `web/src/design/assets/papiro.svg`, com a mesma geometria e cor herdada do
  contexto;
- `web/public/favicon.svg` usa a geometria do símbolo canônico;
- `web/public/favicon.ico` é o fallback raster transparente em 16, 32 e
  48 px.

Alterações futuras na geometria canônica precisam ser refletidas
deliberadamente nesses assets. Os SVGs independentes incluem título e
descrição; na integração, o nome acessível e a eventual redundância com texto
devem seguir o contexto.

## Verificações

Foram conferidos XML, caixas de exibição, ausência de scripts, eventos,
imagens embutidas, fontes e recursos externos, identidade entre as variantes
e PNGs RGBA transparentes. Também foram verificados os contrastes documentados
acima e a correspondência da geometria usada no site. Não há neste diretório
estudos, pranchas históricas ou artefatos de exploração.
