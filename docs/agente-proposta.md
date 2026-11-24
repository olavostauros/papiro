# Proposta do Agente — Papiro (HackBrasil)

Proposta técnica consolidada para o agente de IA do **Papiro** (HackBrasil — trilha **Acesso à Educação**, entrega: segunda 30/11/2026 às 23h59), baseada nos dados reais do repositório (`api/`, `crawler/db.py`, `db/initdb/01-papiro-ro.sh`, `compose.yaml`, `Dockerfile`, `web/` e 426 shards em `data/questions/`).

## Achados empíricos do repositório que moldam o desenho

- **Acervo real massivo:** **307.624 questões** em 426 concursos, 319 órgãos e 2.834 cargos (77,9% `certo_errado`, 22,1% `multipla_escolha`; mediana de enunciado: **172 caracteres**, p95: 427).
- **Lacuna crítica na coluna `assunto`:** **60,6% das questões (186.449)** têm `assunto` vazio (`NULL`), e os 39,4% preenchidos concentram rótulos genéricos (`Conhecimentos Específicos`, `Conhecimentos Básicos`). Logo, cruzar questões relacionadas e tópicos de edital apenas por `assunto` falharia — é necessário usar busca textual sem acento (`queries.unaccent_ilike`) sobre `QuestaoDB.enunciado`.
- **VM pequena (`e2-small`, 2 GB RAM, sem GPU)** atrás de Cloudflare Tunnel (`api.olavostauros.com`): inviabiliza LLM local; o agente chama API externa via HTTPS.
- **Banco somente leitura na API (`papiro_ro`):** `db/initdb/01-papiro-ro.sh` concede apenas `SELECT`. Cache, rate limit e teto diário na v1 ficam em memória (sem `INSERT` no Postgres).
- **Schema atual sem editais nem `pgvector`:** Postgres 17 possui apenas `banca`, `orgao`, `assunto`, `evento`, `prova` e `questao`.
- **Anuladas hoje não entram no banco:** o crawler descarta itens com gabarito `X` e `questao` possui `CheckConstraint` permitindo apenas `certo`, `errado`, `a`–`e`.
- **CORS restrito:** `api/main.py` hoje libera apenas `allow_methods=["GET"]`; expor `POST` exige ampliar para `["GET", "POST"]`.
- **Dependências acopladas ao Docker:** `Dockerfile` instala `crawler/requirements.lock` com `--require-hashes`. **`httpx` e `pydantic` já estão instalados** em `crawler/requirements.txt` — integramos o Gemini via REST sem adicionar dependências nem alterar o lockfile.
- **Segredos / `.gitignore` confirmados:** `.gitignore` já ignora `.env`, `.env.*` (exceto `.env.example`), `*.local.json`, `*.pem` e `*.key`.

---

## 1. Modelo, provider e validação real da API

| Critério | **Google Gemini API** (`gemini-4-hydrogen` + fallback `gemini-3.5-flash-lite`) | **Groq API** (Llama / modelos abertos) | **OpenAI API** (`mini` / `nano`) |
|---|---|---|---|
| **Camada gratuita** | **Sim** (AI Studio, sem cartão; `gemini-4-hydrogen` e `gemini-3.5-flash-lite` disponíveis) | **Sim** (sem cartão, mas TPM gratuito apertado ~8K–12K) | **Não** (créditos pré-pagos) |
| **Português jurídico / concursos** | **Excelente** (legislação BR, súmulas, estilo Cebraspe) | Bom, mais fraco em nuances jurídicas BR | **Excelente** |
| **Contexto** | **1M tokens** (suporta editais longos sem RAG) | Menor | 128K–400K tokens |
| **Integração na VM** | Total via HTTPS (`httpx` já instalado) | Total via HTTPS | Total via HTTPS |

### Validação real realizada (24/11/2026)
- **Endpoint:** `POST https://generativelanguage.googleapis.com/v1/interactions`
- **Headers:** `x-goog-api-key` + `Api-Revision: 2026-05-20`
- **Configuração validada:** `store: false`, `generation_config: {"thinking_level": "low"}` e `response_format` (`{"type": "text", "mime_type": "application/json", "schema": ...}`).
- **Resultado do teste real:**
  - `gemini-4-hydrogen` retornou `503 service_unavailable` por pico temporário de demanda no momento da sonda.
  - `gemini-3.5-flash-lite` retornou `200 OK` (`1.434 ms`, `status: "completed"`, `steps: ["thought", "model_output"]` e JSON aderente ao schema).
- **Estratégia de resiliência aprovada:** `GEMINI_MODEL` padrão **`gemini-4-hydrogen`** e `GEMINI_FALLBACK_MODEL` padrão **`gemini-3.5-flash-lite`**. Em erro `503` ou `429` de sobrecarga, faz **1 nova tentativa no principal após ~1 s**; persistindo a falha, faz **1 tentativa no fallback** usando o mesmo schema de saída. O campo `modelo` da resposta informa qual modelo respondeu.

---

## 2. Acesso aos dados: contexto direto + busca `unaccent_ilike`

**Decisão:** **Contexto direto** a partir do Postgres (sem RAG/`pgvector`).

- `POST /agente/explicar` recebe `questao_id`, consulta `queries.base_questao().where(QuestaoDB.id == questao_id)` e envia ao Gemini os metadados oficiais (`banca`, `orgao`, `cargo`, `ano`, `assunto`, `tipo`, `enunciado`, `alternativas`, `gabarito`, `fonte`).
- Para compensar os 60,6% sem `assunto`, o Gemini gera um `termo_busca` técnico no mesmo JSON e o backend busca até **3 questões relacionadas reais no Postgres** via `queries.unaccent_ilike(QuestaoDB.enunciado, termo_busca)` (custo zero de LLM extra).

---

## 3. Contrato na API (`api/agente.py`) — plano em 2 entregas

### Entrega 1 (MVP estruturado + script de aquecimento)
- **`POST /agente/explicar`**
  - **Request:** `questao_id`, `resposta_usuario` (opcional), `duvida` (opcional, máx. 500 chars).
  - **Response (`200`):** `questao_id`, `gabarito_oficial`, `fonte`, `anulada`, `acertou`, `disciplina_inferida`, `explicacao`, `armadilha_banca`, `conceito_chave`, `pontos_chave`, `questoes_relacionadas` (até 3), `modelo`, `cached`.
  - **Códigos:** `200`, `404` (questão inexistente), `422` (payload/resposta inválida), `429` (limite por IP ou teto diário + `Retry-After`), `503` (chave ausente ou falha de provider — sem afetar `/questoes` ou `/health`).
- **Script local fora da API pública:** `scripts/aquecer_cache_agente.py` para pré-aquecer o cache em memória antes da demo usando uma lista de `questao_id`s.

### Entrega 2 (diferencial de edital após Entrega 1 testada)
- **`POST /agente/edital`** — recebe conteúdo programático colado (limite rígido de caracteres), extrai até **6 tópicos** prioritários com termos técnicos e consulta o Postgres com timeout por query e `queries.unaccent_ilike` (medindo a latência real no acervo) para retornar quantas questões existem por tópico + filtros prontos.

---

## 4. Regra de ouro: gabarito definitivo como fonte da verdade

1. **Dados sempre do servidor:** o cliente envia apenas `questao_id`; enunciado, `gabarito` e `fonte` vêm do Postgres.
2. **Curto-circuito para anuladas:** se `gabarito` não pertencer ao domínio válido do `tipo` (`certo`/`errado` ou `a`–`e`), retorna imediatamente `anulada: true`, aviso explícito e `fonte`, **sem chamar o LLM**.
3. **Prompt rígido + anti-injection:** fixa o gabarito definitivo como fato incontestável, proíbe inventar legislação/jurisprudência, orienta a avisar quando faltar texto-base (apontando `fonte`) e isola `duvida` em tags delimitadoras.
4. **Saída ancorada + guardrail:** `gabarito_oficial` e `fonte` vêm do Postgres; checagem pós-resposta intercepta contradições explícitas contra o gabarito da banca e aplica fallback seguro.

---

## 5. Custos, limites e segurança

- **Cache em memória por `questao_id` (LRU + TTL 24h):** chamadas sem `duvida` nem `resposta_usuario` reutilizam a resposta com zero tokens extras.
- **Rate limit por IP em memória (`CF-Connecting-IP`):** `5 req/min` e `30 req/dia` por IP (`429` + `Retry-After`).
- **Teto global diário:** `200` chamadas reais/dia ao LLM (`AGENTE_DAILY_GLOBAL_CAP`), evitando estouro de cota gratuita.
- **Segredos:** `GEMINI_API_KEY` lida somente de variável de ambiente (`.env/docker.env` no compose, sem valores commitados).

---

## 6. Arquivos da Fase 2 (branch `agente`, sem tocar em `crawler/`, `data/`, `web/`)

- **Criar:**
  - `api/agente.py` — router `/agente/explicar` (Entrega 1) e depois `/agente/edital` (Entrega 2), cliente Interactions API v1 com retry/fallback, guardrail de gabarito, cache e rate limit.
  - `scripts/aquecer_cache_agente.py` — script CLI local para pré-aquecer o cache da demo.
  - `tests/test_agente.py` — testes automatizados com SQLite + mocks (sem rede), cobrindo fallback, cache, anuladas, rate limit e guardrail.
- **Alterar (mínimo):**
  - `api/main.py` — incluir router do agente e ampliar CORS para `allow_methods=["GET", "POST"]`.
  - `compose.yaml` — repassar `GEMINI_API_KEY`, `GEMINI_MODEL` e `GEMINI_FALLBACK_MODEL` para o container `api` (sem valores).

---

## 7. Contrato final de `POST /agente/explicar` (consumo pelo front)

- **Método e URL:** `POST /agente/explicar` (CORS liberado para `GET` e `POST`).
- **Headers:** `Content-Type: application/json`

### Request (`ExplicarRequest`)

| Campo | Tipo | Obrigatório | Regras / Observações |
|---|---|---|---|
| `questao_id` | `string` | Sim | `3` a `120` caracteres (ex.: `cebraspe-2024-pf-escrivao-001`). |
| `resposta_usuario` | `string \| null` | Não | Máx. `20` chars. Valores válidos: `"certo"` \| `"errado"` (para `certo_errado`) ou `"a"`..`"e"` (para `multipla_escolha`), case-insensitive. |
| `duvida` | `string \| null` | Não | Máx. `500` caracteres. Qualquer texto em `resposta_usuario` ou `duvida` ignora o cache compartilhado para responder sob medida. |

```json
{
  "questao_id": "cebraspe-2024-pf-escrivao-001",
  "resposta_usuario": "errado",
  "duvida": "Qual é a pegadinha desse item?"
}
```

### Response `200 OK` (`ExplicarResponse`)

| Campo | Tipo | Descrição |
|---|---|---|
| `questao_id` | `string` | Identificador da questão. |
| `gabarito_oficial` | `string` | Gabarito definitivo vindo direto do Postgres (`"certo"`, `"errado"` ou `"a"`–`"e"`). |
| `fonte` | `string` | URL oficial do caderno/prova no Postgres. |
| `anulada` | `boolean` | `true` quando anulada/fora do domínio (retorna sem chamar LLM). |
| `texto_base_ausente` | `boolean` | `true` quando o enunciado referencia texto externo ausente (curto-circuito seguro sem LLM). |
| `acertou` | `boolean \| null` | `true`/`false` quando `resposta_usuario` foi enviada; `null` caso contrário. |
| `disciplina_inferida` | `string` | Disciplina/matéria estimada (útil nos 60,6% sem `assunto`). |
| `explicacao` | `string` | Explicação didática fundamentada no gabarito oficial. |
| `armadilha_banca` | `string` | Pegadinha típica explorada pela banca no item. |
| `conceito_chave` | `string` | Conceito central para revisão rápida. |
| `pontos_chave` | `string[]` | Até 5 tópicos curtos de fixação. |
| `questoes_relacionadas` | `QuestaoRelacionada[]` | Até 3 itens do acervo (`id`, `banca`, `orgao`, `ano`, `enunciado_resumo`, `fonte`). |
| `modelo` | `string` | Modelo que respondeu (`gemini-4-hydrogen`, `gemini-3.5-flash-lite`, ou `"nenhum"` se anulada). |
| `cached` | `boolean` | `true` quando servido do cache em memória. |

```json
{
  "questao_id": "cebraspe-2024-pf-escrivao-001",
  "gabarito_oficial": "certo",
  "fonte": "https://cdn.cebraspe.org.br/concursos/PF_24/arquivos/p1.pdf",
  "anulada": false,
  "texto_base_ausente": false,
  "acertou": false,
  "disciplina_inferida": "Direito Administrativo",
  "explicacao": "O gabarito oficial é CERTO porque...",
  "armadilha_banca": "A banca costuma inverter ato vinculado e ato discricionário.",
  "conceito_chave": "Vinculação e motivação dos atos administrativos.",
  "pontos_chave": [
    "Ato vinculado não comporta juízo de conveniência e oportunidade.",
    "A motivação deve ser explícita, clara e congruente."
  ],
  "questoes_relacionadas": [
    {
      "id": "cebraspe-2023-pf-escrivao-002",
      "banca": "Cebraspe",
      "orgao": "Polícia Federal",
      "ano": 2023,
      "enunciado_resumo": "O ato administrativo discricionário também se sujeita ao controle de legalidade.",
      "fonte": "https://cdn.cebraspe.org.br/concursos/PF_23/arquivos/p1.pdf"
    }
  ],
  "modelo": "gemini-4-hydrogen",
  "cached": false
}
```

### Códigos de erro HTTP

| Status | Quando ocorre | Tratamento esperado no front |
|---|---|---|
| `404` | `questao_id` não existe no Postgres. | Exibir aviso de questão não encontrada. |
| `422` | JSON inválido, `duvida > 500` chars ou `resposta_usuario` incompatível com `tipo`. | Validar entrada no formulário. |
| `429` | Rate limit por IP (`5/min`, `30/dia`) ou teto diário global (`200/dia`); inclui header `Retry-After`. | Exibir aviso amigável com tempo de espera. |
| `503` | `GEMINI_API_KEY` ausente ou falha/sobrecarga simultânea no modelo principal e fallback. | Exibir botão de tentar novamente (demais rotas da API seguem operando). |

### Exemplo `curl`

```bash
curl -s -X POST http://127.0.0.1:8000/agente/explicar \
  -H "Content-Type: application/json" \
  -d '{
    "questao_id": "cebraspe-2024-pf-escrivao-001",
    "resposta_usuario": "errado",
    "duvida": "Qual é a pegadinha desse item?"
  }'
```

---

## 8. Contrato de `POST /agente/edital` (Entrega 2) e medição real

- **Request (`EditalRequest`):** `texto_edital` (`50` a `30.000` chars), `banca` (opcional), `cargo` (opcional).
- **Response `200 OK` (`EditalResponse`):** `resumo`, `banca_identificada`, até **6** `topicos` (`disciplina`, `topico`, `prioridade` `"alta"|"media"|"baixa"`, `termo_busca` com no máximo 2 palavras técnicas, `questoes_disponiveis`, `timeout_consulta`, `tempo_consulta_ms`, `filtro_sugerido`), `tempo_total_consultas_ms`, `modelo`. Se a contagem inicial for menor que 5 (e sem timeout), tenta 1 vez com termo mais curto.
- **Timeout por consulta:** `AGENTE_EDITAL_QUERY_TIMEOUT_MS` (padrão `2500` ms). Em Postgres usa `SET LOCAL statement_timeout`; em SQLite usa `set_progress_handler`. Se estourar o timeout em um tópico, retorna `timeout_consulta: true` e `questoes_disponiveis: null` sem falhar a requisição (`200`).

### Medição real de `unaccent_ilike` (307.446 questões no SQLite local)

| Termo | Questões encontradas | Sem filtro de banca | Com `banca="Cebraspe"` |
|---|---:|---:|---:|
| `"ato administrativo"` | 1.141 | 5.221 ms | 4.995 ms |
| `"improbidade"` | 1.690 | 5.475 ms | 5.055 ms |
| `"licitacao"` | 2.581 | 5.183 ms | 5.000 ms |
| `"crase"` | 834 | 5.359 ms | 4.737 ms |
| `"constitucionalidade"` | 484 | 5.042 ms | 4.938 ms |
| `"habeas corpus"` | 299 | 5.146 ms | 4.828 ms |
| **Total (6 queries)** | — | **31.426 ms** | **29.553 ms** |

*Nota:* no SQLite o `unaccent()` roda via UDF Python por linha (~5 s por varredura completa), e o timeout de `1.000 ms` disparou exatamente em `1.002 ms`. Em produção no Postgres 17 (extensão `unaccent` nativa em C), espera-se execução bem mais rápida; o teto de `2.500 ms` por consulta protege contra bloqueios na VM `e2-small`. (Melhoria futura para o pós-hackathon: índice GIN `pg_trgm` sobre `unaccent(enunciado)` se houver escrita/migração no Postgres.)
