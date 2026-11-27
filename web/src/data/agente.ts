/**
 * Client do agente pedagógico — POST /agente/explicar e POST /agente/edital
 * (api/agente.py — LLM ancorado no acervo; gabarito sempre do Postgres).
 *
 * Mesmo API_URL de questions.ts. O POST tem timeout maior (45 s) porque a
 * chamada ao provedor pode levar ~30 s (explicar) ou ~40 s (edital, que
 * inclui a contagem de questões por tópico) — o servidor tem deadline
 * próprio (AGENTE_REQUEST_DEADLINE_S) e responde 503 se estourar.
 *
 * Erros chegam como AgenteError: `status` guarda o HTTP status (0 = falha de
 * rede/timeout do lado do cliente) e `retryAfter` os segundos do header
 * Retry-After (429/503), quando presente.
 */

import { API_URL } from './questions';

export class AgenteError extends Error {
  /** HTTP status da resposta; 0 quando nem resposta houve (rede/timeout). */
  readonly status: number;
  /** Retry-After em segundos (429/503); null quando ausente ou inválido. */
  readonly retryAfter: number | null;

  constructor(message: string, status = 0, retryAfter: number | null = null) {
    super(message);
    this.name = 'AgenteError';
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

export interface ExplicarRequest {
  questao_id: string;
  /** 'certo'|'errado' ou 'a'..'e' — a opção marcada no card da questão. */
  resposta_usuario?: string;
  /** Máx. 500 chars — campo de dúvida livre do usuário. */
  duvida?: string;
}

export interface QuestaoRelacionada {
  id: string;
  banca: string;
  orgao: string;
  ano: number;
  enunciado_resumo: string;
  fonte: string;
}

export interface ExplicarResponse {
  questao_id: string;
  /** 'certo'|'errado'|'a'..'e' ('anulada' quando anulada=true). */
  gabarito_oficial: string;
  fonte: string;
  anulada: boolean;
  texto_base_ausente: boolean;
  /** Tipo do material-base ausente quando texto_base_ausente=true; null nos demais casos. */
  material_ausente: 'texto' | 'imagem' | null;
  acertou: boolean | null;
  disciplina_inferida: string;
  explicacao: string;
  armadilha_banca: string;
  conceito_chave: string;
  /** Modo diagnóstico — preenchido apenas quando acertou=false e não há curto-circuito. */
  por_que_parecia_certa: string;
  /** Modo diagnóstico — tópico curto de revisão; acompanha por_que_parecia_certa. */
  topico_para_revisar: string;
  pontos_chave: string[];
  questoes_relacionadas: QuestaoRelacionada[];
  /** true quando ao menos uma questão relacionada foi encontrada. */
  relacionadas_ok: boolean;
  modelo: string;
  /** Servido do cache em memória — não exibir na UI. */
  cached: boolean;
}

export interface EditalRequest {
  /** 50–30.000 chars — conteúdo programático colado pelo usuário. */
  texto_edital: string;
  banca?: string;
  cargo?: string;
}

export interface TopicoEdital {
  disciplina: string;
  topico: string;
  prioridade: 'alta' | 'media' | 'baixa';
  termo_busca: string;
  /** null quando a contagem estoura o timeout por consulta (comum hoje). */
  questoes_disponiveis: number | null;
  timeout_consulta: boolean;
  tempo_consulta_ms: number;
  /** Filtro pronto para o question-browser: { q, banca? }. */
  filtro_sugerido: { q?: string; banca?: string };
}

export interface EditalResponse {
  resumo: string;
  banca_identificada: string | null;
  topicos: TopicoEdital[];
  tempo_total_consultas_ms: number;
  modelo: string;
}

const TIMEOUT_MS = 45_000;

function parseRetryAfter(res: Response): number | null {
  const ra = res.headers.get('Retry-After');
  if (ra === null) return null;
  const n = Number(ra.trim());
  return Number.isFinite(n) && n >= 0 ? n : null;
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  if (!API_URL) throw new AgenteError('PUBLIC_API_URL não configurada');
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch (err) {
    // Abort externo (elemento desconectado, nova submissão) propaga; o resto
    // — TimeoutError incluso — vira falha de rede para a UI.
    if (signal?.aborted) throw err;
    throw new AgenteError(err instanceof Error ? err.message : 'falha de rede');
  }
  if (!res.ok) {
    throw new AgenteError(`${path}: HTTP ${res.status}`, res.status, parseRetryAfter(res));
  }
  return (await res.json()) as T;
}

export function postExplicar(
  body: ExplicarRequest,
  signal?: AbortSignal,
): Promise<ExplicarResponse> {
  return post<ExplicarResponse>('/agente/explicar', body, signal);
}

export function postEdital(
  body: EditalRequest,
  signal?: AbortSignal,
): Promise<EditalResponse> {
  return post<EditalResponse>('/agente/edital', body, signal);
}
