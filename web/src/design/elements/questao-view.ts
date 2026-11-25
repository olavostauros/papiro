import { fetchQuestao } from '../../data/questions';
import './question-card';
// o cardHtml traz um <questao-explicar> embutido (inerte aqui — dedup,
// pois o card fica dentro de <questao-view>)
import './questao-explicar';
import { cardHtml } from '../templates';

/**
 * <questao-view> — página de uma questão (permalink /questao/?id=…), servida
 * por GET /questoes/{id}.
 *
 * Contrato:
 * - `data-api-url` no elemento — sem ele o componente fica inerte e o
 *   conteúdo SSR permanece.
 * - `[data-alvo]` — contêiner que recebe o card (o SSR pode já ter
 *   renderizado um <question-card data-id> igual ao da URL — nesse caso não
 *   refaz o fetch).
 * - `[data-status]` — mensagens de carregando/erro (role=status na página).
 *
 * Sem `?id=` ou sem API o EmptyState do SSR permanece e o elemento só exibe
 * a mensagem correspondente em [data-status].
 */
export class QuestaoViewElement extends HTMLElement {
  connectedCallback() {
    const alvo = this.querySelector<HTMLElement>('[data-alvo]');
    const id = new URLSearchParams(location.search).get('id') ?? '';
    if (!id) return; // EmptyState do SSR já orienta o usuário

    const ssr = alvo?.querySelector<HTMLElement>('question-card[data-id]');
    if (ssr?.dataset.id === id) return; // SSR já renderizou esta questão

    const apiUrl = this.dataset.apiUrl;
    if (!apiUrl || !alvo) {
      this.status('API indisponível — não foi possível carregar a questão.');
      return;
    }

    this.status('Carregando…');
    fetchQuestao(id)
      .then((q) => {
        alvo.innerHTML = cardHtml(q);
        document.title = `papiro — ${q.id}`;
        this.status('');
      })
      .catch((err) => {
        alvo.innerHTML =
          '<div class="rounded-xl border border-line bg-surface p-5"><p class="text-ink-soft">Questão não encontrada — verifique o identificador ou tente novamente mais tarde.</p></div>';
        this.status('');
        console.warn('questao-view:', err);
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

if (!customElements.get('questao-view')) {
  customElements.define('questao-view', QuestaoViewElement);
}
