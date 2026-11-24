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
