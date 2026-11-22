# papiro

Provas e questões oficiais de **concursos públicos brasileiros**, por banca, órgão, cargo, ano e
assunto — de graça e sem cadastro.

Projeto desenvolvido para o [HackBrasil](https://hackbrasil.com/) — a maior hackathon do Brasil —
na trilha **Acesso à educação**.

## O problema

Resolver questões de provas anteriores é a principal forma de estudar para concurso público no
Brasil. Mas acessar esse material hoje é difícil:

- **As provas estão espalhadas.** Cada banca (Cebraspe, FGV, FCC, Vunesp…) publica provas e
  gabaritos em PDFs soltos no próprio site, com padrões diferentes e links que quebram.
- **Os bancos de questões completos são pagos.** Filtrar por banca, órgão, cargo, ano e assunto —
  o básico para montar um simulado útil — costuma exigir assinatura.
- **Não dá para confiar na fonte.** Sites gratuitos agregam questões sem indicar de qual prova
  ela veio nem qual foi o gabarito definitivo publicado pela banca.

Quem não pode pagar estuda pior. Isso é um problema de acesso à educação.

## A solução

papiro é um site onde qualquer estudante acessa provas e resolve questões de concursos públicos
brasileiros, de graça e sem cadastro:

- Filtre questões por **banca, órgão, cargo, ano e assunto**
- Resolva questões e confira o **gabarito na hora**
- Acesse **provas oficiais completas** para montar seus simulados
- Cada questão traz o **gabarito definitivo** e a **fonte** de onde foi extraída

**Exemplo de uso:** Maria vai prestar o concurso do IBAMA para Analista Administrativo. No papiro
ela filtra `banca: Cebraspe` + `cargo: Analista Administrativo` + `assunto: Língua Portuguesa`,
resolve um bloco de 20 questões e confere o gabarito com a fonte oficial de cada uma.

## Como funciona

```
sites das bancas ──> crawler ──> PDFs oficiais ──> extração ──> Postgres ──> api ──> site
                  (scheduler)
```

1. O container **`crawler`** coleta provas e gabaritos nos sites das bancas em um agendamento
   (scheduler), extrai as questões dos PDFs e grava tudo no **Postgres** — com gabarito
   definitivo e fonte.
2. O container **`api`** serve o banco de questões para o site.
3. O **site** consome a API para filtrar, listar e exibir questões e provas.

`crawler` e `api` rodam a partir da **mesma imagem Docker `papiro`**, orquestrada pelo compose
junto com o container do Postgres — tanto no desenvolvimento local quanto no deploy.

### Formato dos dados

Cada questão é um registro no Postgres com metadados de filtro, enunciado, gabarito e fonte:

```json
{
  "id": "cebraspe-2024-pf-escrivao-042",
  "banca": "Cebraspe",
  "orgao": "Polícia Federal",
  "cargo": "Escrivão de Polícia Federal",
  "ano": 2024,
  "assunto": "Direito Administrativo",
  "tipo": "certo_errado",
  "enunciado": "A respeito dos atos administrativos, julgue o item a seguir. ...",
  "gabarito": "certo",
  "fonte": "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/..."
}
```

## Estrutura do repositório

```
papiro/
├── web/                # site (Astro, TypeScript, Tailwind CSS)
│   └── src/design/     # design system — tokens (cores, tipografia, espaçamento) e componentes base
├── crawler/            # coleta e extração de provas (Python) — roda em schedule
├── api/                # API do banco de questões (Python)
├── Dockerfile          # imagem única `papiro` — base dos containers crawler e api
└── compose.yaml        # api + crawler + Postgres (dev local e deploy na VM)
```

## Como executar

Pré-requisitos: Docker (com o plugin compose) e Node.js 22+ para o site.

### Operação (api + crawler + Postgres)

```bash
export POSTGRES_PASSWORD=$(cat .env/POSTGRES_PASSWORD)
docker compose up -d --build                # sobe db + api

# primeira vez (ou para reconstruir): shards → Postgres
docker compose run --rm crawler python -m crawler.db sync

# crawler roda one-shot sob o profile `crawler`
docker compose run --rm crawler python -m crawler next --probe 30
```

- `db` — Postgres, o banco de questões (populado pelos shards de `data/questions/`)
- `api` — FastAPI na porta 8000 (`/questoes`, `/filtros`, `/eventos`, `/provas`)
- `crawler` — coleta e extração de provas; roda por comando (cron/timer na VM)

### Site

```bash
cd web
npm install
npm run dev     # desenvolvimento em http://localhost:4321/papiro/
npm run build   # gera o site estático em dist/
npm run preview # serve o build de produção localmente
```

### Deploy

O backend é deployado em uma **VM no GCP** rodando o mesmo setup do desenvolvimento local: a
imagem `papiro` é publicada no Artifact Registry e a VM sobe os containers com o compose:

```bash
# na VM
docker compose pull
docker compose up -d
```

O front-end continua publicado no GitHub Pages a cada push na branch `master`, pelo workflow
`.github/workflows/deploy.yml`. URL de produção: https://olavostauros.github.io/papiro/

O deploy do site também pode ser disparado manualmente em **Actions → Deploy to GitHub Pages →
Run workflow**.

## Stack

- **Front-end:** Astro, TypeScript e Tailwind CSS; site estático no GitHub Pages
- **API:** Python, servindo o banco de questões
- **Crawler:** Python — parsers locais sobre poppler (`pdftotext`/`pdftohtml`) e API pública da Cebraspe; Firecrawl opcional para fontes sem parser local
- **Banco de dados:** Postgres
- **Infra:** Docker — imagem única `papiro` e compose para dev local e deploy em VM no GCP
- **Agente (planejado):** LLM que resolve, explica e ensina questões e lê editais

## Questões em aberto

**Front-end**

- Uso de React ou Vue — se e onde faz sentido introduzir componentes interativos além do que o
  Astro entrega sozinho

**Agente** — resolve, explica e ensina questões, e lê editais para ajudar o estudante a entender
o que vai cair na prova

- O agente roda no backend (a `api` já existe) — resta definir em qual ponto da API ele é exposto
- Escolha do modelo e provider
- Como o agente acessa o banco de questões, editais, recursos e decisões (RAG sobre o Postgres
  vs. contexto direto)
- Custos e limites de uso por estudante

## Próximos passos

O banco de dados também vai incluir editais, recursos e decisões das bancas.

No front-end, o design system será construído em `web/src/design/`: tokens de cores,
tipografia e espaçamento (via `@theme` do Tailwind) e os componentes base do site — botões,
ícones, cards, inputs e o que mais a interface precisar.

## O nome

**papiro** é gíria de concurseiro para o calhamaço de estudo — a apostila, o livro, o edital
enorme que precisa ser encarado de capa a capa. É também uma referência ao papiro original, um
dos primeiros suportes de escrita da história: papel de estudar, desde sempre.

## Origem

papiro nasceu do [Plantão](https://github.com/olavostauros/plantao), que cataloga questões de
provas oficiais de concursos policiais. papiro amplia o escopo para todos os concursos públicos
brasileiros, com foco em estudantes.
