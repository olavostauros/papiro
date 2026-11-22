/**
 * O dataset não é mais empacotado no site — os shards vivem em
 * data/questions/ (raiz do repo) e são servidos por uma API na VM.
 * Até o client da API existir, este módulo exporta uma lista vazia
 * para manter as páginas compilando.
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

// TODO(api): buscar na API da VM (filtros server-side + paginação).
export const questions: Questao[] = [];

export default questions;
