/**
 * Client da API do papiro (Postgres na VM — .agents/docs/docker-postgres.md).
 *
 * `PUBLIC_API_URL` aponta para a API; sem ela os fetches lançam erro e as
 * páginas degradam para listas vazias (o build continua funcionando).
 * Aceita URL absoluta (`https://api…`) ou relativa (`/api`, reverse-proxy).
 * O shape `Questao` é o registro flat servido por GET /questoes — o mesmo
 * que `shard_to_records` emite em data/questions/.
 */

export interface Questao {
  id: string;
  banca: string;
  orgao: string;
  cargo: string;
  ano: number;
  assunto: string;
  tipo: 'certo_errado' | 'multipla_escolha';
  enunciado: string;
  alternativas: string[];
  gabarito: string;
  fonte: string;
}

export interface QuestoesPage {
  total: number;
  page: number;
  per_page: number;
  pages: number;
  items: Questao[];
}

/** Campos ficam ausentes quando /filtros é chamado com `dims=` — daí opcionais. */
export interface Filtros {
  bancas?: string[];
  orgaos?: string[];
  cargos?: string[];
  anos?: number[];
  assuntos?: string[];
}

/** Entrada de GET /filtros/{dim} — valor da faceta + contagem de questões. */
export interface Faceta {
  valor: string;
  questoes: number;
}

export type FacetDim = 'banca' | 'orgao' | 'cargo' | 'ano' | 'assunto';

export interface Evento {
  evento: string;
  banca: string;
  questoes: number;
  provas: number;
}

export interface Prova {
  evento: string;
  fonte: string;
  questoes: number;
}

export type QuestoesParams = {
  banca?: string;
  orgao?: string;
  cargo?: string;
  ano?: number | string;
  assunto?: string;
  tipo?: string;
  q?: string;
  evento?: string;
  page?: number;
  per_page?: number;
};

export const API_URL = (import.meta.env.PUBLIC_API_URL ?? '').replace(/\/+$/, '');

/** Tempo máximo de um fetch — protege o build/CI de conexões penduradas. */
const TIMEOUT_MS = 15_000;

export const EMPTY_FILTROS: Filtros = { bancas: [], orgaos: [], cargos: [], anos: [], assuntos: [] };
export const EMPTY_PAGE: QuestoesPage = { total: 0, page: 1, per_page: 20, pages: 0, items: [] };

function buildUrl(path: string, params: Record<string, unknown> = {}): string {
  // Montado à mão (não new URL()) para aceitar PUBLIC_API_URL relativa, ex. /api
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  }
  const s = qs.toString();
  return `${API_URL}${path}${s ? `?${s}` : ''}`;
}

async function get<T>(
  path: string,
  params?: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  if (!API_URL) throw new Error('PUBLIC_API_URL não configurada');
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  const res = await fetch(buildUrl(path, params), {
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export function fetchQuestoes(
  params: QuestoesParams = {},
  signal?: AbortSignal,
): Promise<QuestoesPage> {
  return get<QuestoesPage>('/questoes', params, signal);
}

export function fetchQuestao(id: string, signal?: AbortSignal): Promise<Questao> {
  return get<Questao>(`/questoes/${encodeURIComponent(id)}`, undefined, signal);
}

export function fetchFiltros(
  params: QuestoesParams & { dims?: string } = {},
  signal?: AbortSignal,
): Promise<Filtros> {
  return get<Filtros>('/filtros', params, signal);
}

/**
 * Facetas de uma dimensão (top-N por contagem). `q` busca no VALOR da faceta
 * (não no enunciado) e os demais filtros restringem a cascata — a própria
 * dimensão é excluída pelo servidor.
 */
export function fetchFacetas(
  dim: FacetDim,
  params: QuestoesParams & { limit?: number } = {},
  signal?: AbortSignal,
): Promise<Faceta[]> {
  return get<Faceta[]>(`/filtros/${dim}`, params, signal);
}

export function fetchEventos(signal?: AbortSignal): Promise<Evento[]> {
  return get<Evento[]>('/eventos', undefined, signal);
}

export function fetchProvas(evento?: string, signal?: AbortSignal): Promise<Prova[]> {
  return get<Prova[]>('/provas', evento ? { evento } : {}, signal);
}
