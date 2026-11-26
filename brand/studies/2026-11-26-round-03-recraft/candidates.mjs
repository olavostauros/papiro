// Builds an SVG contact sheet of the four original outputs, without editing raw/.
import {readFileSync,writeFileSync} from 'node:fs';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const out=dirname(fileURLToPath(import.meta.url));
const root=resolve(out,'../../..');
const {create}=await import(pathToFileURL(join(root,'web/node_modules/fontkitten/dist/index.js')));
const font=create(readFileSync(join(root,'web/node_modules/@fontsource-variable/inter/files/inter-latin-standard-normal.woff2')));
function text(str,x,y,size=20){
 let advance=0;const scale=size/font.unitsPerEm;
 const body=font.glyphsForString(str).map(g=>{const d=g.path.transform(scale,0,0,-scale,advance,0).toSVG();advance+=g.advanceWidth*scale;return `<path d="${d}"/>`;}).join('');
 return `<g fill="#2c471c" transform="translate(${x} ${y})">${body}</g>`;
}
let body='<rect width="1600" height="1780" fill="#f4f6ee"/>';
body+=text('PAPIRO / RECRAFT / QUATRO RESULTADOS ORIGINAIS',40,52,24);
body+=text('Cores e curvas recebidas. As alternativas B foram selecionadas para composição.',40,88,17);
for(const [i,[file,label]] of [['01-margens-a','Margens A'],['01-margens-b','Margens B · selecionada'],['02-lombada-a','Lombada A'],['02-lombada-b','Lombada B · selecionada']].entries()){
 const x=40+(i%2)*800,y=126+Math.floor(i/2)*810;
 let source=readFileSync(join(out,'raw',`${file}.svg`),'utf8');
 const box=source.match(/viewBox="([^"]+)"/)[1].trim().split(/[ ,]+/).map(Number);
 source=source.replace(/^\s*(?:<\?xml[^>]*>\s*)?<svg\b[^>]*>/,'').replace(/<\/svg>\s*$/,'').replace(/<metadata\b[^>]*>[\s\S]*?<\/metadata>/g,'');
 body+=text(label,x,y+28,23);
 const scale=720/Math.max(box[2],box[3]);
 body+=`<g transform="translate(${x} ${y+52}) scale(${scale})">${source}</g>`;
}
body+=text('SVGs raw preservados sem alterações; metadados omitidos somente nesta prancha.',40,1750,16);
writeFileSync(join(out,'candidates.svg'),`<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1780" viewBox="0 0 1600 1780" role="img" aria-labelledby="title desc"><title id="title">papiro — quatro alternativas originais do Recraft</title><desc id="desc">Alternativas A e B de Margens e Lombada. Geometria e cores originais.</desc>${body}</svg>\n`);
console.log('Built candidates.svg from four original Recraft outputs.');
