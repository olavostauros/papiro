# papiro — rodada 03 / Recraft

**Atualização de 26/11/2026:** o usuário aprovou **03 — Miolo**, apresentado
na terceira coluna da comparação. Foram adotados o símbolo local da rodada
02 e o lettering original, exatamente como reapresentados aqui. Os
[arquivos canônicos e instruções](../../README.md) estão em `brand/`.
As pranchas e avaliações abaixo preservam o estado exploratório anterior
à escolha; Miolo não teve geração Recraft bem-sucedida.

O Recraft produziu
quatro símbolos vetoriais: duas alternativas de Margens e duas de Lombada.
A tentativa de Miolo retornou saldo insuficiente. Foram informados **48
créditos** nas duas chamadas bem-sucedidas, 24 por rota. Nenhum crédito
adicional foi comprado e não houve nova geração após a falha.

Começar pela [comparação antes/depois](comparison.png). Também estão
disponíveis a [prancha das quatro saídas originais](candidates.png) e as
[reduções em tamanho real](reductions.png). As três pranchas têm versões
SVG editáveis: [comparação](comparison.svg), [alternativas](candidates.svg)
e [reduções](reductions.svg).

## Contexto e ferramenta

O [briefing bilíngue](BRIEF.md) usa o público, o produto, o estudo semiótico
e as escolhas da rodada 02. Cada chamada recebeu o contexto completo em
inglês, o prompt da rota e o respectivo símbolo de referência, enviado em
PNG de 1024 px com fundo de papel `#f4f6ee`.

O modelo recomendado pela descoberta autenticada do Recraft foi
`recraftv4_1_pro_vector`, V4.1 Vector Pro. Esse identificador foi solicitado
nas chamadas `image_to_image`, com `strength=0.4`,
`input_style=vector_illustration` e `n=2`. O serviço aceitou os parâmetros;
não retornou um metadado independente de versão. O
[registro real da execução](RUN-approved.md) contém prompts integrais,
referências, URLs de resultado, IDs, hashes e custo explicitamente informado.

## Seleção e avaliação visual

| Rota | Seleção para composição | Observação e limite |
| --- | --- | --- |
| [Margens](01-margens/papiro.svg) | Alternativa B | Mantém duas molduras fechadas e a geometria angular. A alternativa A cria fendas inferiores finas, frágeis na redução, e por isso ficou apenas como registro. B continua próxima ao desenho anterior e ainda pode parecer duas portas. |
| [Lombada](02-lombada/papiro.svg) | Alternativa B | Selecionada pelos miolos amplos e pela menor massa aparente na junção entre as duas páginas. A alternativa A também é coerente; a preferência por B é julgamento do Publicitário. O encontro central ainda pode sugerir um M. |
| [Miolo — referência anterior](../2026-11-26-round-02/03-miolo/papiro.svg) | Sem resultado nesta rodada | Mantido somente como referência da rodada 02 nas pranchas. Não foi redesenhado nem apresentado como criação do Recraft. |

**A evolução é discreta.** O modelo manteve as famílias e produziu pequenas
variações de curvas, aberturas e massa. Isso não demonstra um salto de
qualidade sobre a rodada 02. Os caminhos recebidos têm muito mais segmentos
que a geometria local anterior e pequenas assimetrias; uma edição vetorial
manual posterior pode ser mais útil do que novas gerações semelhantes.

A recomendação histórica, anterior à escolha do usuário, era trabalhar a
direção **Lombada** pela leitura
imediata de livro e pela relação com os bojos do lettering. A seleção B é
uma alternativa para avaliação, sem substituir automaticamente a versão
anterior ou estabelecer preferência do usuário. Os quatro resultados
originais permanecem visíveis para comparação.

## O que foi preservado e o que foi ajustado

O Recraft gerou somente os símbolos. As seis letras, suas proporções e seus
espaçamentos internos foram recompostos a partir do **grupo vetorial exato**
da proposta `2026-11-26/01-nome/papiro.svg`. Nenhuma fonte foi usada para
redesenhar o nome.

Os quatro arquivos de `raw/` preservam os bytes recebidos, inclusive os
metadados C2PA do fornecedor. Nas duas seleções, os ajustes locais são
reprodutíveis em `prepare.py` e `selections.json`:

1. Retirada do metadado C2PA apenas da cópia de trabalho; o original com esse
   metadado permanece em `raw/`. A assinatura C2PA não foi verificada.
2. Retirada do path retangular que preenchia todo o canvas com quase branco.
3. Concatenação dos caminhos verdes e dos caminhos brancos internos em um
   path composto com `fill-rule="evenodd"`. Isso transforma as contraformas
   em transparência real, preservando cada comando de curva e a transformação
   original `translate(0,0)`; não houve redesenho das curvas.
4. Normalização da cor para `currentColor`, usando o oliva do projeto nas
   versões positivas. A geometria do modelo é mantida; a cor bruta recebida
   era próxima ao oliva, mas não idêntica.

O `viewBox` de 4358 × 4358 foi preservado nas cópias de trabalho. A composição
encaixa esse canvas proporcionalmente em 104 × 104 unidades e usa o arranjo
da rodada 02: intervalo e posição do lettering preservados, sem mexer nas
letras. Nenhum recorte de geometria foi aplicado.

## Peças de entrega

Cada rota selecionada tem:

| Arquivo | Uso |
| --- | --- |
| `mark.svg`, `papiro.svg` | Símbolo e assinatura em oliva, transparentes |
| `mark-reverse.svg`, `papiro-reverse.svg` | Versões claras para fundo escuro |
| `mark-mono.svg`, `papiro-mono.svg` | Reprodução preta em uma cor |
| `mark.png` | Símbolo RGBA transparente de 416 × 416 px |
| `papiro.png` | Assinatura RGBA transparente de 1200 × 279 px |

As pranchas são arquivos de avaliação com fundo, não logos de produção.
As cores de composição são oliva `#2c471c`, claro `#e6ece1`, papel
`#f4f6ee` e fundo escuro `#0d1609`, conforme as conversões já documentadas
dos tokens do site. Preto e branco puros são usados na monocromia.

O lettering é o desenho original da exploração 01. Os rótulos das pranchas
usam contornos de Inter Regular do pacote existente em `web/node_modules`,
sob SIL OFL 1.1, já verificada na rodada anterior. Nenhum arquivo de fonte
é distribuído. A procedência dos símbolos é o Recraft; isso não demonstra
exclusividade, registro ou liberação jurídica da marca.

## Inspeção e limites provisórios

Foram inspecionados os quatro resultados brutos, as seleções em comparação
com a rodada 02, as contraformas transparentes, as versões claras/escuras,
a monocromia e reduções a 16, 24, 32 e 48 px. As assinaturas foram comparadas
a 160, 176 e 208 px de largura. Não foram observados recortes ou sobreposições
acidentais na composição final.

Margens continua mais delicado a 16 px; **24 px** é o mínimo provisório
recomendado para o símbolo. Lombada permanece reconhecível a 16 px nesta
renderização, mas **24 px** conserva melhor a abertura e as curvas. Para
ambas as assinaturas, manter mínimo provisório de **160 px**, preferindo
**176 px** no cabeçalho. Não foi criada uma variante óptica específica.

Preservar a proporção e o `viewBox`. Manter provisoriamente espaço externo
equivalente a metade da altura visível do `o`, seguindo a composição anterior.
Esses limites são observações desta renderização de tela, sem teste com
usuários, impressão, outros dispositivos ou integração real no site.

## Reprodução e validação

```bash
python3 brand/studies/2026-11-26-round-03-recraft/inspect_svg.py
python3 brand/studies/2026-11-26-round-03-recraft/prepare.py
node brand/studies/2026-11-26-round-03-recraft/generate.mjs
node brand/studies/2026-11-26-round-03-recraft/candidates.mjs
rsvg-convert -o brand/studies/2026-11-26-round-03-recraft/candidates.png brand/studies/2026-11-26-round-03-recraft/candidates.svg
python3 brand/studies/2026-11-26-round-03-recraft/validate.py
```

Ferramentas locais: Python padrão, Node.js, `fontkitten` já instalado e
`rsvg-convert`. Não houve instalação de dependências. Os comandos locais
não chamam o Recraft e não consomem créditos.

O validador verifica os ativos e pranchas principais: XML, elementos
permitidos, caixas finitas e positivas, IDs únicos, ausência de scripts,
eventos, imagens embutidas e recursos externos; compara literalmente o
grupo original das letras em seis assinaturas e confere os quatro PNGs RGBA.
A prancha de alternativas e os quatro raw têm inspeção estrutural adicional.

Nenhum arquivo de `web/` foi alterado. Após a aprovação de Miolo, a integração
cabe ao escriba a partir dos arquivos canônicos de `brand/`. Sem commit, publicação ou deploy nesta entrega.
