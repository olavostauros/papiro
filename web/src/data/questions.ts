/**
 * Client da API do papiro (Postgres na VM — .agents/docs/docker-postgres.md).
 *
 * `PUBLIC_API_URL` aponta para a API; sem ela os fetches lançam erro e as
 * páginas degradam para listas vazias (o build continua funcionando).
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

export interface Filtros {
  bancas: string[];
  orgaos: string[];
  cargos: string[];
  anos: number[];
  assuntos: string[];
}

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
  page?: number;
  per_page?: number;
};

export const API_URL = (import.meta.env.PUBLIC_API_URL ?? '').replace(/\/+$/, '');

export const EMPTY_FILTROS: Filtros = { bancas: [], orgaos: [], cargos: [], anos: [], assuntos: [] };
export const EMPTY_PAGE: QuestoesPage = { total: 0, page: 1, per_page: 20, pages: 0, items: [] };

function buildUrl(path: string, params: Record<string, unknown> = {}): string {
  const url = new URL(`${API_URL}${path}`);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
  }
  return url.toString();
}

async function get<T>(
  path: string,
  params?: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  if (!API_URL) throw new Error('PUBLIC_API_URL não configurada');
  const res = await fetch(buildUrl(path, params), { signal });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export function fetchQuestoes(
  params: QuestoesParams = {},
  signal?: AbortSignal,
): Promise<QuestoesPage> {
  return get<QuestoesPage>('/questoes', params, signal);
}

export function fetchQuestao(id: string): Promise<Questao> {
  return get<Questao>(`/questoes/${encodeURIComponent(id)}`);
}

export function fetchFiltros(
  params: QuestoesParams = {},
  signal?: AbortSignal,
): Promise<Filtros> {
  return get<Filtros>('/filtros', params, signal);
}

export function fetchEventos(): Promise<Evento[]> {
  return get<Evento[]>('/eventos');
}

export function fetchProvas(evento?: string): Promise<Prova[]> {
  return get<Prova[]>('/provas', evento ? { evento } : {});
}
