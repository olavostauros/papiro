import { AgenteError, postEdital, type EditalResponse, type TopicoEdital } from '../../data/agente';
import { BASE, esc, esperaHumana, plural } from '../templates';

/**
 * <edital-cruzamento> — "Cruzar o edital" na página /edital/, servido por
 * POST /agente/edital. O usuário cola o conteúdo programático (50–30.000
 * chars, validado no cliente antes do POST) e recebe tópicos com contagem
 * de questões e CTA para o question-browser filtrado (/?q=…&banca=… — o
 * filtro_sugerido do servidor usa os mesmos nomes de parâmetro da URL).
 *
 * Contrato:
 * - `data-api-url` — sem ela o [data-painel] se esconde (a página já
 *   renderiza EmptyState quando PUBLIC_API_URL está ausente). Sem JS, a nota
 *   de [data-sem-js] permanece.
 * - `form[data-form]` — textarea [data-texto] (contador [data-contador]
 *   "{n}/30.000"), inputs [data-banca]/[data-cargo] opcionais, submit
 *   [data-acao] e [data-erro] (role=alert) de validação.
 * - `[data-status]` (role=status) — [data-status-msg] + [data-status-aux]
 *   durante a chamada (pode levar ~40 s).
 * - `[data-resultado]` — resumo + lista de tópicos, ou erro (role=alert +
 *   [data-retry] quando cabível). O foco é movido para o resultado.
 *
 * questoes_disponiveis null (timeout da contagem no Postgres) é comum hoje —
 * a microcopy avisa e o CTA continua funcionando. Seção vazia some; todo
 * campo do LLM/dataset passa por esc() antes do innerHTML.
 */

const RETRY_CLS =
  'mt-2 inline-flex cursor-pointer items-center justify-center rounded-md px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-surface focus-visible:focus-ring';
const CTA_CLS =
  'inline-flex items-center justify-center rounded-md border border-line-strong bg-surface px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-accent-soft focus-visible:focus-ring';
const BADGE_BASE = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium';
const BADGE_SOFT = `${BADGE_BASE} bg-accent-soft text-accent`;
const BADGE_OUTLINE = `${BADGE_BASE} border border-line text-ink-soft`;

const PRIORIDADES: Record<string, { rotulo: string; cls: string }> = {
  alta: { rotulo: 'Prioridade alta', cls: BADGE_SOFT },
  media: { rotulo: 'Prioridade média', cls: BADGE_OUTLINE },
  baixa: { rotulo: 'Prioridade baixa', cls: BADGE_OUTLINE },
};

const MIN_CHARS = 50;
const MAX_CHARS = 30_000;

function paras(t: string): string {
  return t
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => `<p>${esc(s)}</p>`)
    .join('');
}

function contagemTopico(t: TopicoEdital): string {
  if (t.questoes_disponiveis === null || t.questoes_disponiveis === undefined) {
    return 'Contagem indisponível no momento — o filtro para as questões funciona mesmo assim.';
  }
  if (t.questoes_disponiveis === 0) return 'Nenhuma questão no acervo';
  return `${plural(t.questoes_disponiveis, 'questão', 'questões')} no acervo`;
}

function topicoHtml(t: TopicoEdital): string {
  const pr = PRIORIDADES[t.prioridade] ?? PRIORIDADES.media;
  const p = new URLSearchParams();
  if (t.filtro_sugerido?.q) p.set('q', t.filtro_sugerido.q);
  if (t.filtro_sugerido?.banca) p.set('banca', t.filtro_sugerido.banca);
  const qs = p.toString();
  return (
    `<li class="rounded-lg border border-line p-4">` +
    `<div class="flex flex-wrap items-center gap-x-3 gap-y-1">` +
    `<p class="text-sm font-medium text-ink">${esc(t.topico)}</p>` +
    `<span class="${pr.cls}">${pr.rotulo}</span>` +
    `</div>` +
    `<p class="mt-0.5 text-xs text-ink-soft">${esc(t.disciplina)}</p>` +
    `<p class="mt-2 text-sm text-ink-soft">${esc(contagemTopico(t))}</p>` +
    `<p class="mt-3"><a href="${BASE}/${qs ? `?${qs}` : ''}" class="${CTA_CLS}" aria-label="Resolver as questões — ${esc(t.topico)}">Resolver as questões</a></p>` +
    `</li>`
  );
}

export class EditalCruzamentoElement extends HTMLElement {
  private painel: HTMLElement | null = null;
  private texto: HTMLTextAreaElement | null = null;
  private contador: HTMLElement | null = null;
  private banca: HTMLInputElement | null = null;
  private cargo: HTMLInputElement | null = null;
  private acao: HTMLButtonElement | null = null;
  private erro: HTMLElement | null = null;
  private statusBox: HTMLElement | null = null;
  private statusMsg: HTMLElement | null = null;
  private statusAux: HTMLElement | null = null;
  private resultado: HTMLElement | null = null;
  private abort: AbortController | null = null;

  connectedCallback() {
    this.painel = this.querySelector('[data-painel]');
    if (!this.dataset.apiUrl) {
      if (this.painel) this.painel.hidden = true;
      return;
    }
    const semJs = this.querySelector<HTMLElement>('[data-sem-js]');
    const form = this.querySelector<HTMLFormElement>('form[data-form]');
    this.texto = this.querySelector('[data-texto]');
    this.contador = this.querySelector('[data-contador]');
    this.banca = this.querySelector('[data-banca]');
    this.cargo = this.querySelector('[data-cargo]');
    this.acao = this.querySelector('[data-acao]');
    this.erro = this.querySelector('[data-erro]');
    this.statusBox = this.querySelector('[data-status]');
    this.statusMsg = this.querySelector('[data-status-msg]');
    this.statusAux = this.querySelector('[data-status-aux]');
    this.resultado = this.querySelector('[data-resultado]');
    if (semJs) semJs.hidden = true;
    if (form) {
      form.hidden = false;
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.cruzar();
      });
    }
    this.texto?.addEventListener('input', () => {
      if (this.contador) {
        this.contador.textContent = `${this.texto!.value.length.toLocaleString('pt-BR')}/30.000`;
      }
      this.mostrarErro('');
    });
    this.resultado?.addEventListener('click', (e) => {
      if ((e.target as HTMLElement).closest?.('[data-retry]')) this.cruzar();
    });
  }

  disconnectedCallback() {
    this.abort?.abort();
  }

  private async cruzar() {
    const texto = (this.texto?.value ?? '').trim();
    if (texto.length < MIN_CHARS) {
      this.mostrarErro(
        'Cole o conteúdo programático — o texto precisa de pelo menos 50 caracteres.',
      );
      this.texto?.focus();
      return;
    }
    if (texto.length > MAX_CHARS) {
      this.mostrarErro(
        'O texto passa de 30.000 caracteres — cole apenas o conteúdo programático do edital.',
      );
      this.texto?.focus();
      return;
    }
    this.mostrarErro('');
    this.abort?.abort();
    this.abort = new AbortController();
    this.carregando(true);
    try {
      const res = await postEdital(
        {
          texto_edital: texto,
          banca: this.banca?.value.trim() || undefined,
          cargo: this.cargo?.value.trim() || undefined,
        },
        this.abort.signal,
      );
      this.renderResultado(res);
    } catch (err) {
      if (!(err instanceof AgenteError)) return; // abort externo
      this.renderErro(err);
    } finally {
      this.carregando(false);
    }
  }

  private carregando(on: boolean) {
    if (this.acao) this.acao.disabled = on;
    this.painel?.toggleAttribute('aria-busy', on);
    this.setStatus(
      on ? 'O agente está lendo o edital…' : '',
      on ? 'Isso pode levar até 40 segundos — inclui a contagem de questões no acervo.' : '',
    );
  }

  private setStatus(msg: string, aux = '') {
    if (this.statusMsg) this.statusMsg.textContent = msg;
    if (this.statusAux) this.statusAux.textContent = aux;
    if (this.statusBox) this.statusBox.hidden = !msg;
  }

  private mostrarErro(msg: string) {
    if (this.erro) {
      this.erro.textContent = msg;
      this.erro.hidden = !msg;
    }
  }

  private renderErro(err: AgenteError) {
    let msg: string;
    let retry = false;
    switch (err.status) {
      case 422:
        msg = 'O conteúdo programático precisa ter entre 50 e 30.000 caracteres.';
        break;
      case 429:
        msg = `Limite de uso do agente atingido — tente novamente em ${esperaHumana(err.retryAfter)}.`;
        break;
      case 503:
        msg = 'O agente está indisponível no momento — o restante do site segue funcionando.';
        retry = true;
        break;
      case 0:
        msg = 'Não foi possível contatar o agente — verifique a conexão e tente novamente.';
        retry = true;
        break;
      default:
        msg = 'Não foi possível cruzar o edital — tente novamente.';
    }
    if (!this.resultado) return;
    this.resultado.innerHTML =
      `<div role="alert" class="rounded-lg border border-danger-line bg-danger-soft p-4">` +
      `<p class="text-sm font-medium text-danger">${esc(msg)}</p>` +
      (retry
        ? `<button type="button" data-retry class="${RETRY_CLS}">Tentar novamente</button>`
        : '') +
      `</div>`;
  }

  private renderResultado(res: EditalResponse) {
    if (!this.resultado) return;
    const partes: string[] = ['<div tabindex="-1" data-inner>'];
    if (res.resumo.trim()) {
      partes.push(
        `<section><h2 class="text-sm font-medium text-ink">Resumo</h2>` +
          `<div class="mt-1 space-y-2 text-sm text-ink-soft">${paras(res.resumo)}</div></section>`,
      );
    }
    if (res.banca_identificada?.trim()) {
      partes.push(
        `<p class="mt-3 text-sm text-ink-soft">Banca identificada: ${esc(res.banca_identificada)} — aplicada aos filtros dos tópicos.</p>`,
      );
    }
    partes.push('<h2 class="mt-5 text-sm font-medium text-ink">Tópicos do edital</h2>');
    if (res.topicos.length) {
      partes.push(
        `<ul class="mt-3 space-y-3">${res.topicos.map(topicoHtml).join('')}</ul>`,
      );
    } else {
      partes.push(
        `<p class="mt-2 text-sm text-ink-soft">O agente não extraiu tópicos deste texto — confira se o trecho colado é o conteúdo programático do edital e tente novamente.</p>`,
      );
    }
    const modelo = res.modelo && res.modelo !== 'nenhum' ? ` · modelo ${esc(res.modelo)}` : '';
    partes.push(
      `<p class="mt-5 border-t border-line pt-3 text-xs text-ink-faint">Leitura gerada por inteligência artificial — o conteúdo programático que vale é o do edital oficial da banca.${modelo}</p>`,
    );
    partes.push('</div>');
    this.resultado.innerHTML = partes.join('');
    this.resultado.querySelector<HTMLElement>('[data-inner]')?.focus();
  }
}

if (!customElements.get('edital-cruzamento')) {
  customElements.define('edital-cruzamento', EditalCruzamentoElement);
}
