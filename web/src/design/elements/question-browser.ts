import {
  fetchFiltros,
  fetchQuestoes,
  type Filtros,
  type Questao,
  type QuestoesPage,
} from '../../data/questions';
// cards inseridos dinamicamente precisam do elemento definido mesmo quando o
// SSR veio vazio (API fora no build) — senão nada importaria question-card.ts
import './question-card';

/**
 * <question-browser> — lista paginada de questões servida pela API.
 *
 * Substitui o filtro client-side de <question-filters> (que escondia itens já
 * renderizados) por fetch server-side: selects disparam /questoes com os
 * filtros ativos e /filtros repovoa as opções em cascata.
 *
 * Contrato interno (a página fornece o markup inicial — SSR da 1ª página):
 * - `data-api-url` no elemento: base da API; sem ele o componente fica inerte
 *   (conteúdo SSR permanece).
 * - `select[data-filtro="campo"]`: banca|orgao|cargo|ano|assunto.
 * - `[data-lista]`: contêiner dos cards (substituído a cada fetch).
 * - `[data-contagem]`: total de questões do resultado.
 * - `[data-paginacao]`: nav onde o elemento injeta Anterior/Próxima + status.
 *
 * O template do card replica o markup de QuestionCard/Alternativa/QuestionMeta
 * (components/) — inclusive o contrato data-* lido por <question-card>
 * (gabarito, gabarito-texto, opcao, ver-gabarito, resultado). Ao mudar um,
 * mudar o outro: o elemento <question-card> já cuida da interação de qualquer
 * markup inserido que siga o contrato.
 */

const LETRAS = ['a', 'b', 'c', 'd', 'e'];

const CHECK_SVG =
  '<svg class="ml-auto hidden size-4 group-data-[state=correct]:inline" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5" /></svg>';
const X_SVG =
  '<svg class="ml-auto hidden size-4 group-data-[state=wrong]:inline" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>';

const ALTERNATIVA_CLS =
  'group flex w-full cursor-pointer items-baseline gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors' +
  ' border-line-strong bg-surface text-ink-soft' +
  ' enabled:hover:border-accent enabled:hover:bg-accent-soft enabled:hover:text-ink' +
  ' data-[state=selected]:border-accent data-[state=selected]:bg-accent-soft data-[state=selected]:text-ink' +
  ' data-[state=correct]:border-success-line data-[state=correct]:bg-success-soft data-[state=correct]:text-success' +
  ' data-[state=wrong]:border-danger-line data-[state=wrong]:bg-danger-soft data-[state=wrong]:text-danger' +
  ' data-[state=dim]:opacity-60 focus-visible:focus-ring' +
  ' disabled:cursor-default aria-disabled:pointer-events-none';

const BOTAO_CLS =
  'inline-flex cursor-pointer items-center justify-center rounded-md font-medium transition-colors focus-visible:focus-ring px-3 py-1.5 text-xs text-accent hover:bg-accent-soft';
const PAG_CLS =
  'inline-flex cursor-pointer items-center justify-center rounded-md font-medium transition-colors focus-visible:focus-ring px-3 py-1.5 text-xs border border-line-strong bg-surface text-ink hover:bg-accent-soft disabled:cursor-default disabled:opacity-50';
const LINK_CLS =
  'rounded-sm text-ink-soft transition-colors hover:text-ink focus-visible:focus-ring underline decoration-line underline-offset-2 ml-auto';

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function gabaritoTexto(q: Questao): string {
  return q.tipo === 'certo_errado'
    ? q.gabarito === 'certo'
      ? 'Certo'
      : 'Errado'
    : `Alternativa ${q.gabarito.toUpperCase()}`;
}

function cardHtml(q: Questao): string {
  const ce = q.tipo === 'certo_errado';
  const aria = esc(`Questão — ${q.banca}, ${q.cargo}, ${q.ano}`);
  const opcoes = q.alternativas
    .map((alt, i) => {
      const valor = ce ? alt.toLowerCase() : LETRAS[i];
      const letra = ce ? '' : `<span class="font-medium text-ink-faint group-data-[state=correct]:text-success group-data-[state=wrong]:text-danger">${LETRAS[i].toUpperCase()})</span>`;
      return `<button type="button" role="radio" aria-checked="false" data-opcao="${esc(valor)}" class="${ALTERNATIVA_CLS}${ce ? ' justify-center' : ''}">${letra}<span>${esc(alt)}</span>${CHECK_SVG}${X_SVG}</button>`;
    })
    .join('');
  const meta = `<p class="flex flex-wrap gap-x-2 gap-y-1 text-xs text-ink-soft"><span class="font-medium text-ink">${esc(q.banca)}</span><span aria-hidden="true">·</span><span>${esc(q.orgao)}</span><span aria-hidden="true">·</span><span>${esc(q.cargo)}</span><span aria-hidden="true">·</span><span>${q.ano}</span>${
    q.assunto
      ? `<span class="ml-auto inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-accent-soft text-accent">${esc(q.assunto)}</span>`
      : ''
  }</p>`;
  return `<question-card data-banca="${esc(q.banca)}" data-orgao="${esc(q.orgao)}" data-cargo="${esc(q.cargo)}" data-ano="${q.ano}" data-assunto="${esc(q.assunto)}" data-gabarito="${esc(q.gabarito)}" data-gabarito-texto="${esc(gabaritoTexto(q))}" data-filter-item><article class="rounded-xl border border-line bg-surface p-5" aria-label="${aria}">${meta}<p id="enunciado-${esc(q.id)}" class="mt-3 font-serif text-base leading-relaxed sm:text-lg">${esc(q.enunciado)}</p><div class="mt-3 grid gap-1.5${ce ? ' grid-cols-2' : ''}" role="radiogroup" aria-labelledby="enunciado-${esc(q.id)}">${opcoes}</div><div class="mt-4 flex flex-wrap items-center gap-4 text-sm"><button class="${BOTAO_CLS}" type="button" data-ver-gabarito>Ver gabarito</button><p data-resultado role="status" class="hidden font-medium"></p><a href="${esc(q.fonte)}" class="${LINK_CLS}" aria-label="Fonte oficial — ${esc(q.banca)}, ${esc(q.cargo)}, ${q.ano}">Fonte oficial</a></div></article></question-card>`;
}

const CAMPOS = ['banca', 'orgao', 'cargo', 'ano', 'assunto'] as const;
type Campo = (typeof CAMPOS)[number];

interface State extends Record<Campo, string> {
  page: number;
}

export class QuestionBrowserElement extends HTMLElement {
  private selects: NodeListOf<HTMLSelectElement> | [] = [];
  private lista: HTMLElement | null = null;
  private contagem: HTMLElement | null = null;
  private paginacao: HTMLElement | null = null;
  private perPage = 20;
  private abort: AbortController | null = null;

  connectedCallback() {
    if (!this.dataset.apiUrl) return; // sem API: conteúdo SSR permanece
    this.selects = this.querySelectorAll('select[data-filtro]');
    this.lista = this.querySelector('[data-lista]');
    this.contagem = this.querySelector('[data-contagem]');
    this.paginacao = this.querySelector('[data-paginacao]');
    this.perPage = Number(this.dataset.perPage) || 20;
    this.selects.forEach((s) =>
      s.addEventListener('change', () => this.carregar(this.lerEstado(1))),
    );
    this.carregar(this.lerEstado(1), { manterSsr: true });
  }

  private lerEstado(page: number): State {
    const st: State = { banca: '', orgao: '', cargo: '', ano: '', assunto: '', page };
    this.selects.forEach((s) => {
      const campo = s.dataset.filtro as Campo | undefined;
      if (campo && CAMPOS.includes(campo)) st[campo] = s.value;
    });
    return st;
  }

  private async carregar(st: State, opts: { manterSsr?: boolean } = {}) {
    this.abort?.abort();
    this.abort = new AbortController();
    const sinal = this.abort.signal;
    if (this.lista) this.lista.setAttribute('aria-busy', 'true');
    this.status('Carregando…');
    try {
      const [pagina, filtros] = await Promise.all([
        fetchQuestoes({ ...st, ano: st.ano || undefined, per_page: this.perPage }, sinal),
        fetchFiltros({ ...st, ano: st.ano || undefined }, sinal),
      ]);
      if (sinal.aborted) return;
      this.renderLista(pagina);
      this.renderPaginacao(pagina, st);
      this.repovoar(filtros, st);
    } catch (err) {
      if (sinal.aborted) return;
      const temItens = !!this.lista?.querySelector('question-card');
      if (!temItens || !opts.manterSsr) {
        this.status('Não foi possível carregar as questões — API indisponível.');
        if (!temItens && this.lista) this.lista.innerHTML = '';
      } else {
        this.status(''); // SSR do build permanece
      }
      console.error('question-browser:', err);
    } finally {
      if (!sinal.aborted && this.lista) this.lista.removeAttribute('aria-busy');
    }
  }

  private renderLista(pagina: QuestoesPage) {
    if (this.contagem) this.contagem.textContent = String(pagina.total);
    if (!this.lista) return;
    this.lista.innerHTML =
      pagina.items.map(cardHtml).join('') ||
      '<div class="rounded-xl border border-line bg-surface p-5"><p class="text-ink-soft">Nenhuma questão encontrada com esses filtros.</p></div>';
    this.status('');
  }

  private renderPaginacao(pagina: QuestoesPage, st: State) {
    if (!this.paginacao) return;
    if (pagina.pages <= 1) {
      this.paginacao.innerHTML = '';
      return;
    }
    this.paginacao.innerHTML =
      `<button type="button" class="${PAG_CLS}" data-pag="-1"${st.page <= 1 ? ' disabled' : ''}>Anterior</button>` +
      `<span class="text-sm text-ink-soft">Página ${pagina.page} de ${pagina.pages}</span>` +
      `<button type="button" class="${PAG_CLS}" data-pag="1"${st.page >= pagina.pages ? ' disabled' : ''}>Próxima</button>`;
    this.paginacao.querySelectorAll('button[data-pag]').forEach((b) =>
      b.addEventListener('click', () => {
        this.carregar(this.lerEstado(st.page + Number((b as HTMLElement).dataset.pag)));
        this.lista?.scrollIntoView({ block: 'start' });
      }),
    );
  }

  private repovoar(f: Filtros, st: State) {
    const listas: Record<string, (string | number)[]> = {
      banca: f.bancas,
      orgao: f.orgaos,
      cargo: f.cargos,
      ano: f.anos,
      assunto: f.assuntos,
    };
    this.selects.forEach((s) => {
      const campo = s.dataset.filtro as Campo;
      const valores = listas[campo];
      if (!valores) return;
      const atual = st[campo];
      const placeholder = s.querySelector('option[value=""]')?.outerHTML ?? '<option value=""></option>';
      s.innerHTML =
        placeholder + valores.map((v) => `<option value="${esc(String(v))}">${esc(String(v))}</option>`).join('');
      s.value = valores.map(String).includes(atual) ? atual : '';
    });
  }

  private status(msg: string) {
    const el = this.querySelector<HTMLElement>('[data-status]');
    if (el) {
      el.textContent = msg;
      el.classList.toggle('hidden', !msg);
    }
  }
}

if (!customElements.get('question-browser')) {
  customElements.define('question-browser', QuestionBrowserElement);
}
