// Rebuild with: node brand/studies/2026-11-26/generate.mjs
// Uses only the fonts and fontkitten already present in web/node_modules.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const out = dirname(fileURLToPath(import.meta.url));
const root = resolve(out, '../../..');
const { create } = await import(pathToFileURL(join(root, 'web/node_modules/fontkitten/dist/index.js')));
const load = (family, file) => create(readFileSync(join(root, 'web/node_modules/@fontsource-variable', family, 'files', file)));
const inter = load('inter', 'inter-latin-standard-normal.woff2');
const serif = load('source-serif-4', 'source-serif-4-latin-standard-italic.woff2');
const round = d => d.replace(/-?\d*\.?\d+(?:e[+-]?\d+)?/gi, n => String(+Number(n).toFixed(3)));
const esc = s => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
const colors = { olive: '#2c471c', light: '#e6ece1', paper: '#f4f6ee', dark: '#0d1609', muted: '#5d6b55', line: '#cbd3c3' };

function type(str, font = inter, size = 16, tracking = 0) {
  let x = 0;
  const scale = size / font.unitsPerEm;
  const paths = font.glyphsForString(str).map(g => {
    const d = round(g.path.transform(scale, 0, 0, -scale, x, 0).toSVG());
    x += g.advanceWidth * scale + tracking;
    return `<path d="${d}"/>`;
  }).join('');
  return { body: paths, width: x - tracking };
}
function text(str, x, y, size = 16, color = colors.olive, tracking = 0) {
  return `<g fill="${color}" transform="translate(${x} ${y})">${type(str, inter, size, tracking).body}</g>`;
}
function rect(x, y, width, height, color, radius = 0) {
  return `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${radius}" fill="${color}"/>`;
}
function svg(body, width, height, title, desc, color = colors.olive) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" color="${color}" role="img" aria-labelledby="title desc"><title id="title">${esc(title)}</title><desc id="desc">${esc(desc)}</desc>${body}</svg>\n`;
}
function place(body, vb, x, y, width, height, color = colors.olive) {
  const scale = Math.min(width / vb[0], height / vb[1]);
  const dx = x + (width - vb[0] * scale) / 2;
  const dy = y + (height - vb[1] * scale) / 2;
  return `<g color="${color}" transform="translate(${dx} ${dy}) scale(${scale})">${body}</g>`;
}

// A: original geometric lettering. The two p stems end in the same angled cut.
// Coordinates are drawing units, not glyphs extracted from a typeface.
const p = 'M0 16H14V23C20 16 28 12 39 12C61 12 74 26 74 47C74 68 60 82 39 82C28 82 20 78 14 72V100L0 108ZM14 47C14 61 23 69 37 69C50 69 59 60 59 47C59 34 50 25 37 25C23 25 14 34 14 47Z';
const a = 'M60 16H74V82H60V73C54 79 46 83 35 83C14 83 0 69 0 48C0 27 14 12 35 12C46 12 54 16 60 23ZM15 48C15 61 24 70 37 70C51 70 60 61 60 48C60 34 51 25 37 25C24 25 15 34 15 48Z';
const i = 'M0 16H14V82H0ZM0-10H14V4H0Z';
const r = 'M0 16H14V27C20 17 30 13 43 15V29C24 27 14 38 14 54V82H0Z';
const o = 'M37 12C60 12 75 27 75 48C75 69 60 83 37 83C15 83 0 69 0 48C0 27 15 12 37 12ZM15 48C15 61 24 70 37 70C51 70 60 61 60 48C60 34 51 25 37 25C24 25 15 34 15 48Z';
const geometricWord = `<g fill="currentColor" fill-rule="evenodd" transform="translate(8 18)">${[[p,0],[a,85],[p,170],[i,260],[r,290],[o,342]].map(([d,x]) => `<path transform="translate(${x} 0)" d="${d}"/>`).join('')}</g>`;
const geometricMark = `<g fill="currentColor" fill-rule="evenodd" transform="translate(17 0)"><path d="${p}"/></g>`;

// B: two open planes; the top edges deliberately do not close into a folder.
const archiveMark = '<g fill="currentColor"><path d="M8 12L43 25V91L8 78ZM18 27V71L33 77V32Z" fill-rule="evenodd"/><path d="M53 25L88 12V78L53 91ZM63 32V77L78 71V27Z" fill-rule="evenodd"/></g>';
const editorial = type('papiro', serif, 104, -1.5);
const archiveWord = `<g fill="currentColor" transform="translate(124 88)">${editorial.body}</g>`;
const archiveLogo = `${archiveMark}${archiveWord}`;

// C: p in solid, bevelled planes, with a large counter and no crossing strokes.
const structureMark = '<path fill="currentColor" fill-rule="evenodd" d="M16 10H63L88 35V55L63 80H36V96L16 106ZM36 30V60H55L68 47V43L55 30Z"/>';
const sans = type('papiro', inter, 102, -3.8);
const structureWord = `<g fill="currentColor" transform="translate(116 87)">${sans.body}</g>`;

const studies = [
  { id: '01-nome', title: 'Nome como marca', concept: 'O nome faz a marca.', line1: 'Geometria original e ritmo dos dois pês.', line2: 'Um gesto: o corte nas hastes.', logo: geometricWord, logoVB: [434,132], mark: geometricMark, markVB:[108,116], short:'Lettering geométrico original', note1:'O pê isolado deriva do nome.', note2:'Leitura direta; associação mais abstrata.', limit:'Símbolo: 16 px / assinatura: 144 px' },
  { id: '02-acervo', title: 'Acervo aberto', concept: 'O estudo se abre.', line1: 'Dois planos, margens e um intervalo.', line2: 'Assinatura editorial em itálico.', logo: archiveLogo, logoVB:[124 + editorial.width + 8,121], mark: archiveMark, markVB:[96,104], short:'Planos abertos + Source Serif 4', note1:'O vazio organiza as duas páginas.', note2:'Pode sugerir livro, sem desenhar um.', limit:'Símbolo: 24 px / assinatura: 160 px' },
  { id: '03-estrutura', title: 'Pê como estrutura', concept: 'Uma letra, uma presença.', line1: 'Massa compacta e contraforma ampla.', line2: 'Chanfros se repetem dentro e fora.', logo: structureMark + structureWord, logoVB:[116 + sans.width + 8,121], mark: structureMark, markVB:[104,116], short:'Pê em planos + Inter', note1:'Um pê de contorno firme e angular.', note2:'A dobra é uma associação possível.', limit:'Símbolo: 16 px / assinatura: 160 px' }
];

for (const s of studies) {
  mkdirSync(join(out, s.id), { recursive: true });
  for (const [suffix, color] of [['', colors.olive], ['-reverse', colors.light], ['-mono', '#000000']]) {
    writeFileSync(join(out,s.id,`papiro${suffix}.svg`), svg(s.logo,...s.logoVB, `papiro — ${s.title}`, `Estudo exploratório. ${s.line1} ${s.line2}`,color));
    writeFileSync(join(out,s.id,`mark${suffix}.svg`),svg(s.mark,...s.markVB, `papiro — símbolo — ${s.title}`, `Símbolo exploratório. ${s.note1}`,color));
  }
  execFileSync('rsvg-convert', ['-w','1200','-o',join(out,s.id,'papiro.png'),join(out,s.id,'papiro.svg')]);
}

// Comparison board. All labels are outlines, so the board renders without fonts.
let board = rect(0,0,1800,1410,colors.paper);
board += text('PAPIRO  /  ESTUDOS DE IDENTIDADE',48,61,16,colors.olive,2.2);
board += text('Três caminhos para o mesmo acervo.',48,130,42);
board += text('Exploração 01 · 26 nov 2026 · nenhuma direção aprovada',48,167,17,colors.muted);
board += rect(48,207,1704,1,colors.line);

studies.forEach((s,index) => {
  const x = 48 + index*584;
  if(index) board += rect(x-24,238,1,1100,colors.line);
  board += text(`0${index+1}`,x,264,18,colors.muted,1.4);
  board += text(s.title,x,307,30);
  board += text(s.concept,x,344,18,colors.muted);
  board += place(s.logo,s.logoVB,x,381,512,144);
  board += place(s.mark,s.markVB,x+6,558,112,112);
  board += text(s.short,x+144,579,14);
  board += text(s.note1,x+144,611,14,colors.muted);
  board += text(s.note2,x+144,636,13,colors.muted);
  board += rect(x,710,536,215,colors.dark);
  // Label intentionally follows background in paint order.
  board += text('TEMA ESCURO',x+24,749,12,colors.light,1.3);
  board += place(s.logo,s.logoVB,x+24,775,488,112,colors.light);
  board += text('UMA COR',x,980,12,colors.muted,1.3);
  board += place(s.logo,s.logoVB,x,1003,350,90,'#000000');
  board += rect(x+412,995,104,104,'#000000',16);
  board += place(s.mark,s.markVB,x+432,1015,64,64,'#ffffff');
  board += text('REDUÇÃO · SÍMBOLO',x,1154,12,colors.muted,1.3);
  [16,24,32,48].forEach((size,k)=> {
    const sx=x+12+k*125;
    board += place(s.mark,s.markVB,sx,1191+(48-size)/2,size,size);
    board += text(`${size} px`,sx,1272,13,colors.muted);
  });
  board += text(s.limit,x,1320,13,colors.muted);
});
board += text('SVG EDITÁVEL · PNG PARA AVALIAÇÃO · PROPOSTAS EXPLORATÓRIAS',48,1381,12,colors.muted,1.2);
writeFileSync(join(out,'comparison.svg'),svg(board,1800,1410,'papiro — três estudos de identidade','Comparação das direções Nome como marca, Acervo aberto e Pê como estrutura, em temas claro e escuro, monocromia e reduções.'));
execFileSync('rsvg-convert',['-o',join(out,'comparison.png'),join(out,'comparison.svg')]);

// One physical pixel per SVG drawing pixel, for an honest small-size inspection.
let reductions = rect(0,0,1200,850,colors.paper);
reductions += text('PAPIRO / INSPEÇÃO EM TAMANHO REAL',40,52,18);
reductions += text('Símbolos a 16, 24, 32 e 48 px · assinaturas a 144 e 160 px de largura',40,85,14,colors.muted);
studies.forEach((s,index) => {
 const y=125+index*226;
 reductions += text(`0${index+1} / ${s.title}`,40,y+25,20);
 [16,24,32,48].forEach((size,k)=> {
   const x=58+k*109;
   reductions += place(s.mark,s.markVB,x,y+65+(48-size)/2,size,size);
   reductions += text(`${size}`,x,y+145,12,colors.muted);
 });
 reductions += rect(530,y+40,280,132,colors.dark,8);
 [16,24,32,48].forEach((size,k)=> reductions+=place(s.mark,s.markVB,550+k*62,y+81-size/2,size,size,colors.light));
 reductions += place(s.logo,s.logoVB,860,y+47,144,48);
 reductions += text('144 px',1030,y+75,12,colors.muted);
 reductions += place(s.logo,s.logoVB,860,y+112,160,50);
 reductions += text('160 px',1030,y+140,12,colors.muted);
 reductions += rect(40,y+193,1120,1,colors.line);
});
reductions += text('Ver a 100%: ampliação e reamostragem alteram a avaliação óptica.',40,829,13,colors.muted);
writeFileSync(join(out,'reductions.svg'),svg(reductions,1200,850,'papiro — inspeção óptica','Símbolos em quatro tamanhos, positivos e negativos, e assinaturas reduzidas.'));
execFileSync('rsvg-convert',['-o',join(out,'reductions.png'),join(out,'reductions.svg')]);
console.log(`Rendered 3 studies, 18 asset SVGs, 3 signature PNGs and 2 boards in ${out}`);
