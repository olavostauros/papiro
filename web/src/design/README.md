# Design system do papiro

Documentação de referência dos tokens e componentes do papiro, escrita para ser usada
tanto por humanos quanto por agentes autônomos (Devin, Codex, ou qualquer agent harness)
que trabalhem no front-end.

Showcase navegável com todos os tokens e componentes: **`/papiro/design/`**
(`web/src/pages/design.astro`).

## Onde as coisas vivem

```
web/src/
├── design/
│   ├── tokens.css          # todos os design tokens (@theme do Tailwind v4) + modo escuro
│   ├── nav.ts              # itens de navegação usados por SiteHeader e SiteFooter
│   ├── components/         # componentes base (.astro, sem framework de UI)
│   │   └── icons/          # ícones SVG (Check, Moon, Sun, X)
│   └── elements/           # custom elements (.ts) — comportamento dos componentes
├── styles/global.css       # importa fontes, tailwindcss e tokens.css — único CSS global
├── layouts/Layout.astro    # <html>, <head>, script anti-FOUC de tema, skip link
└── components/DocSection.astro  # usado apenas pela página /design/
```

Stack: **Astro + Tailwind CSS v4** (via `@tailwindcss/vite`). Não existe
`tailwind.config` — toda a configuração é CSS-first em `tokens.css`. Fontes via
`@fontsource-variable` (Inter e Source Serif 4). Sem React/Vue: interatividade é
JavaScript vanilla na forma de **custom elements** (`design/elements/`) —
`<question-browser>`, `<question-card>`, `<question-filters>`, `<theme-toggle>` —
que envolvem o markup
dos componentes e se auto-inicializam em `connectedCallback`, com escopo por
instância (`this.querySelector`) em vez de queries globais no `document`.

## Regras de ouro (leia antes de escrever UI)

1. **Use sempre tokens semânticos** (`bg-surface`, `text-ink`, `border-line`,
   `text-accent`…). Nunca use a escala `olive-*` diretamente em componentes nem
   cores arbitrárias (`#fff`, `slate-*`, `bg-white`) — os semânticos já mudam com
   o tema. A escala `olive-*` existe só para definir os semânticos em `tokens.css`.
2. **Prefira compor componentes existentes** a inventar markup novo. Card para
   superfícies, Button para ações, Link para navegação inline, Badge para tags,
   EmptyState para listas vazias.
3. **Todo elemento interativo precisa de `focus-visible:focus-ring`** e de
   semântica acessível (roles, `aria-*`, rótulos em pt-BR).
4. **Estado visual via `data-*`**, não classes ad-hoc: componentes leem
   `data-state`, `data-opcao`, `data-filtro` etc. como contrato com o JavaScript.
   Comportamento novo vai num custom element em `design/elements/` (ver
   "Estendendo o sistema"), nunca num `<script>` com `document.querySelectorAll`.
5. **Todo componente aceita `class?: string`** para ajustes pontuais, usando
   `class:list` no template, e espalha `...rest` para atributos extras
   (`data-*`, `aria-*`, `id`…). Siga esse padrão em componentes novos.
6. **Não introduza framework de UI** (React, Vue…) sem decidir isso
   explicitamente — é uma questão em aberto no projeto (ver README raiz).
7. Ao adicionar token ou componente, **atualize `design.astro`** e esta
   documentação.

## Tokens

Todos os tokens vivem em `tokens.css`, dentro de `@theme` (Tailwind v4). A
convenção `--color-x` gera as utilidades `bg-x`, `text-x`, `border-x`, etc.

### Escala `olive` (primitiva — não usar diretamente em UI)

`--color-olive-50` … `--color-olive-950`, em OKLCh. Verde-azeitona frio, de baixo
croma. Use apenas dentro de `tokens.css` para compor tokens semânticos.

### Cores semânticas (use estas)

| Token | Utilidades | Uso |
|---|---|---|
| `paper` | `bg-paper` | fundo da página (`<body>`) |
| `surface` | `bg-surface` | superfícies elevadas: cards, header, footer |
| `line` | `border-line` | bordas suaves / divisores |
| `line-strong` | `border-line-strong` | bordas de inputs e controles |
| `ink` | `text-ink` | texto principal |
| `ink-soft` | `text-ink-soft` | texto secundário |
| `ink-faint` | `text-ink-faint` | texto terciário / letras de alternativa |
| `accent` | `bg-accent`, `text-accent` | cor de ação/ênfase |
| `accent-strong` | `hover:bg-accent-strong` | estado hover do accent |
| `accent-soft` | `bg-accent-soft` | fundo suave de hover/seleção |
| `paper-glass` | `bg-paper-glass` | `paper` a 80% via `color-mix`, para o header fixo com `backdrop-blur` |

### Feedback

| Token | Uso |
|---|---|
| `success`, `success-soft`, `success-line` | resposta correta (texto, fundo, borda) |
| `danger`, `danger-soft`, `danger-line` | resposta errada (texto, fundo, borda) |

Padrão de uso: `border-success-line bg-success-soft text-success`.

### Tipografia

| Token | Família | Uso |
|---|---|---|
| `--font-sans` → `font-sans` | Inter Variable | UI inteira (padrão no `<body>`) |
| `--font-serif` → `font-serif` | Source Serif 4 Variable | títulos (`PageHeader`, `Logo`), enunciados de questões |

Pesos usados: `font-normal`, `font-medium`, `font-bold`. Títulos sempre com
`tracking-tight`.

### Raios

`rounded-sm` (0.25rem) · `rounded-md` (0.375rem) · `rounded-lg` (0.5rem) ·
`rounded-xl` (0.75rem). Controles usam `rounded-md`, cards `rounded-xl`,
badges `rounded-full`, alvos de foco pequenos `rounded-sm`.

### Layout

`--container-content: 64rem` → utilidade `max-w-content`, usada pelo
`Container`. Todo conteúdo de página vive dentro de `Container`.

### Motion

`--default-transition-duration: 200ms` — `transition-colors` já usa esse valor.
Com `prefers-reduced-motion`, duração vai a 0. `.theme-switching` (no `<html>`)
desliga todas as transições durante a troca de tema.

### Foco

`focus-ring` é uma `@utility`: `outline: 2px solid var(--color-accent)` +
`outline-offset: 2px`. Aplicar como `focus-visible:focus-ring`.

## Modo escuro

- Variante `dark:` registrada por `@custom-variant` — é **por classe**:
  `.dark` no `<html>` ativa o tema.
- `Layout.astro` contém um script inline que aplica `.dark` antes do paint,
  lendo `localStorage.theme` e caindo em `prefers-color-scheme`. **Não remova.**
- Os overrides de cor vivem no bloco `.dark { … }` em `tokens.css`. Ao criar um
  token semântico novo, defina **os dois** valores (claro e escuro).
- `ThemeToggle` faz o toggle e sincroniza `aria-pressed`/`aria-label`; use-o em
  vez de implementar outro seletor de tema.
- Ao estilizar, escreva para os dois temas de uma vez — os tokens semânticos
  resolvem sozinhos; só use `dark:` para o que for exceção (ex.: ícones
  Sun/Moon no ThemeToggle).

## Componentes

Todos em `web/src/design/components/`. Props com valor padrão são opcionais.
Todo componente aceita `class?: string` e repassa atributos extras via
`...rest`.

### Container

`as?: 'div' | 'main' | 'section' | 'header' | 'footer'` (default `div`).

`mx-auto max-w-content px-4`. Envolve todo conteúdo de página:
`<Container as="main" id="conteudo" class="py-10">`. O `id="conteudo"` é o alvo
do skip link do `Layout` — mantenha em toda página.

### PageHeader

`title: string` + slot (descrição). Cabeçalho padrão de página:
`<h1>` serifado + parágrafo `text-ink-soft`, margem `mb-10`.

### Card

`as?: 'div' | 'article' | 'section'` (default `div`).

Superfície base: `rounded-xl border border-line bg-surface p-5`. É o bloco de
construção de quase tudo — use-o para agrupar conteúdo em vez de replicar essa
combinação de classes.

### EmptyState

Slot apenas. `Card` + `text-ink-soft`; para páginas/listas sem conteúdo.

### Button

`variant?: 'primary' | 'outline' | 'ghost'` (default `primary`) ·
`size?: 'sm' | 'md'` (default `md`) · `href?: string`.

Com `href`, renderiza `<a>`; sem, `<button>`. Já inclui
`focus-visible:focus-ring` e `transition-colors`.

```astro
<Button>Confirmar</Button>
<Button variant="outline" size="sm">Menor</Button>
<Button variant="ghost" href="/papiro/provas/">Ver provas</Button>
```

### Link

`href: string` · `variant?: 'subtle' | 'underline'` (default `subtle`).

Texto `ink-soft` que vai a `ink` no hover; `underline` adiciona sublinhado
`decoration-line`. Para navegação inline em textos e listas.

### Badge

`variant?: 'soft' | 'outline'` (default `soft`).

Pílula pequena (`rounded-full`, `text-xs font-medium`). `soft` usa
`accent-soft`/`accent`; para feedback, sobrescreva via `class`:
`<Badge class="bg-success-soft text-success">Correta</Badge>`.

### Select

`label: string` · `options: string[]` · `placeholder?: string` (default `'Todas'`).

`<label>` + `<select>` já rotulados e estilizados; a primeira `<option>` é o
placeholder com `value=""`. Filtros consomem via `data-filtro` repassado por
`...rest` (ver `question-filters` e `index.astro`).

### Alternativa

`valor: string` · `letra?: string`.

`<button role="radio">` de opção de resposta. O estado vem **todo** de
`data-state`:

| `data-state` | Significado | Visual |
|---|---|---|
| _(ausente)_ | neutra | `border-line-strong` |
| `selected` | escolhida pelo usuário | `accent-soft` |
| `correct` | gabarito | `success-*` + ícone `Check` automático |
| `wrong` | escolha errada | `danger-*` + ícone `X` automático |
| `dim` | não escolhida após correção | `opacity-60` |

Grupo: wrapper com `role="radiogroup"`. Nunca alterne classes manualmente —
só `dataset.state`.

### QuestionMeta

`banca`, `orgao`, `cargo: string` · `ano: number` · `assunto: string`.

Linha de metadados da questão: `Banca · Órgão · Cargo · Ano` + `Badge` de
assunto à direita (`ml-auto`).

### QuestionCard

`q: Question` — cartão completo e interativo da questão (metadados, enunciado
serifado, alternativas, "Ver gabarito", resultado, link da fonte). O markup é
envolvido por `<question-card>` (`design/elements/question-card.ts`), que cuida
da interação (seleção por click/setas, correção via `data-state`).

```ts
interface Question {
  id: string;
  banca: string;
  orgao: string;
  cargo: string;
  ano: number;
  assunto: string;
  tipo: 'certo_errado' | 'multipla_escolha';
  enunciado: string;
  alternativas: string[];   // 'Certo'/'Errado' ou opções a–e
  gabarito: string;         // 'certo' | 'errado' | 'a'..'e'
  fonte: string;            // URL da fonte oficial
}
```

Contrato `data-*` no elemento `<question-card>` renderizado: `data-banca`,
`data-orgao`, `data-cargo`, `data-ano`, `data-assunto` (lidos pelo filtro —
o elemento também leva `data-filter-item`), `data-gabarito` e
`data-gabarito-texto` (lidos pelo próprio elemento para a correção). Preserve
esses atributos ao alterar o componente.

### question-browser

Elemento wrapper (`design/elements/question-browser.ts`) — lista paginada de
questões servida pela API (`data/questions.ts`). Substituiu o filtro
client-side na `index`: os `<select>`s disparam `GET /questoes` com os filtros
ativos e `GET /filtros` repovoa as opções em cascata. Não entra no showcase
(`/design/`) por depender de API viva. Contrato interno:

- `data-api-url` no elemento — base da API (`PUBLIC_API_URL`); sem ele o
  componente fica inerte e o conteúdo SSR da página permanece;
- `data-per-page` — tamanho de página (default 20);
- `select[data-filtro="campo"]` — banca | orgao | cargo | ano | assunto;
- `[data-lista]` — contêiner substituído a cada fetch;
- `[data-contagem]` — total do resultado; `[data-paginacao]` — nav onde o
  elemento injeta Anterior/Próxima; `[data-status]` — mensagens de carregando/erro.

O template do card replica o markup de `QuestionCard`/`Alternativa`/
`QuestionMeta` — inclusive o contrato `data-*` lido por `<question-card>`.
**Ao mudar um, mude o outro** (o comentário no topo de
`question-browser.ts` lista os atributos do contrato). Todo texto dinâmico
passa por `esc()` antes de entrar no `innerHTML`.

### question-filters

Elemento wrapper (`design/elements/question-filters.ts`) que filtra itens por
`<select>`s escondendo/mostrando os já renderizados — adequado para listas
pequenas inteiramente no cliente (a `index` usa `question-browser` porque a
lista completa não cabe no build). Contrato interno:

- `select[data-filtro="campo"]` — filtra itens cujo `dataset[campo]` bate com o valor;
- `[data-filter-item]` — item filtrável (escondido via atributo `hidden`);
- `[data-contagem]` — elemento que recebe a contagem de itens visíveis.

### Logo

`href?: string` · `size?: 'lg' | 'xl'` (default `xl`).

Wordmark "papiro" em serif bold, `text-accent`. Com `href` renderiza `<a>`,
senão `<p>`.

### SiteHeader / SiteFooter

Sem props. Chrome do site: header fixo (`sticky`, `bg-paper-glass`,
`backdrop-blur`) com `Logo`, `Badge` HackBrasil, `ThemeToggle` e nav com
`aria-current` no item ativo; footer com 3 colunas. Ambos leem `design/nav.ts` —
para mexer na navegação, edite `navItems`/`projectLinks` lá.

### ThemeToggle

Sem props. `<theme-toggle>` (`design/elements/theme-toggle.ts`) envolve um
`<button>` que alterna `.dark` no `<html>` e persiste em `localStorage.theme`.
Ao trocar, o elemento sincroniza `aria-pressed`/`aria-label` de todos os
`<theme-toggle>` da página. O wrapper usa `display: contents` (global.css) e
não interfere no layout.

### Ícones (`icons/`)

`Check`, `X`, `Sun`, `Moon` — `class?: string` apenas. SVG estilo Lucide:
`viewBox 24`, `stroke="currentColor"`, `stroke-width 2`, `aria-hidden`. Cor e
tamanho vêm do contexto: `<Check class="size-4" />` dentro de um elemento com
`text-*`. Novo ícone: copie um existente e troque os `<path>`.

## Acessibilidade — checklist do sistema

Padrões já embutidos que devem ser mantidos em código novo:

- Skip link "Pular para o conteúdo" → `#conteudo` (no `Layout`; o `main` leva
  `tabindex="-1"`).
- `focus-visible:focus-ring` em todo elemento clicável/focável.
- Grupo de alternativas: `role="radiogroup"` + `role="radio"` +
  `aria-checked`; roving `tabindex` (só a opção ativa entra no Tab) e setas
  movem/selecionam — ver o script do `QuestionCard` como referência.
- Feedback dinâmico: `role="status"` (ou equivalente) para resultados anunciados
  por leitor de tela; nunca depender só de cor — `Alternativa` sempre mostra
  ícone junto à cor de feedback.
- `aria-hidden="true"` em separadores decorativos (`·`) e ícones; texto
  `.sr-only` para contexto extra (ex.: "(abre em nova aba)").
- `aria-label`/`aria-labelledby` descritivos em pt-BR; `aria-current="page"` no
  nav ativo; `aria-pressed` no ThemeToggle; `aria-disabled` (não `disabled`)
  para travar alternativas após a correção sem sair da ordem de foco.
- Respeitar `prefers-reduced-motion` (já resolvido nos tokens).

## Estendendo o sistema

**Novo token de cor semântica:** adicione `--color-foo` no `@theme` de
`tokens.css` e o override correspondente no bloco `.dark`. Fica disponível como
`bg-foo`/`text-foo`/`border-foo` imediatamente.

**Novo componente:** crie `components/Nome.astro` seguindo o padrão dos
existentes — `interface Props` tipada, `class?: string` + `class:list`,
`...rest` para atributos extras, tokens semânticos, `focus-ring` se interativo.
Se tiver comportamento, crie `elements/nome-do-elemento.ts` com uma classe que
estende `HTMLElement` (queries escopadas em `this`, estado por instância,
guarda `customElements.get` antes de `define`), envolva o markup com a tag
`<nome-do-elemento>`, carregue o módulo num `<script>import` do componente e
defina o `display` do elemento em `global.css` (custom elements nascem
`display: inline`).

**Em ambos os casos:** adicione uma `DocSection` em `design.astro` (a página de
showcase é a documentação viva — ela e este arquivo devem ficar sincronizados).

## Referência rápida de importação

```astro
---
import Layout from '../layouts/Layout.astro';
import SiteHeader from '../design/components/SiteHeader.astro';
import SiteFooter from '../design/components/SiteFooter.astro';
import Container from '../design/components/Container.astro';
import PageHeader from '../design/components/PageHeader.astro';
import Card from '../design/components/Card.astro';
import Button from '../design/components/Button.astro';
// Badge, Link, Select, Alternativa, QuestionMeta, QuestionCard,
// EmptyState, Logo, ThemeToggle, icons/* — mesmo diretório
---

<Layout title="papiro — título">
  <SiteHeader />
  <Container as="main" id="conteudo" tabindex="-1" class="py-10">
    <PageHeader title="Título">Descrição.</PageHeader>
    <!-- conteúdo -->
  </Container>
  <SiteFooter />
</Layout>
```

Estrutura padrão de toda página: `SiteHeader` → `Container as="main"
id="conteudo"` → `PageHeader` → conteúdo → `SiteFooter`.
