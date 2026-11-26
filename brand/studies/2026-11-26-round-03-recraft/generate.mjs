// Run only after raw SVG inspection, visual review and selections.json.
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';

const out = dirname(fileURLToPath(import.meta.url));
const root = resolve(out, '../../..');
const selected = JSON.parse(readFileSync(join(out, 'selections.json'), 'utf8'));
if (selected.length !== 2) throw Error('Select one reviewed result for each of the two completed routes.');
const {create} = await import(pathToFileURL(join(root, 'web/node_modules/fontkitten/dist/index.js')));
const font = create(readFileSync(join(root, 'web/node_modules/@fontsource-variable/inter/files/inter-latin-standard-normal.woff2')));
const c = {olive:'#2c471c', light:'#e6ece1', paper:'#f4f6ee', dark:'#0d1609', muted:'#5d6b55', line:'#cbd3c3'};
const escape = s => s.replaceAll('&','&amp;').replaceAll('<','&lt;');
const original = readFileSync(join(out, '../2026-11-26/01-nome/papiro.svg'),'utf8');
const word = original.slice(original.indexOf('<g '), original.lastIndexOf('</g>')+4);
const rect = (x,y,w,h,fill) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}"/>`;
function text(str,x,y,size=16,color=c.olive) {
  let advance=0; const scale=size/font.unitsPerEm;
  const paths=font.glyphsForString(str).map(g=>{
    const d=g.path.transform(scale,0,0,-scale,advance,0).toSVG();
    advance+=g.advanceWidth*scale;
    return `<path d="${d}"/>`;
  }).join('');
  return `<g fill="${color}" transform="translate(${x} ${y})">${paths}</g>`;
}
function svg(body,w,h,title,desc,color=c.olive) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" color="${color}" role="img" aria-labelledby="title desc"><title id="title">${escape(title)}</title><desc id="desc">${escape(desc)}</desc>${body}</svg>\n`;
}
function readSvg(path, prefix='') {
  const src=readFileSync(path,'utf8');
  const vb=src.match(/viewBox="([^"]+)"/)[1].trim().split(/[ ,]+/).map(Number);
  let body=src.replace(/^\s*(?:<\?xml[^>]*>\s*)?<svg\b[^>]*>/,'').replace(/<\/svg>\s*$/,'');
  body=body.replace(/<(title|desc)\b[^>]*>[\s\S]*?<\/\1>/g,'');
  if(prefix) {
    const ids=[...body.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
    for(const id of ids) body=body.replaceAll(`id="${id}"`,`id="${prefix}${id}"`).replaceAll(`url(#${id})`,`url(#${prefix}${id})`);
  }
  return {body,vb};
}
let instance=0;
function place(asset,x,y,w,h,color=c.olive) {
  const [vx,vy,vw,vh]=asset.vb;
  const scale=Math.min(w/vw,h/vh);
  let body=asset.body;
  const prefix=`instance${instance++}-`;
  for(const id of [...body.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1])) {
    body=body.replaceAll(`id="${id}"`,`id="${prefix}${id}"`).replaceAll(`url(#${id})`,`url(#${prefix}${id})`);
  }
  return `<g${color ? ` color="${color}"` : ''} transform="translate(${x+(w-vw*scale)/2-vx*scale} ${y+(h-vh*scale)/2-vy*scale}) scale(${scale})">${body}</g>`;
}
function render(name,body,w,h,title,desc) {
  writeFileSync(join(out,`${name}.svg`),svg(body,w,h,title,desc));
  execFileSync('rsvg-convert',['-o',join(out,`${name}.png`),join(out,`${name}.svg`)]);
}

const studies=selected.map((s,i)=>{
  const source=readSvg(join(out,'working',`${s.id}.svg`),`r${i}-`);
  const mark={body:place(source,0,0,104,104,null),vb:[0,0,104,104]};
  const logo={body:`<g transform="translate(8 14)">${mark.body}</g><g transform="translate(134 0)">${word}</g>`,vb:[0,0,568,132]};
  const before=readSvg(join(out,'../2026-11-26-round-02',s.id,'papiro.svg'),`old${i}-`);
  mkdirSync(join(out,s.id),{recursive:true});
  for(const [suffix,color] of [['',c.olive],['-reverse',c.light],['-mono','#000000']]) {
    writeFileSync(join(out,s.id,`mark${suffix}.svg`),svg(mark.body,104,104,`papiro — Recraft — ${s.name}`,s.description,color));
    writeFileSync(join(out,s.id,`papiro${suffix}.svg`),svg(logo.body,568,132,`papiro — Recraft — ${s.name}`,`${s.description} Lettering original preservado.`,color));
  }
  execFileSync('rsvg-convert',['-w','416','-o',join(out,s.id,'mark.png'),join(out,s.id,'mark.svg')]);
  execFileSync('rsvg-convert',['-w','1200','-o',join(out,s.id,'papiro.png'),join(out,s.id,'papiro.svg')]);
  return {...s,mark,logo,before};
});

let board=rect(0,0,1800,1590,c.paper);
board+=text('PAPIRO / RODADA 03 / RECRAFT',48,58,18);
board+=text('Duas rotas refinadas no Recraft.',48,123,43);
board+=text('Estudos vetoriais Recraft V4.1 Vector Pro · comparação com a rodada 02',48,165,19,c.muted);
board+=text('Exploração: nenhuma versão final adotada.',48,198,15,c.muted);
board+=rect(48,224,1704,1,c.line);
studies.forEach((s,i)=>{
  const x=48+i*584;
  if(i)board+=rect(x-24,252,1,1270,c.line);
  board+=text(`${String(i+1).padStart(2,'0')} / ${s.name}`,x,288,29);
  board+=text(`Seleção: ${s.candidate}`,x,321,15,c.muted);
  board+=text('RODADA 02',x,367,13,c.muted);
  board+=place(s.before,x,389,536,125);
  board+=text('RECRAFT / RODADA 03',x,551,13,c.muted);
  board+=place(s.mark,x+178,575,180,180);
  board+=place(s.logo,x,778,536,125);
  board+=rect(x,929,536,184,c.dark);
  board+=text('TEMA ESCURO',x+22,961,12,c.light);
  board+=place(s.logo,x+22,977,492,114,c.light);
  board+=text('UMA COR',x,1155,12,c.muted);
  board+=place(s.logo,x,1178,390,91,'#000000');
  board+=rect(x+430,1175,92,92,'#000000');
  board+=place(s.mark,x+446,1191,60,60,'#ffffff');
  board+=text('SÍMBOLO / TAMANHO REAL',x,1323,12,c.muted);
  [16,24,32,48].forEach((size,j)=>{
    const xx=x+12+j*125;
    board+=place(s.mark,xx,1352+(48-size)/2,size,size);
    board+=text(`${size} px`,xx,1435,13,c.muted);
  });
  board+=text('Cabeçalho / 176 px',x,1495,12,c.muted);
  board+=place(s.logo,x+330,1469,176,41);
});
const reference=readSvg(join(out,'../2026-11-26-round-02/03-miolo/papiro.svg'),'pending-');
const referenceMark=readSvg(join(out,'../2026-11-26-round-02/03-miolo/mark.svg'),'pending-mark-');
const pendingX=1216;
board+=rect(pendingX-24,252,1,1270,c.line);
board+=text('03 / Miolo',pendingX,288,29);
board+=text('REFERÊNCIA / RODADA 02',pendingX,321,15,c.muted);
board+=place(referenceMark,pendingX+178,390,180,180);
board+=place(reference,pendingX,616,536,125);
board+=text('Sem nova versão Recraft.',pendingX,803,22);
board+=text('A tentativa encontrou saldo insuficiente.',pendingX,846,17,c.muted);
board+=text('O desenho anterior está preservado.',pendingX,880,17,c.muted);
board+=text('Nenhum crédito adicional foi comprado.',pendingX,914,17,c.muted);
board+=text('MESMA PALETA · LETTERING ORIGINAL · GEOMETRIA DOS SÍMBOLOS GERADA NO RECRAFT',48,1555,12,c.muted);
render('comparison',board,1800,1590,'papiro — rodada 03 — comparação','Três símbolos Recraft selecionados, com comparação antes/depois, temas, monocromia e reduções.');

let reductions=rect(0,0,1280,930,c.paper);
reductions+=text('PAPIRO / RODADA 03 / INSPEÇÃO ÓPTICA',40,52,20);
reductions+=text('Inspecionar a 100%: a reamostragem altera os detalhes.',40,86,15,c.muted);
studies.forEach((s,k)=>{
  const y=122+k*254;
  reductions+=text(`${String(k+1).padStart(2,'0')} / ${s.name}`,40,y+24,22);
  [16,24,32,48].forEach((size,i)=>{
    const x=54+i*100;
    reductions+=place(s.mark,x,y+61+(48-size)/2,size,size);
    reductions+=text(`${size}`,x,y+143,12,c.muted);
  });
  reductions+=rect(475,y+42,282,135,c.dark);
  [16,24,32,48].forEach((size,i)=>reductions+=place(s.mark,495+i*62,y+105-size/2,size,size,c.light));
  [160,176,208].forEach((w,i)=>{
    reductions+=place(s.logo,810,y+34+i*51,w,w*132/568);
    reductions+=text(`${w} px`,1050,y+62+i*51,12,c.muted);
  });
  reductions+=rect(40,y+214,1200,1,c.line);
});
reductions+=text('03 / Miolo — referência da rodada 02',40,680,22);
reductions+=text('Sem resultado Recraft: saldo insuficiente na tentativa.',40,715,15,c.muted);
reductions+=place(reference,40,757,280,65);
reductions+=text('A comparação detalhada original permanece na rodada 02.',40,870,15,c.muted);
render('reductions',reductions,1280,930,'papiro — rodada 03 — reduções','Símbolos em 16, 24, 32 e 48 pixels; assinaturas em 160, 176 e 208 pixels.');
console.log('Generated 12 assets, four transparent PNGs and two boards from two reviewed Recraft routes. Miolo remains a round-02 reference.');
