# papiro — três estudos, exploração 01

Estado: **exploratórios, sem direção aprovada**. A autorização foi explorar os
três caminhos do planejamento. Os arquivos anteriores em `brand/` foram
preservados; a proposta rejeitada não foi utilizada como identidade aprovada.

Começar por [comparison.png](comparison.png). A prancha SVG é
[comparison.svg](comparison.svg), totalmente vetorial, incluindo os textos.
[reductions.png](reductions.png) permite inspecionar as reduções a 100%.

## Os três caminhos

| Estudo | Hipótese e construção | Leituras alternativas / limite |
| --- | --- | --- |
| [01 — Nome como marca](01-nome/papiro.svg) | O nome sustenta a identidade. Lettering geométrico original: a de um andar, pês repetidos, ponto quadrado e corte diagonal nas duas descendentes. O símbolo é o primeiro pê do nome. | A forma é direta, mas o pê isolado é genérico; o caráter próprio reside principalmente na assinatura. O desenho não comunica sozinho provas oficiais ou gratuidade. |
| [02 — Acervo aberto](02-acervo/papiro.svg) | Dois planos inclinados, separados por um intervalo, sugerem acesso à leitura. O nome em Source Serif 4 Italic oferece uma presença editorial e contrasta com o símbolo rígido. | Pode ser entendido como livro aberto, janelas ou duas portas. O vínculo com concursos depende do contexto. A 16 px, os planos e vazios ficam delicados; a recomendação para o símbolo começa em 24 px. |
| [03 — Pê como estrutura](03-estrutura/papiro.svg) | Um pê maciço construído com planos e chanfros de 45°, repetidos na contraforma. Inter Regular acompanha a estrutura com um nome de leitura simples. | O símbolo parece P maiúsculo angular e pode lembrar marca esportiva ou tecnológica; a ligação com uma dobra de papel é hipótese, não leitura comprovada. |

**Recomendação do Publicitário:** desenvolver primeiro o caminho 01. Ele dá
prioridade à leitura de `papiro` e possui o maior grau de desenho próprio no
nome. O símbolo isolado ainda precisa adquirir reconhecimento por uso; a
recomendação é uma avaliação de desenho, não um teste com o público.

## Arquivos por estudo

Cada subdiretório contém:

| Arquivo | Função |
| --- | --- |
| `papiro.svg` / `mark.svg` | Assinatura e símbolo em verde-oliva, transparentes |
| `papiro-reverse.svg` / `mark-reverse.svg` | Mesmas geometrias em cor clara para fundos escuros |
| `papiro-mono.svg` / `mark-mono.svg` | Reprodução preta em uma cor |
| `papiro.png` | Assinatura transparente, largura de 1200 px, para avaliação visual |

A cor é definida no atributo `color` da raiz e usada por `currentColor`.
Os arquivos claros são claros com transparência: precisam de fundo escuro.
As pranchas têm fundo e **não são arquivos de logo para produção**.

## Materiais e procedência

- Símbolos dos três caminhos e lettering do caminho 01 desenhados em
  geometria vetorial nesta exploração, em `generate.mjs`.
- Caminho 02: `Source Serif 4 Italic`, instância padrão de
  `source-serif-4-latin-standard-italic.woff2`, pacote já instalado
  `web/node_modules/@fontsource-variable/source-serif-4/`; peso 400,
  tamanho óptico padrão 20. Espaçamento ajustado no script.
- Caminho 03: `Inter Regular`, instância padrão de
  `inter-latin-standard-normal.woff2`, pacote já instalado
  `web/node_modules/@fontsource-variable/inter/`; peso 400,
  tamanho óptico padrão 14. Espaçamento ajustado no script.
- Rótulos das pranchas: Inter Regular. Todos os textos e assinaturas foram
  convertidos em contornos usando `fontkitten` 1.0.3 já instalado. Os SVGs
  renderizam sem fontes instaladas. Nenhum arquivo de fonte foi distribuído.
- As licenças locais dos dois pacotes foram lidas: SIL Open Font License 1.1.
  Fonte e licença permanecem nos respectivos pacotes do projeto.
- Paleta mantida constante para comparar desenho: oliva `#2c471c`
  (`accent` claro), claro `#e6ece1` (`ink` escuro), papel `#f4f6ee`
  (`paper` claro) e fundo `#0d1609` (`paper` escuro), a partir das conversões
  documentadas no acervo anterior e dos tokens atuais do site. Preto e
  branco puros nas demonstrações de monocromia. As cores não foram
  aprovadas como decisão de marca.
- Ferramentas: Node.js, `fontkitten`, `rsvg-convert`, Python padrão e
  ImageMagick. Nenhuma dependência nova ou recurso remoto.

## Inspeção óptica e uso provisório

Foram inspecionadas visualmente as duas pranchas renderizadas: assinatura,
símbolo, temas claros/escuros, uma cor e símbolos a 16, 24, 32 e 48 px.
Não foram observados recortes ou sobreposições acidentais. As contraformas
dos caminhos 01 e 03 permanecem distinguíveis a 16 px nesta renderização;
o caminho 02 perde força nesse tamanho e é recomendado a partir de 24 px.

| Estudo | Símbolo provisório | Assinatura provisória |
| --- | --- | --- |
| 01 | 16 px de caixa | 144 px de largura |
| 02 | 24 px de caixa | 160 px de largura |
| 03 | 16 px de caixa | 160 px de largura |

As assinaturas foram comparadas a 144 e 160 px. A de 01 preserva melhor sua
presença a 144 px; as de 02 e 03 ficam mais equilibradas a 160 px. Esses são
limites provisórios observados em tela, sem validação de impressão,
navegadores ou dispositivos adicionais. Não há variante óptica especial.
Não ampliar uma imagem da prancha para inferir o desempenho no tamanho real.

Preservar a proporção e todo o `viewBox` dos arquivos. Como regra provisória,
reservar espaço externo igual a 1/4 da altura da caixa do símbolo ou 1/2 da
altura visível da letra `o` da assinatura. Esta folga é recomendação de
composição e ainda não foi testada em layouts reais do site.

## Verificação estrutural e reprodução

```bash
node brand/studies/2026-11-26/generate.mjs
python3 brand/studies/2026-11-26/validate.py
```

O gerador precisa dos pacotes existentes em `web/node_modules` e do
`rsvg-convert`. O validador precisa apenas de Python padrão. A validação
concluída cobriu os **20 SVGs** (18 ativos e duas pranchas): XML, caixas
positivas, elementos vetoriais permitidos, IDs acessíveis únicos e ausência
de scripts, eventos, imagens, `foreignObject`, fontes ou recursos externos.
Os três PNGs de assinatura foram verificados como RGBA transparentes e têm
respectivamente 1200 × 365, 1200 × 355 e 1200 × 353 px. As pranchas medem
1800 × 1410 e 1200 × 850 px.

Os SVGs são estudos editáveis, não uma alegação de exclusividade, registro
ou aprovação. Não houve pesquisa com usuários ou busca de anterioridade.
Integração, favicon e acessibilidade no contexto de navegação ficam para o
`escriba` após a escolha de direção; nenhum arquivo de `web/` foi alterado.
