import {
  fetchFiltros,
  fetchQuestoes,
  type Filtros,
  type QuestoesPage,
} from '../../data/questions';
// cards inseridos dinamicamente precisam do elemento definido mesmo quando o
// SSR veio vazio (API fora no build) — senão nada importaria question-card.ts
import './question-card';
import './facet-combobox';
import {
  arquivoFonte,
  cardHtml,
  esc,
  fonteEhUrl,
  paginacaoHtml,
  plural,
} from '../templates';
import type { FacetComboboxElement } from './facet-combobox';

/**
 * <question-browser> — lista paginada de questões servida pela API.
 *
 * Busca server-side: controles disparam GET /questoes com os filtros ativos;
 * GET /filtros?dims=banca,ano repovoa os selects pequenos em cascata e os
 * <facet-combobox> (orgao/cargo/assunto) consultam /filtros/{dim} sozinhos.
 * O estado vive na URL (?banca&orgao&cargo&ano&assunto&tipo&q&evento&fonte&
 * prova&page&per_page): mudanças dão pushState, popstate re-aplica —
 * deep-link, refresh e voltar preservam tudo. `prova` é SÓ de exibição
 * (rótulo da prova em [data-prova-aviso]) — nunca vai à API.
 *
 * Contrato interno (a página fornece o markup inicial — SSR da 1ª página):
 * - `data-api-url` no elemento: base da API; sem ele o componente fica inerte
 *   (conteúdo SSR permanece).
 * - `data-per-page`: tamanho de página padrão (select [data-por-pagina] pode
 *   mudar; a URL manda nos dois).
 * - `[data-filtro="campo"]` em select ou input: banca|orgao|cargo|ano|assunto
 *   |tipo|evento|fonte (evento e fonte são hidden — vêm de links da página
 *   de provas: evento filtra o concurso, fonte a URL exata de uma prova).
 * - `input[data-q]`: busca textual no enunciado (debounce).
 * - `select[data-por-pagina]`: 20/50/100.
 * - `[data-evento-ativo]`/`[data-evento-rotulo]`/`[data-evento-nome]`/
 *   `[data-prova-aviso]`/`[data-limpar-evento]`: aviso de evento/prova
 *   filtrado + botão de limpar (limpa evento, fonte e o rótulo `prova`
 *   juntos). O nome exibido é o evento ou, em link artesanal só com
 *   `fonte=`, o nome do arquivo da URL (senão o host, senão o <strong>
 *   fica oculto); `data-prova-aviso` diz "— somente a prova {prova}"
 *   quando a URL traz `?prova=` junto de `fonte=`.
 * - `[data-lista]`: contêiner dos cards (substituído a cada fetch).
 * - `[data-contagem]`: contagem infletida ("N questões"); `[data-paginacao]`:
 *   nav de âncoras (ver templates.ts); `[data-status]`: carregando/erro.
 * - Sem parâmetros na URL, NENHUM fetch acontece na carga: o SSR já é a
 *   primeira página do estado padrão.
 *
 * O template do card vive em design/templates.ts e replica o markup de
 * QuestionCard/Alternativa/QuestionMeta — ao mudar um, mude o outro.
 */

/** Campos lidos de [data-filtro]. banca/ano vêm de /filtros?dims=; tipo é
 * select estático; evento e fonte são hidden (links da página de provas). */
const CAMPOS = ['banca', 'orgao', 'cargo', 'ano', 'assunto', 'tipo', 'evento', 'fonte'] as const;
type Campo = (typeof CAMPOS)[number];

/** Selects repovoados por GET /filtros?dims=banca,ano (os demais campos são
 * combobox assíncrono ou fixos). */
const DIMS_SELECT = ['banca', 'ano'] as const;
const DIMS_QS = DIMS_SELECT.join(',');
const PER_PAGE_PADRAO = 20;
const DEBOUNCE_MS = 300;

interface State extends Record<Campo, string> {
  page: number;
  /** Rótulo da prova — SÓ exibição ([data-prova-aviso]). Fora de CAMPOS,
   * nunca entra em paramsDe nem vai à API. */
  prova: string;
}

export class QuestionBrowserElement extends HTMLElement {
  private campos: (HTMLSelectElement | HTMLInputElement)[] = [];
  private combos: FacetComboboxElement[] = [];
  private busca: HTMLInputElement | null = null;
  private porPagina: HTMLSelectElement | null = null;
  private lista: HTMLElement | null = null;
  private contagem: HTMLElement | null = null;
  private paginacao: HTMLElement | null = null;
  private perPage = PER_PAGE_PADRAO;
  private abort: AbortController | null = null;
  private debounce = 0;

  connectedCallback() {
    if (!this.dataset.apiUrl) return; // sem API: conteúdo SSR permanece
    this.campos = [
      ...this.querySelectorAll<HTMLSelectElement | HTMLInputElement>(
        'select[data-filtro], input[data-filtro]',
      ),
    ];
    this.combos = [...this.querySelectorAll<FacetComboboxElement>('facet-combobox')];
    this.busca = this.querySelector('[data-q]');
    this.porPagina = this.querySelector('[data-por-pagina]');
    this.lista = this.querySelector('[data-lista]');
    this.contagem = this.querySelector('[data-contagem]');
    this.paginacao = this.querySelector('[data-paginacao]');

    // Estado inicial = URL (deep-link). Sem params, o SSR já é a resposta.
    const st = this.estadoDaUrl();
    this.aplicarEstado(st);
    this.atualizarContextos(st);

    this.addEventListener('change', (e) => {
      const t = e.target as HTMLElement;
      if (t.matches?.('[data-filtro]')) this.mudar(t.dataset.filtro);
      if (t.matches?.('[data-por-pagina]')) {
        this.perPage = Number(this.porPagina?.value) || PER_PAGE_PADRAO;
        this.mudar();
      }
    });
    this.busca?.addEventListener('input', () => {
      window.clearTimeout(this.debounce);
      this.debounce = window.setTimeout(() => this.mudar('q'), DEBOUNCE_MS);
    });
    // limpar zera evento E fonte de uma vez — um único change dispara o fetch
    this.querySelector('[data-limpar-evento]')?.addEventListener('click', () => {
      let alvo: HTMLElement | undefined;
      for (const c of this.campos) {
        if (c.dataset.filtro === 'evento' || c.dataset.filtro === 'fonte') {
          c.value = '';
          alvo = c;
        }
      }
      alvo?.dispatchEvent(new Event('change', { bubbles: true }));
    });
    this.paginacao?.addEventListener('click', (e) => {
      const a = (e.target as HTMLElement).closest?.('a[data-nav]');
      if (!a || a.getAttribute('aria-disabled') === 'true') return;
      e.preventDefault();
      const st2 = this.lerEstado(Number((a as HTMLElement).dataset.pagina));
      this.carregar(st2, { push: true, focar: (a as HTMLElement).dataset.nav });
      this.lista?.scrollIntoView({ block: 'start' });
    });
    window.addEventListener('popstate', this.onPop);

    // Fetch inicial só se a URL pede algo diferente do estado padrão (que o
    // SSR já renderizou) — evita o fetch duplo /questoes+/filtros na carga.
    if (this.temParams()) this.carregar(st);
  }

  disconnectedCallback() {
    window.removeEventListener('popstate', this.onPop);
  }

  private onPop = () => {
    const st = this.estadoDaUrl();
    this.aplicarEstado(st);
    this.atualizarContextos(st);
    this.carregar(st);
  };

  private temParams(): boolean {
    const p = new URLSearchParams(location.search);
    return [...CAMPOS, 'q', 'page', 'per_page'].some((k) => p.has(k));
  }

  private estadoDaUrl(): State & { q: string } {
    const p = new URLSearchParams(location.search);
    const st = this.estadoBase(Math.max(1, Number(p.get('page')) || 1));
    for (const c of CAMPOS) st[c] = p.get(c) ?? '';
    st.q = p.get('q') ?? '';
    st.prova = p.get('prova') ?? '';
    this.perPage = Number(p.get('per_page')) || Number(this.dataset.perPage) || PER_PAGE_PADRAO;
    return st;
  }

  private lerEstado(page: number): State & { q: string } {
    const st = this.estadoBase(page);
    for (const c of this.campos) {
      const campo = c.dataset.filtro as Campo | undefined;
      if (campo && (CAMPOS as readonly string[]).includes(campo)) st[campo] = c.value;
    }
    st.q = this.busca?.value.trim() ?? '';
    // `prova` não tem controle próprio — preserva o que a URL atual traz
    // (pushState ainda não aconteceu neste ponto); qsDe só a reemite com fonte.
    st.prova = new URLSearchParams(location.search).get('prova') ?? '';
    return st;
  }

  private estadoBase(page: number): State & { q: string } {
    return { banca: '', orgao: '', cargo: '', ano: '', assunto: '', tipo: '', evento: '', fonte: '', q: '', page, prova: '' };
  }

  /** Aplica o estado aos controles (deep-link, popstate). */
  private aplicarEstado(st: State & { q?: string }) {
    for (const c of this.campos) {
      const campo = c.dataset.filtro as Campo | undefined;
      if (!campo) continue;
      const v = st[campo] ?? '';
      if (c instanceof HTMLSelectElement) {
        if (v && ![...c.options].some((o) => o.value === v)) {
          c.add(new Option(v, v)); // valor de deep-link fora do SSR
        }
        c.value = v;
      } else {
        const combo = c.closest<FacetComboboxElement>('facet-combobox');
        if (combo?.setValue) combo.setValue(v);
        else c.value = v;
      }
    }
    if (this.busca && st.q !== undefined) this.busca.value = st.q;
    if (this.porPagina) this.porPagina.value = String(this.perPage);
    this.atualizarAviso(st);
  }

  /**
   * Aviso "Filtrando pelo evento/pela fonte …". Nome: o evento, ou — em link
   * artesanal só com `fonte=` — o arquivo da URL (`arquivoFonte`), o host, ou
   * nada (o <strong> se esconde e o rótulo muda para "pela fonte"). O aviso de
   * prova só aparece com `fonte` ativa e nomeia a prova quando a URL traz
   * `?prova=` (parâmetro só de exibição, emitido pelos links de /provas/).
   */
  private atualizarAviso(st: State) {
    const aviso = this.querySelector<HTMLElement>('[data-evento-ativo]');
    if (!aviso) return;
    aviso.hidden = !(st.evento || st.fonte);
    let nome = st.evento;
    if (!nome && st.fonte) {
      nome = arquivoFonte(st.fonte) ?? '';
      if (!nome && fonteEhUrl(st.fonte)) {
        try {
          nome = new URL(st.fonte).host;
        } catch {
          /* fonte malformada — sem nome, o rótulo já basta */
        }
      }
    }
    const rotulo = aviso.querySelector<HTMLElement>('[data-evento-rotulo]');
    if (rotulo) rotulo.textContent = st.evento ? 'Filtrando pelo evento' : 'Filtrando pela fonte';
    const nomeEl = aviso.querySelector<HTMLElement>('[data-evento-nome]');
    if (nomeEl) {
      nomeEl.textContent = nome;
      nomeEl.hidden = !nome;
    }
    const provaAviso = aviso.querySelector<HTMLElement>('[data-prova-aviso]');
    if (provaAviso) {
      provaAviso.hidden = !st.fonte;
      provaAviso.textContent = st.prova
        ? ` — somente a prova ${st.prova}`
        : ' — somente a prova selecionada';
    }
  }

  /** Cascata para os comboboxes: todos os filtros menos a própria dim e q
   * (q de /filtros/{dim} é busca na faceta, não no enunciado). */
  private atualizarContextos(st: State) {
    const ctx: Record<string, string | undefined> = {};
    for (const c of CAMPOS) ctx[c] = st[c] || undefined;
    for (const combo of this.combos) combo.setContext?.(ctx);
  }

  private paramsDe(st: State & { q?: string }) {
    const p: Record<string, string | number | undefined> = {};
    for (const c of CAMPOS) p[c] = st[c] || undefined;
    p.q = st.q || undefined;
    return p;
  }

  /** Querystring para URL/âncoras — omite vazios e defaults (page=1,
   * per_page=20). */
  private qsDe(st: State & { q?: string }): string {
    const p = new URLSearchParams();
    for (const c of CAMPOS) if (st[c]) p.set(c, st[c]);
    if (st.q) p.set('q', st.q);
    // prova só faz sentido nomeando uma prova filtrada por fonte — sem fonte,
    // sai da URL no próximo pushState (inclui o fluxo de limpar)
    if (st.fonte && st.prova) p.set('prova', st.prova);
    if (this.perPage !== PER_PAGE_PADRAO) p.set('per_page', String(this.perPage));
    return p.toString();
  }

  private mudar(protegido?: string) {
    this.carregar(this.lerEstado(1), { push: true, protegido });
  }

  private async carregar(
    st: State & { q?: string },
    opts: { push?: boolean; focar?: string; refeito?: boolean; protegido?: string } = {},
  ): Promise<void> {
    this.abort?.abort();
    this.abort = new AbortController();
    const sinal = this.abort.signal;
    if (this.lista) this.lista.setAttribute('aria-busy', 'true');
    this.status('Carregando…');
    try {
      const params = this.paramsDe(st);
      const [pagina, filtros] = await Promise.all([
        fetchQuestoes({ ...params, page: st.page, per_page: this.perPage }, sinal),
        fetchFiltros({ ...params, dims: DIMS_QS }, sinal),
      ]);
      if (sinal.aborted) return;
      // Cascata: se um select perdeu o valor (filtro incompatível), o estado
      // efetivo muda — refaz o fetch UMA vez com o estado pós-reset, senão a
      // página exibe "Nenhuma questão" do filtro derrubado. O campo que o
      // usuário acabou de mudar (opts.protegido) nunca é derrubado: o filtro
      // mais antigo é quem cede.
      const mudou = this.repovoar(filtros, st, opts.protegido);
      if (mudou && !opts.refeito) {
        this.aplicarEstado(st);
        return this.carregar(st, { ...opts, refeito: true });
      }
      this.atualizarAviso(st);
      this.renderLista(pagina);
      this.renderPaginacao(pagina, st, opts.focar);
      this.atualizarContextos(st);
      if (opts.push) this.pushUrl(st);
    } catch (err) {
      if (sinal.aborted) return;
      const temItens = !!this.lista?.querySelector('question-card');
      this.status(
        temItens
          ? 'API indisponível — exibindo os últimos resultados carregados.'
          : 'Não foi possível carregar as questões — API indisponível.',
      );
      if (!temItens && this.lista) {
        this.lista.innerHTML =
          '<div class="rounded-xl border border-line bg-surface p-5"><p class="text-ink-soft">Não foi possível carregar as questões — a API está indisponível no momento.</p></div>';
      }
      console.error('question-browser:', err);
    } finally {
      if (!sinal.aborted && this.lista) this.lista.removeAttribute('aria-busy');
    }
  }

  private pushUrl(st: State & { q?: string }) {
    const p = new URLSearchParams(this.qsDe(st));
    if (st.page > 1) p.set('page', String(st.page));
    const s = p.toString();
    history.pushState(null, '', location.pathname + (s ? `?${s}` : ''));
  }

  private renderLista(pagina: QuestoesPage) {
    if (this.contagem) {
      this.contagem.textContent = plural(pagina.total, 'questão', 'questões');
    }
    if (!this.lista) return;
    this.lista.innerHTML =
      pagina.items.map(cardHtml).join('') ||
      '<div class="rounded-xl border border-line bg-surface p-5"><p class="text-ink-soft">Nenhuma questão encontrada com esses filtros.</p></div>';
    this.status('');
  }

  private renderPaginacao(pagina: QuestoesPage, st: State, focar?: string) {
    if (!this.paginacao) return;
    this.paginacao.innerHTML = paginacaoHtml(pagina.page, pagina.pages, this.qsDe(st));
    // Foco: o botão clicado foi destruído pelo innerHTML — reaplica no
    // equivalente novo; sem equivalente, cai no indicador da página atual.
    if (focar) {
      const alvo =
        this.paginacao.querySelector<HTMLElement>(
          `a[data-nav="${focar}"]:not([aria-disabled])`,
        ) ?? this.paginacao.querySelector<HTMLElement>('[data-atual]');
      alvo?.focus();
    }
  }

  /** Repovoa os selects pequenos com a cascata de /filtros. Retorna true se
   * algum valor foi derrubado (estado efetivo mudou → refazer o fetch).
   * `protegido` — o campo recém-mudado — mantém o valor mesmo fora da lista
   * (a opção é injetada); são os filtros mais antigos que cedem. */
  private repovoar(f: Filtros, st: State, protegido?: string): boolean {
    const listas: Partial<Record<Campo, (string | number)[] | undefined>> = {
      banca: f.bancas,
      ano: f.anos,
    };
    let mudou = false;
    for (const s of this.campos) {
      if (!(s instanceof HTMLSelectElement)) continue;
      const campo = s.dataset.filtro as Campo;
      if (!(DIMS_SELECT as readonly string[]).includes(campo)) continue;
      const valores = listas[campo];
      if (!valores) continue;
      const atual = st[campo];
      const placeholder =
        s.querySelector('option[value=""]')?.outerHTML ?? '<option value=""></option>';
      s.innerHTML =
        placeholder +
        valores.map((v) => `<option value="${esc(String(v))}">${esc(String(v))}</option>`).join('');
      if (atual && !valores.map(String).includes(atual)) {
        if (campo === protegido) {
          s.add(new Option(atual, atual));
          s.value = atual;
          continue;
        }
        st[campo] = '';
        s.value = '';
        mudou = true;
      } else {
        s.value = atual;
      }
    }
    return mudou;
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
