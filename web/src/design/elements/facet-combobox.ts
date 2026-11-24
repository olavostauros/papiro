import { fetchFacetas, type Faceta, type FacetDim } from '../../data/questions';
import { esc } from '../templates';

/**
 * <facet-combobox> — combobox de faceta para dimensões grandes demais para um
 * <select> (cargo: 2.6k valores; orgao/assunto: centenas). Busca assíncrona
 * em GET /filtros/{dim}?q=&limit= com debounce, alimentando um <datalist>
 * nativo (combobox acessível de graça: setas, leitor de tela, sem popup
 * customizado).
 *
 * Contrato:
 * - markup vem de FacetCombobox.astro: input[list][data-busca] visível,
 *   input[type=hidden][data-filtro] com o valor EFETIVO (lido por
 *   <question-browser> como qualquer outro [data-filtro]) e <datalist>.
 * - Escolher uma faceta válida grava o valor no hidden e dispara `change`
 *   com bubbles — o browser escuta por delegação. Texto que não casa com
 *   faceta nenhuma não vira filtro; ao sair do campo (change) o input volta
 *   a exibir o valor efetivo.
 * - `setContext(params)` — chamado pelo <question-browser> a cada mudança de
 *   filtro: os demais filtros ativos entram na query (cascata). O valor já
 *   escolhido NÃO é limpo automaticamente quando deixa de ser válido — com
 *   top-N por contagem não dá para provar ausência; o usuário limpa no campo.
 * - `setValue(v)` — aplica valor sem disparar change (deep-link/popstate).
 * - URL da API vem do [data-api-url] ancestral (<question-browser>); sem ela
 *   o elemento fica inerte.
 */

const DEBOUNCE_MS = 250;
const LIMITE = 50;

export class FacetComboboxElement extends HTMLElement {
  private input: HTMLInputElement | null = null;
  private efetivo: HTMLInputElement | null = null;
  private datalist: HTMLDataListElement | null = null;
  private ctx: Record<string, string | undefined> = {};
  private cache: Faceta[] | null = null;
  private carregou = false;
  private debounce = 0;
  private abort: AbortController | null = null;

  connectedCallback() {
    this.input = this.querySelector('input[data-busca]');
    this.efetivo = this.querySelector('input[data-filtro]');
    this.datalist = this.querySelector('datalist');
    if (!this.input || !this.efetivo || !this.datalist) return;
    this.input.addEventListener('input', () => this.onInput());
    this.input.addEventListener('change', () => this.onCommit());
    this.input.addEventListener('focus', () => this.sugestoes());
  }

  get dim(): FacetDim | '' {
    return (this.efetivo?.dataset.filtro ?? '') as FacetDim | '';
  }

  get value(): string {
    return this.efetivo?.value ?? '';
  }

  /** Valor efetivo sem disparar change — usado por deep-link/popstate. */
  setValue(v: string) {
    if (!this.efetivo || !this.input) return;
    this.efetivo.value = v;
    this.input.value = v;
  }

  /** Cascata: filtros ativos (exceto a própria dim — a API já a exclui). */
  setContext(ctx: Record<string, string | undefined>) {
    this.ctx = { ...ctx };
    this.carregou = false; // sugestões passam a refletir o novo contexto
  }

  private apiUrl(): string {
    return (
      this.dataset.apiUrl ??
      this.closest<HTMLElement>('[data-api-url]')?.dataset.apiUrl ??
      ''
    );
  }

  private onInput() {
    const termo = this.input!.value;
    if (!termo) {
      this.aplicar('');
      return;
    }
    if (this.cache?.some((f) => f.valor === termo)) {
      this.aplicar(termo); // casou com uma faceta já carregada — aplica na hora
      return;
    }
    window.clearTimeout(this.debounce);
    this.debounce = window.setTimeout(() => this.buscar(termo), DEBOUNCE_MS);
  }

  private onCommit() {
    const termo = this.input!.value;
    if (!termo) {
      this.aplicar('');
      return;
    }
    if (this.cache?.some((f) => f.valor === termo)) {
      this.aplicar(termo);
      return;
    }
    // Só dá para invalidar quando há cache (API viva): texto que não é
    // faceta não filtra — limpa o efetivo e reexibe o valor real.
    if (this.cache) {
      this.aplicar('');
      this.input!.value = this.efetivo!.value;
    }
  }

  /** Grava o valor efetivo e avisa o <question-browser>. */
  private aplicar(v: string) {
    if (!this.efetivo || this.efetivo.value === v) return;
    this.efetivo.value = v;
    this.efetivo.dispatchEvent(new Event('change', { bubbles: true }));
  }

  private sugestoes() {
    if (!this.carregou) this.buscar('');
  }

  private async buscar(termo: string) {
    const dim = this.dim;
    const apiUrl = this.apiUrl();
    if (!dim || !apiUrl) return;
    this.abort?.abort();
    this.abort = new AbortController();
    const sinal = this.abort.signal;
    try {
      const facetas = await fetchFacetas(
        dim,
        { ...this.ctx, q: termo || undefined, limit: LIMITE },
        sinal,
      );
      if (sinal.aborted) return;
      this.carregou = true;
      this.cache = facetas;
      this.datalist!.innerHTML = facetas
        .map(
          (f) =>
            `<option value="${esc(f.valor)}" label="${esc(`${f.valor} — ${f.questoes.toLocaleString('pt-BR')} questões`)}"></option>`,
        )
        .join('');
      // Termo digitado pode ter virado casamento exato com a resposta
      if (this.input!.value && facetas.some((f) => f.valor === this.input!.value)) {
        this.aplicar(this.input!.value);
      }
    } catch (err) {
      if (sinal.aborted) return;
      console.warn(`facet-combobox (${dim}):`, err);
    }
  }
}

if (!customElements.get('facet-combobox')) {
  customElements.define('facet-combobox', FacetComboboxElement);
}
