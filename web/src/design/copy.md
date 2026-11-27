# Voz e tom do papiro

Referência de copy para quem escreve texto de UI no `web/` — páginas,
componentes e custom elements. Curto e vinculante: em dúvida, siga a tabela.

## Tom

- **Sóbrio e direto.** Frases curtas, informação antes de ornamentação. O
  leitor é um concurseiro medindo cada minuto.
- **Flavor de arquivo com parcimônia.** "Acervo", "catalogado" são bem-vindos;
  nunca em detrimento da clareza. Nada de tom de marketing ("Descubra!",
  "incrível", "gratuito para sempre").
- **pt-BR de concurso.** Concordância e pontuação impecáveis; travessão `—`
  para incisos; `·` como separador de metadados.
- **Nunca prometa o que a UI não entrega.** Estados dizem o que houve e o que
  o usuário pode fazer ("só carrega com JavaScript ativado", "API
  indisponível").
- **Você** só no feedback de ação do usuário ("Você acertou", "Você errou").
  Em todo o resto, impessoal.

## Terminologia — um termo por conceito

| Conceito | Termo | Notas |
|---|---|---|
| unidade do acervo / registro da API | **questão** | contagens genéricas ("42 questões"), cards, filtros |
| enunciado de prova 100% certo/errado | **item** | jargão Cespe; só na meta de prova ("120 itens"). MC e mistas → "questões" |
| documento de uma seleção | **prova** | entrada dentro do evento; nome = cargo(s) |
| seleção/concurso que agrupa provas | **evento** | termo honesto (nem todo evento é concurso); o slug aparece em badge |
| tipo `certo_errado` | **Certo e errado** | mesma redação do Select de tipo |
| tipo `multipla_escolha` | **Múltipla escolha** | misto → "Certo e errado + Múltipla escolha" |
| resposta oficial | **gabarito** | "Ver gabarito", "Gabarito: …" |
| dimensões | **banca, órgão, cargo, ano, assunto** | vêm do dataset — nunca reescritos |
| documento de origem | **Fonte oficial** | link; `.pdf` → "PDF oficial" |
| fonte sem link (diretório, não-URL) | **Fonte indisponível** | texto morto, não link quebrado |
| ir para a lista filtrada | **Resolver as questões** | destino = question-browser |
| o que o site reúne | **acervo** | preferir a "dataset", "banco", "coleção" |

### Terminologia de marca

| Conceito | Termo | Notas |
|---|---|---|
| identidade visual como guarda-chuva | **marca** ou **identidade** | **Miolo** é o nome da identidade aprovada |
| composição completa símbolo + nome | **assinatura** | usar nos rótulos e orientações do showcase |
| livro aberto isolado | **símbolo** | também usado como favicon |
| componente de código | **`Logo`** | só em contexto técnico |

## Regras de microcopy

- **Plural sempre correto**: "1 questão" / "42 questões", "e mais 1 cargo" /
  "e mais 2 cargos", "1 prova" / "3 provas". Sem "(s)".
- **Números** em `pt-BR` (`1.234`).
- **Erro de API**: fato primeiro, causa depois — "Não foi possível carregar
  as questões — API indisponível." Estado de página inteira: "… a API está
  indisponível no momento."
- **Lista vazia**: nomeie o que faltou — "Nenhuma questão encontrada com esses
  filtros.", "Nenhum evento encontrado com essa busca.", "Nenhuma prova
  registrada para este evento." O demonstrativo concorda com o controle
  ("esses filtros" nos vários controles da index; "essa busca" no campo único
  de /provas).
- **Carregando**: "Carregando…" (reticência única `…`).
- **Links/ações** no infinitivo ("Resolver", "Ver"), curtos; `aria-label`
  acrescenta o contexto: "Resolver as questões — {prova}".
- **Jargão de pipeline proibido na UI**: ingerido, shard, crawler, registro.
  Prefira "catalogado", "reunido no acervo".
- **Texto do dataset é dado, não copy**: enunciados, alternativas, nomes de
  cargo/órgão passam por `esc()` e nunca são reescritos — inclusive caixa
  ALL-CAPS, que se corrige na fonte, não na exibição.

## Agente — explicação e cruzamento de edital

O agente (`POST /agente/explicar`, `POST /agente/edital`) é um recurso de IA
ancorado no acervo. Além das regras gerais, valem as suas:

- **Explica, não corrige.** O resultado é sempre "explicação" — nunca
  "correção" nem promessa de precisão. Quem corrige é o **gabarito oficial**,
  que vem do Postgres, não do modelo.
- **"Inteligência artificial" uma vez por resultado**, só no disclaimer.
  Fora dele, "o agente" — minúsculo, sem marca e sem antropomorfismo de
  marketing ("o agente está lendo" é estado, não personificação).
- **Campos do LLM são dado, não copy** — `explicacao`, `armadilha_banca`,
  `conceito_chave`, `pontos_chave`, `resumo`, `topico`, `disciplina`,
  `enunciado_resumo` passam por `esc()`/`textContent`, nunca `innerHTML`
  (contrato de segurança do `api/agente.py`).
- **Seção vazia some.** `armadilha_banca` `""`, `pontos_chave` `[]`,
  `questoes_relacionadas` `[]`, `disciplina_inferida` `""`,
  `banca_identificada` `null`, `modelo` `"nenhum"` — omitir; a UI nunca
  escreve "não informado".
- **O aviso não é erro.** `anulada` e `texto_base_ausente` são respostas
  `200` — tratar como conteúdo, não como falha.

### Terminologia do agente

| Conceito | Termo | Notas |
|---|---|---|
| recurso de IA | **o agente** | minúsculo; "O agente está lendo a questão…" |
| resultado de `/agente/explicar` | **explicação** | nunca "correção" |
| ação na página da questão | **Explicar a questão** | botão |
| página/nav de `/agente/edital` | **Edital** (nav) · **Cruzar o edital** (H1, botão, `title`) | |
| questão sem gabarito vigente | **anulada** | mesma palavra do dataset |
| enunciado sem o texto que o embasa | **texto-base ausente** | aviso, não erro |
| questões sugeridas ao final | **Questões relacionadas** | CTA "Resolver" |
| prioridade do tópico | **Prioridade alta · média · baixa** | redação do badge |

### Explicar a questão (`POST /agente/explicar`)

| Estado | Redação |
|---|---|
| botão | **Explicar a questão** — aria-label "Explicar a questão — {id}" |
| carregando (status) | "O agente está lendo a questão…" |
| carregando (linha auxiliar) | "Isso pode levar até 30 segundos." |
| sem JavaScript | "A explicação do agente só funciona com JavaScript ativado." |
| campo dúvida — label | "Dúvida sobre a questão (opcional)" |
| campo dúvida — placeholder | "O que não ficou claro nesta questão?" |
| campo dúvida — contador | "{n}/500" |
| dúvida acima do limite | "A dúvida pode ter no máximo 500 caracteres." |
| linha do gabarito | "Gabarito oficial: {Certo · Errado · Alternativa X}" — mesma inflexão do card |
| `acertou: true` | "Você acertou — gabarito: {gabarito}" |
| `acertou: false` | "Você errou — gabarito: {gabarito}" |
| títulos de seção | **Explicação** · **Armadilha da banca** · **Conceito-chave** · **Pontos-chave** · **Questões relacionadas** |
| disciplina inferida | "Disciplina inferida: {disciplina_inferida}" |
| relacionada — meta | "{banca} · {orgao} · {ano}" |
| relacionada — CTA | "Resolver" — aria-label "Resolver a questão — {id}" |
| relacionada — fonte | link secundário ao lado do CTA — "Fonte oficial"/"PDF oficial", aria "{rótulo} — {id}" |
| `anulada: true` | título "Questão anulada"; corpo "A banca anulou esta questão — não há gabarito vigente nem explicação. Confira os comunicados na fonte oficial." |
| `texto_base_ausente: true` | título "Texto-base ausente"; corpo "Esta questão remete a um texto-base externo que não está no recorte do acervo. O gabarito oficial está confirmado, mas a justificativa depende do texto — consulte a fonte oficial." — a linha do gabarito/feedback também abre este aviso |
| link da fonte | "Fonte oficial"; `.pdf` → "PDF oficial" |
| disclaimer | "Explicação gerada por inteligência artificial — pode conter imprecisões. O gabarito é o oficial da banca; em caso de divergência, vale o PDF oficial da prova." |
| modelo | sufixo do disclaimer: " · modelo {modelo}" — omitir quando `"nenhum"`; `cached` nunca aparece |

### Cruzar o edital (`POST /agente/edital`)

| Estado | Redação |
|---|---|
| nav | "Edital" |
| `Layout title` | "papiro — edital" |
| PageHeader — título | "Cruzar o edital" |
| PageHeader — descrição | "Cole o conteúdo programático do edital e veja quantas questões do acervo cobrem cada tópico — cada um vira uma lista pronta para resolver." |
| textarea — label | "Conteúdo programático do edital" |
| textarea — placeholder | "Cole aqui o trecho do edital com as disciplinas e os tópicos da prova…" |
| textarea — ajuda | "Entre 50 e 30.000 caracteres — só o conteúdo programático, não o edital inteiro." |
| textarea — contador | "{n}/30.000" |
| banca — label / placeholder | "Banca (opcional)" / "Ex.: Cebraspe" |
| cargo — label / placeholder | "Cargo (opcional)" / "Ex.: Escrivão de Polícia Federal" |
| botão submit | "Cruzar o edital" |
| carregando (status) | "O agente está lendo o edital…" |
| carregando (linha auxiliar) | "Isso pode levar até 40 segundos — inclui a contagem de questões no acervo." |
| sem JavaScript | "O cruzamento do edital só funciona com JavaScript ativado." |
| sem API (EmptyState do SSR) | "O cruzamento do edital depende da API — indisponível no momento." — sem o "restante do site segue funcionando" do 503 (sem API, as listas também não carregam) |
| validação — texto curto | "Cole o conteúdo programático — o texto precisa de pelo menos 50 caracteres." |
| validação — texto longo | "O texto passa de 30.000 caracteres — cole apenas o conteúdo programático do edital." |
| seção do resumo | "Resumo" |
| banca identificada | "Banca identificada: {banca_identificada} — aplicada aos filtros dos tópicos." (omitir se `null`) |
| seção dos tópicos | "Tópicos do edital" |
| badge de prioridade | "Prioridade alta" · "Prioridade média" · "Prioridade baixa" |
| contagem por tópico | "{n} questões no acervo" (plural correto); `0` → "Nenhuma questão no acervo" |
| `questoes_disponiveis: null` | "Contagem indisponível no momento — o filtro para as questões funciona mesmo assim." |
| CTA por tópico | "Resolver as questões" — aria-label "Resolver as questões — {tópico}" |
| `topicos: []` | "O agente não extraiu tópicos deste texto — confira se o trecho colado é o conteúdo programático do edital e tente novamente." |
| disclaimer | "Leitura gerada por inteligência artificial — o conteúdo programático que vale é o do edital oficial da banca." (+ " · modelo {modelo}") |

### Erros do agente (compartilhados pelos dois endpoints)

Fato primeiro, causa depois; com ação sempre que houver. O detalhe técnico do
`detail` da API nunca aparece na UI.

| Estado | Redação |
|---|---|
| 404 (só `/explicar`) | "Questão não encontrada — verifique o identificador ou tente novamente mais tarde." |
| 422 — `/explicar` | "A dúvida pode ter no máximo 500 caracteres." |
| 422 — `/edital` | "O conteúdo programático precisa ter entre 50 e 30.000 caracteres." |
| 429 | "Limite de uso do agente atingido — tente novamente em {espera}." |
| 503 | "O agente está indisponível no momento — o restante do site segue funcionando." + botão "Tentar novamente" |
| rede/timeout | "Não foi possível contatar o agente — verifique a conexão e tente novamente." + botão "Tentar novamente" |
| falha genérica | "Não foi possível obter a explicação — tente novamente." / "Não foi possível cruzar o edital — tente novamente." |

`{espera}` humaniza o `Retry-After` (segundos): < 60 s → "alguns segundos";
< 60 min → "{n} minuto(s)"; < 24 h → "{n} hora(s)"; acima disso → "amanhã"
(cobre o teto diário global, que vira na meia-noite UTC).
