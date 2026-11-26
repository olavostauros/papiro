// Rebuild: node brand/studies/2026-11-26-round-02/generate.mjs
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {dirname, resolve, join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';

const out=dirname(fileURLToPath(import.meta.url));
const root=resolve(out,'../../..');
const {create}=await import(pathToFileURL(join(root,'web/node_modules/fontkitten/dist/index.js')));
const font=create(readFileSync(join(root,'web/node_modules/@fontsource-variable/inter/files/inter-latin-standard-normal.woff2')));
const c={olive:'#2c471c',light:'#e6ece1',paper:'#f4f6ee',dark:'#0d1609',muted:'#5d6b55',line:'#cbd3c3'};
const round=d=>d.replace(/-?\d*\.?\d+(?:e[+-]?\d+)?/gi,n=>String(+Number(n).toFixed(3)));
const esc=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;');
const wordSource=readFileSync(join(out,'../2026-11-26/01-nome/papiro.svg'),'utf8');
// Preserve the original lettering as an exact, complete vector group.
const word=wordSource.slice(wordSource.indexOf('<g '),wordSource.lastIndexOf('</g>')+4);
const originalBookSource=readFileSync(join(out,'../2026-11-26/02-acervo/mark.svg'),'utf8');
const originalBook=originalBookSource.slice(originalBookSource.indexOf('<g '),originalBookSource.lastIndexOf('</g>')+4);

function text(str,x,y,size=16,color=c.olive,tracking=0){
 let advance=0; const scale=size/font.unitsPerEm;
 const paths=font.glyphsForString(str).map(g=>{const d=round(g.path.transform(scale,0,0,-scale,advance,0).toSVG());advance+=g.advanceWidth*scale+tracking;return `<path d="${d}"/>`;}).join('');
 return `<g fill="${color}" transform="translate(${x} ${y})">${paths}</g>`;
}
const rect=(x,y,w,h,fill,r=0)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}"/>`;
function svg(body,w,h,title,desc,color=c.olive){return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" color="${color}" role="img" aria-labelledby="title desc"><title id="title">${esc(title)}</title><desc id="desc">${esc(desc)}</desc>${body}</svg>\n`;}
function place(body,vb,x,y,w,h,color=c.olive){const z=Math.min(w/vb[0],h/vb[1]);return `<g color="${color}" transform="translate(${x+(w-vb[0]*z)/2} ${y+(h-vb[1]*z)/2}) scale(${z})">${body}</g>`;}

const studies=[
 {id:'01-margens',name:'Margens',heading:'Mais aberto, mais firme.',
  mark:'<g fill="currentColor" fill-rule="evenodd"><path d="M8 14L45 27V89L8 76ZM21 32V67L32 71V36Z"/><path d="M59 27L96 14V76L59 89ZM72 36V71L83 67V32Z"/></g>',
  first:'Páginas separadas; espessura ampliada.',second:'O ritmo angular segue os cortes dos pês.',trade:'Continuidade com a rodada 01; ainda lembra portas.'},
 {id:'02-lombada',name:'Lombada',heading:'Curvas que se encontram.',
  mark:'<path fill="currentColor" fill-rule="evenodd" d="M8 18C23 10 37 14 52 24C67 14 81 10 96 18V83C81 75 67 78 52 89C37 78 23 75 8 83ZM21 29V66C30 64 38 68 46 73V33C37 27 29 25 21 29ZM58 33V73C66 68 74 64 83 66V29C75 25 67 27 58 33Z"/>',
  first:'Um livro contínuo e duas contraformas amplas.',second:'As curvas conversam com p, a e o do nome.',trade:'Leitura de livro mais imediata; menos abstrato.'},
 {id:'03-miolo',name:'Miolo',heading:'O livro pelo intervalo.',
  mark:'<g fill="currentColor"><path d="M8 14C25 14 38 20 46 29V89C35 80 23 76 8 76Z"/><path d="M58 29C66 20 79 14 96 14V76C81 76 69 80 58 89Z"/></g>',
  first:'Dois planos sólidos, sem miolos estreitos.',second:'A abertura central constrói a leitura.',trade:'Mais forte na redução; pode sugerir asas.'}
];
const logoVB=[568,132],markVB=[104,104];
for(const s of studies){
 s.logo=`<g transform="translate(8 14)">${s.mark}</g><g transform="translate(134 0)">${word}</g>`;
 mkdirSync(join(out,s.id),{recursive:true});
 for(const [suffix,color] of [['',c.olive],['-reverse',c.light],['-mono','#000000']]){
  writeFileSync(join(out,s.id,`papiro${suffix}.svg`),svg(s.logo,...logoVB,`papiro — rodada 02 — ${s.name}`,`Estudo exploratório. ${s.first} Lettering geométrico da rodada 01.`,color));
  writeFileSync(join(out,s.id,`mark${suffix}.svg`),svg(s.mark,...markVB,`papiro — símbolo — ${s.name}`,`Estudo exploratório. ${s.first}`,color));
 }
 execFileSync('rsvg-convert',['-w','1200','-o',join(out,s.id,'papiro.png'),join(out,s.id,'papiro.svg')]);
 execFileSync('rsvg-convert',['-w','416','-o',join(out,s.id,'mark.png'),join(out,s.id,'mark.svg')]);
}

let board=rect(0,0,1800,1500,c.paper);
board+=text('PAPIRO / RODADA 02',48,60,16,c.olive,2.2);
board+=text('O livro evolui. O lettering permanece.',48,130,42);
board+=text('Três símbolos refinados com o mesmo desenho de letras da proposta 01.',48,168,18,c.muted);
board+=text('Estudos exploratórios · nenhuma versão final adotada',48,200,14,c.muted);
board+=rect(48,231,1704,1,c.line);
studies.forEach((s,k)=>{
 const x=48+k*584;
 if(k)board+=rect(x-24,263,1,1165,c.line);
 board+=text(`0${k+1} / ${s.name}`,x,294,30);
 board+=text(s.heading,x,332,18,c.muted);
 board+=place(s.mark,markVB,x+168,361,200,200);
 board+=place(s.logo,logoVB,x,592,536,125);
 board+=text(s.first,x,752,15,c.muted);
 board+=text(s.second,x,779,15,c.muted);
 board+=rect(x,817,536,191,c.dark);
 board+=text('TEMA ESCURO',x+24,850,12,c.light,1.2);
 board+=place(s.logo,logoVB,x+24,873,488,113,c.light);
 board+=text('UMA COR',x,1055,12,c.muted,1.2);
 board+=place(s.logo,logoVB,x,1084,365,85,'#000000');
 board+=rect(x+426,1074,94,94,'#000000',14);
 board+=place(s.mark,markVB,x+443,1091,60,60,'#ffffff');
 board+=text('SÍMBOLOS / TAMANHO REAL',x,1224,12,c.muted,1.1);
 [16,24,32,48].forEach((size,i)=>{
  const xx=x+12+i*125;
  board+=place(s.mark,markVB,xx,1260+(48-size)/2,size,size);
  board+=text(`${size} px`,xx,1341,13,c.muted);
 });
 board+=text('Cabeçalho / 176 px',x,1399,12,c.muted);
 board+=place(s.logo,logoVB,x+330,1372,176,42);
});
board+=text('MESMA PALETA · MESMA ASSINATURA · COMPARAÇÃO FOCADA NO SÍMBOLO',48,1470,12,c.muted,1.2);
writeFileSync(join(out,'comparison.svg'),svg(board,1800,1500,'papiro — rodada 02','Três refinamentos do livro aberto com o lettering original da proposta 01, nos temas claro e escuro, monocromia e reduções.'));
execFileSync('rsvg-convert',['-o',join(out,'comparison.png'),join(out,'comparison.svg')]);

let detail=rect(0,0,1280,1030,c.paper);
detail+=text('PAPIRO / RODADA 02 / INSPEÇÃO ÓPTICA',40,52,18);
detail+=text('Símbolos a 16, 24, 32 e 48 px. Assinaturas a 160, 176 e 208 px de largura.',40,86,15,c.muted);
studies.forEach((s,k)=>{
 const y=120+k*240;
 detail+=text(`0${k+1} / ${s.name}`,40,y+24,20);
 [16,24,32,48].forEach((size,i)=>{
  const xx=54+i*100;
  detail+=place(s.mark,markVB,xx,y+60+(48-size)/2,size,size);
  detail+=text(`${size}`,xx,y+139,12,c.muted);
 });
 detail+=rect(475,y+40,282,135,c.dark,8);
 [16,24,32,48].forEach((size,i)=>detail+=place(s.mark,markVB,495+i*62,y+100-size/2,size,size,c.light));
 [160,176,208].forEach((w,i)=>{
  detail+=place(s.logo,logoVB,810,y+35+i*51,w,w*132/568);
  detail+=text(`${w} px`,1050,y+61+i*51,12,c.muted);
 });
 detail+=rect(40,y+203,1200,1,c.line);
});
detail+=text('REFERÊNCIA / LIVRO DA RODADA 01',40,899,13,c.muted,1);
[16,24,32,48].forEach((size,i)=>{
 const xx=400+i*105;
 detail+=place(originalBook,[96,104],xx,873+(48-size)/2,size,size);
 detail+=text(`${size}`,xx,956,12,c.muted);
});
detail+=text('Inspecionar a 100%: a reamostragem do visualizador altera os detalhes.',40,1004,13,c.muted);
writeFileSync(join(out,'reductions.svg'),svg(detail,1280,1030,'papiro — rodada 02 — reduções','Comparação em tamanho real dos três símbolos e assinaturas, com referência ao símbolo da rodada 01.'));
execFileSync('rsvg-convert',['-o',join(out,'reductions.png'),join(out,'reductions.svg')]);
console.log('Rendered round 02: 18 vector assets, 6 transparent PNGs and 2 comparison boards.');
