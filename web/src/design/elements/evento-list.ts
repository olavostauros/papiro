import { fetchProvas, type Prova } from '../../data/questions';
import {
  BASE,
  arquivoFonte,
  esc,
  plural,
  resumoAnos,
  resumoCargos,
  tipoLabel,
} from '../templates';

/**
 * <evento-list> — lista de eventos (concursos ingeridos) na página /provas/.
 *
 * Contrato:
 * - `data-api-url` no elemento ou num ancestral — sem ela a busca textual
 *   continua funcionando (filtra o já renderizado), só as provas por evento
 *   ficam indisponíveis.
 * - `input[data-busca]` — filtra itens no cliente (sem fetch), ignorando
 *   acentos, sobre o texto de `data-busca-texto` (slug, banca, órgãos,
 *   cargos e anos do evento).
 * - `[data-evento-item]` — item (li) de um evento; `data-busca-texto` guarda
 *   o texto pesquisável já normalizado.
 * - `details[data-evento]` + `[data-provas]` — id do evento e contêiner
 *   preenchido na primeira abertura com GET /provas?evento= (uma requisição
 *   por evento). Cada prova vira uma entrada nomeada: cargo(s) como título,
 *   meta (tipo · ano · N itens/questões) e ações — "Resolver as questões"
 *   (/?evento=…&fonte=…&prova=… — `prova` é o nome de exibição da prova, só
 *   de leitura para o question-browser) e link do documento quando a fonte aponta para um
 *   arquivo (diretório/não-URL vira texto "Fonte indisponível", sem link).
 * - `[data-contagem]` — recebe a contagem infletida de eventos visíveis:
 *   "N evento(s)" ou, com zero, "Nenhum evento encontrado com essa busca.".
 *
 * Todo texto vindo do dataset passa por esc() antes do innerHTML.
 */

const LINK_CLS =
  'rounded-sm text-ink-soft transition-colors hover:text-ink focus-visible:focus-ring underline decoration-line underline-offset-2';

function normaliza(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '');
}

/** Linha de uma prova na lista do <details> — exportada para testes. */
export function provaHtml(p: Prova, indice: number): string {
  const temCargos = (p.cargos ?? []).length > 0;
  const nome = temCargos ? resumoCargos(p.cargos ?? []) : `Prova ${indice + 1}`;
  // ?prova= é o nome de exibição no question-browser — sem cargos o aviso lá
  // diz "somente a prova N", então o rótulo vai sem o "Prova" duplicado
  const rotulo = temCargos ? nome : String(indice + 1);

  const meta: string[] = [];
  const tipos = (p.tipos ?? []).map(tipoLabel);
  if (tipos.length) meta.push(tipos.join(' + '));
  const anos = resumoAnos(p.anos ?? []);
  if (anos) meta.push(anos);
  // prova só de certo/errado conta "itens"; MC e listas mistas, "questões"
  const soCe = p.tipos?.length === 1 && p.tipos[0] === 'certo_errado';
  meta.push(plural(p.itens ?? p.questoes, soCe ? 'item' : 'questão', soCe ? 'itens' : 'questões'));

  const resolver =
    `<a href="${BASE}/?evento=${encodeURIComponent(p.evento)}&fonte=${encodeURIComponent(p.fonte)}&prova=${encodeURIComponent(rotulo)}"` +
    ` class="${LINK_CLS}" aria-label="Resolver as questões — ${esc(nome)}">Resolver as questões</a>`;
  const arquivo = arquivoFonte(p.fonte);
  const doc = arquivo
    ? `<a href="${esc(p.fonte)}" class="${LINK_CLS}" aria-label="${
        arquivo.toLowerCase().endsWith('.pdf') ? 'PDF oficial' : 'Fonte oficial'
      } — ${esc(nome)}">${
        arquivo.toLowerCase().endsWith('.pdf') ? 'PDF oficial' : 'Fonte oficial'
      }</a>`
    : '<span class="text-ink-faint">Fonte indisponível</span>';

  return (
    `<li>` +
    `<p class="text-sm font-medium text-ink">${esc(nome)}</p>` +
    `<p class="mt-0.5 text-xs text-ink-soft">${esc(meta.join(' · '))}</p>` +
    `<p class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">${resolver}${doc}</p>` +
    `</li>`
  );
}

export class EventoListElement extends HTMLElement {
  private itens: HTMLElement[] = [];

  connectedCallback() {
    const busca = this.querySelector<HTMLInputElement>('input[data-busca]');
    const contagem = this.querySelector<HTMLElement>('[data-contagem]');
    this.itens = [...this.querySelectorAll<HTMLElement>('[data-evento-item]')];

    busca?.addEventListener('input', () => {
      const termo = normaliza(busca.value);
      let visiveis = 0;
      for (const item of this.itens) {
        const ok = !termo || (item.dataset.buscaTexto ?? '').includes(termo);
        item.hidden = !ok;
        if (ok) visiveis++;
      }
      if (contagem) {
        contagem.textContent = visiveis
          ? plural(visiveis, 'evento')
          : 'Nenhum evento encontrado com essa busca.';
      }
    });

    // toggle não borbulha — captura na fase de captura atende todos os details
    this.addEventListener(
      'toggle',
      (e) => {
        const d = e.target as HTMLDetailsElement;
        if (d instanceof HTMLDetailsElement && d.open && !d.dataset.carregou) {
          this.carregarProvas(d);
        }
      },
      true,
    );
  }

  private apiUrl(): string {
    return (
      this.dataset.apiUrl ??
      this.closest<HTMLElement>('[data-api-url]')?.dataset.apiUrl ??
      ''
    );
  }

  private async carregarProvas(detalhe: HTMLDetailsElement) {
    detalhe.dataset.carregou = '1';
    const alvo = detalhe.querySelector<HTMLElement>('[data-provas]');
    if (!alvo) return;
    if (!this.apiUrl()) {
      alvo.innerHTML = '<p class="text-sm text-ink-soft">Não foi possível listar as provas — API indisponível.</p>';
      return;
    }
    alvo.innerHTML = '<p class="text-sm text-ink-soft">Carregando…</p>';
    try {
      const provas = await fetchProvas(detalhe.dataset.evento);
      alvo.innerHTML = provas.length
        ? `<ul class="space-y-4">${provas.map(provaHtml).join('')}</ul>`
        : '<p class="text-sm text-ink-soft">Nenhuma prova registrada para este evento.</p>';
    } catch (err) {
      alvo.innerHTML =
        '<p class="text-sm text-ink-soft">Não foi possível carregar as provas — API indisponível.</p>';
      console.warn('evento-list:', err);
    }
  }
}

if (!customElements.get('evento-list')) {
  customElements.define('evento-list', EventoListElement);
}
