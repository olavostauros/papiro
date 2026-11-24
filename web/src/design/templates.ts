/**
 * templates.ts — markup de string compartilhado entre o SSR (.astro) e os
 * custom elements. Módulo PURO: sem efeitos colaterais, para poder ser
 * importado no frontmatter do Astro e no bundle do cliente.
 *
 * CONTRATO — `cardHtml` replica o markup de QuestionCard/Alternativa/
 * QuestionMeta (design/components/) incluindo os atributos data-* lidos por
 * <question-card> (design/elements/question-card.ts): data-id, data-banca,
 * data-orgao, data-cargo, data-ano, data-assunto, data-gabarito,
 * data-gabarito-texto, data-filter-item, data-opcao, data-ver-gabarito,
 * data-resultado. AO MUDAR UM, MUDE O OUTRO.
 *
 * `paginacaoHtml` gera âncoras (`?page=N`) — deep-links que funcionam sem JS;
 * <question-browser> intercepta o clique e troca por fetch. O contrato é
 * data-nav (first|prev|next|last|num), data-pagina (alvo) e o <span>
 * data-atual + aria-current da página corrente.
 *
 * Todo texto vindo do dataset passa por esc() antes do innerHTML — conteúdo
 * derivado das bancas é não-confiável.
 */

import type { Questao } from '../data/questions';

const BASE = import.meta.env.BASE_URL.replace(/\/+$/, '');

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
  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:focus-ring px-3 py-1.5 text-xs border border-line-strong bg-surface text-ink hover:bg-accent-soft aria-disabled:pointer-events-none aria-disabled:opacity-50';
const ATUAL_CLS =
  'inline-flex items-center justify-center rounded-md px-3 py-1.5 text-xs font-medium border border-accent bg-accent-soft text-accent';
const LINK_CLS =
  'rounded-sm text-ink-soft transition-colors hover:text-ink focus-visible:focus-ring underline decoration-line underline-offset-2';
const PERMALINK_CLS =
  'rounded-sm text-ink-soft transition-colors hover:text-ink focus-visible:focus-ring';

export function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// fonte vira href: só http(s) é clicável (banca futura com fonte arbitrária)
const FONTE_URL = /^https?:/i;

export function fonteEhUrl(fonte: string): boolean {
  return FONTE_URL.test(fonte);
}

function gabaritoTexto(q: Questao): string {
  return q.tipo === 'certo_errado'
    ? q.gabarito === 'certo'
      ? 'Certo'
      : 'Errado'
    : `Alternativa ${q.gabarito.toUpperCase()}`;
}

export function cardHtml(q: Questao): string {
  const ce = q.tipo === 'certo_errado';
  const gab = gabaritoTexto(q);
  const aria = esc(`Questão — ${q.banca}, ${q.cargo}, ${q.ano}`);
  const permalink = `<a href="${BASE}/questao/?id=${encodeURIComponent(q.id)}" class="${PERMALINK_CLS}" aria-label="Página da questão — ${aria}">Permalink</a>`;
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
  const grupo = opcoes
    ? `<div class="mt-3 grid gap-1.5${ce ? ' grid-cols-2' : ''}" role="radiogroup" aria-labelledby="enunciado-${esc(q.id)}">${opcoes}</div>`
    : '';
  // MC rara sem alternativas (62 registros): sem botão, gabarito vai inline
  const resposta = opcoes
    ? `<button class="${BOTAO_CLS}" type="button" data-ver-gabarito>Ver gabarito</button><p data-resultado role="status" class="hidden font-medium"></p>`
    : `<p data-resultado role="status" class="font-medium text-accent">Gabarito: ${esc(gab)}</p>`;
  const fonte = FONTE_URL.test(q.fonte)
    ? `<a href="${esc(q.fonte)}" class="${LINK_CLS}" aria-label="Fonte oficial — ${aria}">Fonte oficial</a>`
    : '<span>Fonte oficial</span>';
  return `<question-card data-id="${esc(q.id)}" data-banca="${esc(q.banca)}" data-orgao="${esc(q.orgao)}" data-cargo="${esc(q.cargo)}" data-ano="${q.ano}" data-assunto="${esc(q.assunto)}" data-gabarito="${esc(q.gabarito)}" data-gabarito-texto="${esc(gab)}" data-filter-item><article class="rounded-xl border border-line bg-surface p-5" aria-label="${aria}">${meta}<p id="enunciado-${esc(q.id)}" class="mt-3 font-serif text-base leading-relaxed sm:text-lg">${esc(q.enunciado)}</p>${grupo}<div class="mt-4 flex flex-wrap items-center gap-4 text-sm">${resposta}<div class="ml-auto flex items-center gap-4">${permalink}${fonte}</div></div></article></question-card>`;
}

/** Janela de páginas: primeira, última e ±2 ao redor da atual; `null` = reticências. */
function janelaPaginas(page: number, pages: number): (number | null)[] {
  const nums = new Set<number>([1, pages]);
  for (let n = page - 2; n <= page + 2; n++) {
    if (n >= 1 && n <= pages) nums.add(n);
  }
  const ordenadas = [...nums].sort((a, b) => a - b);
  const out: (number | null)[] = [];
  let prev = 0;
  for (const n of ordenadas) {
    if (prev && n - prev > 1) out.push(null);
    out.push(n);
    prev = n;
  }
  return out;
}

/**
 * Paginação como âncoras (`href="?page=N&…"`) — funciona sem JS e dá
 * deep-link de graça. `qs` é a querystring dos filtros ativos SEM page nem
 * '?' inicial (ex.: "banca=X&q=y").
 */
export function paginacaoHtml(page: number, pages: number, qs = ''): string {
  if (pages <= 1) return '';
  const href = (n: number) => `?${qs ? `${qs}&` : ''}page=${n}`;
  const link = (n: number, nav: string, texto: string, label: string, disabled = false) =>
    disabled
      ? `<a class="${PAG_CLS}" aria-disabled="true" tabindex="-1" aria-label="${label}">${texto}</a>`
      : `<a href="${href(n)}" class="${PAG_CLS}" data-nav="${nav}" data-pagina="${n}" aria-label="${label}">${texto}</a>`;
  const nums = janelaPaginas(page, pages)
    .map((n) =>
      n === null
        ? '<span aria-hidden="true" class="px-1 text-ink-faint">…</span>'
        : n === page
          ? `<span data-atual tabindex="-1" aria-current="page" aria-label="Página ${page} de ${pages}" class="${ATUAL_CLS}">${n}</span>`
          : link(n, 'num', String(n), `Página ${n}`),
    )
    .join('');
  return (
    link(1, 'first', '«', 'Primeira página', page <= 1) +
    link(page - 1, 'prev', '‹', 'Página anterior', page <= 1) +
    nums +
    link(page + 1, 'next', '›', 'Próxima página', page >= pages) +
    link(pages, 'last', '»', 'Última página', page >= pages)
  );
}
