import { AgenteError, postExplicar, type ExplicarResponse } from '../../data/agente';
import {
  BASE,
  esc,
  esperaHumana,
  fonteEhUrl,
  H2_CLS,
  LINK_CLS,
  paras,
  RETRY_CLS,
  rotuloFonte,
} from '../templates';

/**
 * <questao-explicar> — "Explicar a questão", servido por POST
 * /agente/explicar. Dois modos de hospedagem:
 *
 * - MODO PÁGINA — bloco próprio dentro de <questao-view> (página /questao/):
 *   o [data-painel] fica sempre visível, com a nota [data-sem-js] trocada
 *   pelo [data-form] quando o JS sobe.
 * - MODO CARD — embutido num <question-card> (index/question-browser): um
 *   toggle disclosure [data-explicar-toggle] no rodapé do card (nasce
 *   `hidden` e fora deste elemento) abre/fecha o [data-painel], que nasce
 *   recolhido (`hidden` + aria-expanded/aria-controls apontando para
 *   `explicar-{id}`). Sem JS, toggle e painel ficam ocultos — o card segue
 *   íntegro.
 *
 * Resolução de contexto (válida nos dois modos):
 * - questão: `data-questao-id` no elemento → `data-id` do <question-card>
 *   ancestral → `?id=` da URL.
 * - API: `data-api-url` no elemento ou no ancestral mais próximo que o
 *   carregue (<question-browser>, <questao-view>) — cobre SSR e cards
 *   renderidos no cliente. Sem id ou sem API, toggle+painel ficam ocultos.
 * - resposta_usuario: opção marcada ([data-opcao][aria-checked="true"]) no
 *   escopo `closest('questao-view') ?? closest('question-card') ?? this`.
 *
 * DEDUP: um <questao-explicar> embutido num card que está DENTRO de
 * <questao-view> fica oculto e inerte — a página /questao/ já tem seu
 * painel próprio (o cardHtml é compartilhado entre os dois).
 *
 * Contrato interno (igual nos dois modos):
 * - `[data-form]` — textarea [data-duvida] (máx. 500, contador [data-contador]
 *   "{n}/500"), botão [data-acao] e [data-erro] (role=alert) de validação.
 * - `[data-status]` (role=status) — [data-status-msg] + [data-status-aux]
 *   durante a chamada (pode levar ~30 s).
 * - `[data-resultado]` — explicação seccionada, aviso fixo de anulada/
 *   material-base ausente (texto ou imagem/material visual), ou erro
 *   (role=alert + [data-retry] quando cabível). O foco é movido para o
 *   resultado ao renderizar.
 *
 * Com acertou=false e os campos por_que_parecia_certa + topico_para_revisar
 * preenchidos, o modo diagnóstico aparece antes da Explicação. Questões
 * relacionadas só entram quando relacionadas_ok=true e há itens. Seções vazias
 * são omitidas (armadilha "", pontos [], disciplina "", modelo "nenhum");
 * `cached` nunca aparece. Todo campo do LLM/dataset passa por esc() antes do
 * innerHTML.
 */

const RESOLVER_CLS =
  'inline-flex items-center justify-center rounded-md px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent-soft focus-visible:focus-ring';

const MATERIAL_AUSENTE_COPY = {
  texto: {
    titulo: 'Texto-base ausente',
    corpo:
      'Esta questão remete a um texto-base externo que não está no recorte do acervo. O gabarito oficial está confirmado, mas a justificativa depende do texto — consulte a fonte oficial.',
  },
  imagem: {
    titulo: 'Material visual ausente',
    corpo:
      'Esta questão depende de material visual (figura, gráfico, tabela ou imagem) disponível apenas no caderno oficial da prova. O gabarito oficial está confirmado, mas a justificativa depende desse material — consulte a fonte oficial.',
  },
} as const;

const DIAGNOSTICO_COPY = {
  titulo: 'Diagnóstico do erro',
  topico: 'Tópico para revisar',
} as const;

/** Gabarito do acervo → mesma inflexão do card ("Certo"/"Errado"/"Alternativa X"). */
function gabaritoRotulo(g: string): string {
  const v = g.trim().toLowerCase();
  if (v === 'certo') return 'Certo';
  if (v === 'errado') return 'Errado';
  if (/^[a-e]$/.test(v)) return `Alternativa ${v.toUpperCase()}`;
  return g; // 'anulada' e afins não chegam à linha de gabarito
}

function fonteHtml(fonte: string, contexto: string): string {
  if (!fonteEhUrl(fonte)) return '<span class="text-ink-faint">Fonte indisponível</span>';
  const rotulo = rotuloFonte(fonte);
  return `<a href="${esc(fonte)}" class="${LINK_CLS}" aria-label="${esc(`${rotulo} — ${contexto}`)}">${rotulo}</a>`;
}

function secao(titulo: string, corpo: string): string {
  return `<section class="mt-4"><h2 class="${H2_CLS}">${titulo}</h2><div class="mt-1 space-y-1 text-sm text-ink-soft">${corpo}</div></section>`;
}

/** Modo diagnóstico — só com erro do usuário e os dois campos preenchidos. */
function diagnosticoHtml(res: ExplicarResponse): string {
  const porQue = (res.por_que_parecia_certa || '').trim();
  const topico = (res.topico_para_revisar || '').trim();
  if (res.acertou !== false || !porQue || !topico) return '';
  return (
    `<section class="mt-4 rounded-lg border border-line bg-paper p-4">` +
    `<h2 class="${H2_CLS}">${esc(DIAGNOSTICO_COPY.titulo)}</h2>` +
    `<div class="mt-2 space-y-2 text-sm text-ink-soft">${paras(porQue)}</div>` +
    `<p class="mt-3 flex flex-wrap items-center gap-2 text-sm text-ink-soft">` +
    `<span class="font-medium text-ink">${esc(DIAGNOSTICO_COPY.topico)}:</span>` +
    `<span class="inline-flex max-w-full items-center rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium break-words text-accent">${esc(topico)}</span>` +
    `</p></section>`
  );
}

export class QuestaoExplicarElement extends HTMLElement {
  private painel: HTMLElement | null = null;
  private duvida: HTMLTextAreaElement | null = null;
  private contador: HTMLElement | null = null;
  private acao: HTMLButtonElement | null = null;
  private erro: HTMLElement | null = null;
  private statusBox: HTMLElement | null = null;
  private statusMsg: HTMLElement | null = null;
  private statusAux: HTMLElement | null = null;
  private resultado: HTMLElement | null = null;
  private questaoId = '';
  private toggle: HTMLButtonElement | null = null;
  private abort: AbortController | null = null;

  connectedCallback() {
    const card = this.closest<HTMLElement>('question-card');
    this.painel = this.querySelector('[data-painel]');
    // Toggle do modo card: vive no rodapé do <question-card>, fora deste
    // elemento (também aceita um toggle interno, para reuso futuro).
    this.toggle =
      card?.querySelector<HTMLButtonElement>('[data-explicar-toggle]') ??
      this.querySelector<HTMLButtonElement>('[data-explicar-toggle]');
    // Dedup: card embutido num <questao-view> — a página já tem o painel
    // próprio; este elemento e o toggle do card ficam ocultos e inertes.
    if (card?.closest('questao-view')) {
      this.hidden = true;
      if (this.toggle) this.toggle.hidden = true;
      return;
    }
    // Id: data-questao-id → data-id do card ancestral → ?id= da URL.
    this.questaoId =
      this.dataset.questaoId ||
      card?.dataset.id ||
      new URLSearchParams(location.search).get('id') ||
      '';
    // API: data-api-url no elemento ou no ancestral mais próximo que o
    // carregue (<question-browser>, <questao-view>).
    const apiUrl = this.closest<HTMLElement>('[data-api-url]')?.dataset.apiUrl;
    // Sem questão resolvida ou sem API: painel e toggle ficam ocultos.
    if (!this.questaoId || !apiUrl) {
      if (this.painel) this.painel.hidden = true;
      if (this.toggle) this.toggle.hidden = true;
      return;
    }
    this.duvida = this.querySelector('[data-duvida]');
    this.contador = this.querySelector('[data-contador]');
    this.acao = this.querySelector('[data-acao]');
    this.erro = this.querySelector('[data-erro]');
    this.statusBox = this.querySelector('[data-status]');
    this.statusMsg = this.querySelector('[data-status-msg]');
    this.statusAux = this.querySelector('[data-status-aux]');
    this.resultado = this.querySelector('[data-resultado]');
    const semJs = this.querySelector<HTMLElement>('[data-sem-js]');
    const form = this.querySelector<HTMLElement>('[data-form]');
    if (semJs) semJs.hidden = true;
    if (form) form.hidden = false;
    this.acao?.setAttribute('aria-label', `Explicar a questão — ${this.questaoId}`);
    this.duvida?.addEventListener('input', () => {
      if (this.contador) this.contador.textContent = `${this.duvida!.value.length}/500`;
      this.mostrarErro('');
    });
    this.acao?.addEventListener('click', () => this.explicar());
    this.resultado?.addEventListener('click', (e) => {
      if ((e.target as HTMLElement).closest?.('[data-retry]')) this.explicar();
    });
    // Modo card: o toggle (que nasce hidden) vira disclosure do painel.
    if (this.toggle && this.painel) {
      this.toggle.hidden = false;
      this.toggle.addEventListener('click', () => {
        const abrir = this.painel!.hidden;
        this.painel!.hidden = !abrir;
        this.toggle!.setAttribute('aria-expanded', String(abrir));
      });
    }
  }

  disconnectedCallback() {
    this.abort?.abort();
  }

  /** Opção marcada no card da questão (escopo: página, card hospedeiro ou o próprio elemento). */
  private respostaUsuario(): string | undefined {
    const raiz = this.closest('questao-view') ?? this.closest('question-card') ?? this;
    const sel = raiz.querySelector<HTMLElement>('[data-opcao][aria-checked="true"]');
    return sel?.dataset.opcao || undefined;
  }

  private async explicar() {
    const duvida = (this.duvida?.value ?? '').trim();
    if (duvida.length > 500) {
      this.mostrarErro('A dúvida pode ter no máximo 500 caracteres.');
      this.duvida?.focus();
      return;
    }
    this.mostrarErro('');
    this.abort?.abort();
    this.abort = new AbortController();
    this.carregando(true);
    try {
      const res = await postExplicar(
        {
          questao_id: this.questaoId,
          resposta_usuario: this.respostaUsuario(),
          duvida: duvida || undefined,
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
    if (this.duvida) this.duvida.disabled = on;
    this.painel?.toggleAttribute('aria-busy', on);
    this.setStatus(
      on ? 'O agente está lendo a questão…' : '',
      on ? 'Isso pode levar até 30 segundos.' : '',
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

  private linhaGabarito(res: ExplicarResponse, gab: string): string {
    if (res.acertou === true)
      return `<p class="font-medium text-success">Você acertou — gabarito: ${esc(gab)}</p>`;
    if (res.acertou === false)
      return `<p class="font-medium text-danger">Você errou — gabarito: ${esc(gab)}</p>`;
    return `<p class="font-medium text-accent">Gabarito oficial: ${esc(gab)}</p>`;
  }

  private renderErro(err: AgenteError) {
    let msg: string;
    let retry = false;
    switch (err.status) {
      case 404:
        msg = 'Questão não encontrada — verifique o identificador ou tente novamente mais tarde.';
        break;
      case 422:
        msg = 'A dúvida pode ter no máximo 500 caracteres.';
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
        msg = 'Não foi possível obter a explicação — tente novamente.';
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

  private relacionadaHtml(r: ExplicarResponse['questoes_relacionadas'][number]): string {
    return (
      `<li class="rounded-lg border border-line p-3">` +
      `<p class="text-xs text-ink-soft"><span class="font-medium text-ink">${esc(r.banca)}</span>` +
      `<span aria-hidden="true"> · </span>${esc(r.orgao)}` +
      `<span aria-hidden="true"> · </span>${esc(String(r.ano))}</p>` +
      `<p class="mt-1 text-sm text-ink">${esc(r.enunciado_resumo)}</p>` +
      `<p class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">` +
      `<a href="${BASE}/questao/?id=${encodeURIComponent(r.id)}" class="${RESOLVER_CLS}" aria-label="Resolver a questão — ${esc(r.id)}">Resolver</a>` +
      fonteHtml(r.fonte, r.id) +
      `</p></li>`
    );
  }

  private renderResultado(res: ExplicarResponse) {
    if (!this.resultado) return;
    const gab = gabaritoRotulo(res.gabarito_oficial);
    const fonte = fonteHtml(res.fonte, res.questao_id);

    // Avisos fixos (resposta 200 sem LLM) — não são seções nem erro.
    if (res.anulada) {
      this.resultado.innerHTML =
        `<div tabindex="-1" data-inner>` +
        `<h2 class="font-medium text-ink">Questão anulada</h2>` +
        `<p class="mt-1 text-sm text-ink-soft">A banca anulou esta questão — não há gabarito vigente nem explicação. Confira os comunicados na fonte oficial.</p>` +
        `<p class="mt-3 text-sm">${fonte}</p>` +
        `</div>`;
    } else if (res.texto_base_ausente) {
      const material =
        MATERIAL_AUSENTE_COPY[res.material_ausente === 'imagem' ? 'imagem' : 'texto'];
      this.resultado.innerHTML =
        `<div tabindex="-1" data-inner>` +
        this.linhaGabarito(res, gab) +
        `<h2 class="mt-4 font-medium text-ink">${esc(material.titulo)}</h2>` +
        `<p class="mt-1 text-sm text-ink-soft">${esc(material.corpo)}</p>` +
        `<p class="mt-3 text-sm">${fonte}</p>` +
        `</div>`;
    } else {
      const secoes: string[] = [];
      const diagnostico = diagnosticoHtml(res);
      if (diagnostico) secoes.push(diagnostico);
      if (res.explicacao.trim()) {
        secoes.push(
          `<section class="mt-4"><h2 class="${H2_CLS}">Explicação</h2>` +
            `<div class="mt-1 space-y-2 font-serif leading-relaxed">${paras(res.explicacao)}</div></section>`,
        );
      }
      if (res.armadilha_banca.trim()) {
        secoes.push(secao('Armadilha da banca', paras(res.armadilha_banca)));
      }
      if (res.conceito_chave.trim()) {
        secoes.push(secao('Conceito-chave', paras(res.conceito_chave)));
      }
      const pontos = res.pontos_chave.map((p) => p.trim()).filter(Boolean);
      if (pontos.length) {
        secoes.push(
          secao(
            'Pontos-chave',
            `<ul class="list-disc space-y-1 pl-5">${pontos.map((p) => `<li>${esc(p)}</li>`).join('')}</ul>`,
          ),
        );
      }
      if (res.relacionadas_ok === true && res.questoes_relacionadas.length) {
        secoes.push(
          secao(
            'Questões relacionadas',
            `<ul class="space-y-3">${res.questoes_relacionadas.map((r) => this.relacionadaHtml(r)).join('')}</ul>`,
          ),
        );
      }
      const disciplina = res.disciplina_inferida.trim()
        ? `<p class="mt-2 text-sm text-ink-soft">Disciplina inferida: ${esc(res.disciplina_inferida)}</p>`
        : '';
      const modelo =
        res.modelo && res.modelo !== 'nenhum' ? ` · modelo ${esc(res.modelo)}` : '';
      this.resultado.innerHTML =
        `<div tabindex="-1" data-inner>` +
        this.linhaGabarito(res, gab) +
        disciplina +
        secoes.join('') +
        `<div class="mt-5 border-t border-line pt-3 text-sm">${fonte}` +
        `<p class="mt-1 text-xs text-ink-faint">Explicação gerada por inteligência artificial — pode conter imprecisões. O gabarito é o oficial da banca; em caso de divergência, vale o PDF oficial da prova.${modelo}</p>` +
        `</div></div>`;
    }
    this.resultado.querySelector<HTMLElement>('[data-inner]')?.focus();
  }
}

if (!customElements.get('questao-explicar')) {
  customElements.define('questao-explicar', QuestaoExplicarElement);
}
