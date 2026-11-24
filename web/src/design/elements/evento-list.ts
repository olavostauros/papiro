import { fetchProvas } from '../../data/questions';
import { esc, fonteEhUrl } from '../templates';

/**
 * <evento-list> — lista de eventos (concursos ingeridos) na página /provas/.
 *
 * Contrato:
 * - `data-api-url` no elemento ou num ancestral — sem ela a busca textual
 *   continua funcionando (filtra o já renderizado), só as provas por evento
 *   ficam indisponíveis.
 * - `input[data-busca]` — filtra itens no cliente (sem fetch), ignorando
 *   acentos, sobre o texto de `data-busca-texto`.
 * - `[data-evento-item]` — <details> de um evento; `data-evento` guarda o id
 *   para o fetch e `data-busca-texto` o texto pesquisável.
 * - `[data-provas]` — contêiner dentro do <details> preenchido sob demanda
 *   com GET /provas?evento= na primeira abertura (uma requisição por evento).
 * - `[data-contagem]` — recebe o total de eventos visíveis.
 */

const LINK_CLS =
  'rounded-sm text-ink-soft transition-colors hover:text-ink focus-visible:focus-ring underline decoration-line underline-offset-2';

function normaliza(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '');
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
      if (contagem) contagem.textContent = String(visiveis);
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
      alvo.innerHTML = '<p class="text-sm text-ink-soft">API indisponível — não foi possível listar as provas.</p>';
      return;
    }
    alvo.innerHTML = '<p class="text-sm text-ink-soft">Carregando…</p>';
    try {
      const provas = await fetchProvas(detalhe.dataset.evento);
      alvo.innerHTML = provas.length
        ? `<ul class="space-y-1 text-sm">${provas
            .map(
              (p) =>
                `<li class="flex flex-wrap items-baseline gap-x-2">${
                  fonteEhUrl(p.fonte)
                    ? `<a href="${esc(p.fonte)}" class="${LINK_CLS}">Fonte oficial</a>`
                    : `<span class="text-ink-soft">Fonte oficial</span>`
                }<span class="text-ink-faint">· ${p.questoes.toLocaleString('pt-BR')} questões</span></li>`,
            )
            .join('')}</ul>`
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
