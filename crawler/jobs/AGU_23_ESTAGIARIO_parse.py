import re, json
import xml.etree.ElementTree as ET
from collections import defaultdict
root = ET.parse('/tmp/agu_23_estagiario/gab.xml').getroot()
VERDICTS = ('CORRETO','CORRETA','CERTO','CERTA','ERRADO','ERRADA')
CUTOFF = 24

events=[]; rows=[]; page_labels=defaultdict(list)
for pi,page in enumerate(root.iter('page')):
    els=[]
    for t in page.iter('text'):
        s=' '.join(''.join(t.itertext()).split())
        if s: els.append((float(t.get('top')),float(t.get('left')),s))
    for top,left,s in els:
        if top<86: continue
        if left<150 and re.match(r'^QUESTÃO\s+\d+',s):
            events.append((pi,top,'q',int(re.search(r'\d+',s).group())))
        elif left<110 and s in VERDICTS:
            letter=[x[2] for x in els if abs(x[0]-top)<4 and 150<x[1]<245 and re.fullmatch(r'[A-E]',x[2])]
            events.append((pi,top,'l',(s,letter[0] if letter else '?')))
            page_labels[pi].append(top)
        elif left<110 and s=='ANULADA':
            events.append((pi,top,'a',None))
        elif left>=150:
            if s.startswith(('CEBRASPE','Internet:','Disponível','Adaptado','GABARITO DEFINITIVO')):
                continue
            if re.fullmatch(r'[A-E]',s) and left<245: continue
            rows.append((pi,top,left,s))
events.sort(key=lambda e:(e[0],e[1]))
rows.sort()

# pass 1: create questions + alts
questions=[]; open_q=None; lab2alt={}
for pi,top,kind,v in events:
    if kind=='q':
        if open_q is not None: questions.append(open_q)
        open_q={'num':v,'enun_rows':[],'alts':[],'anulada':False}
    elif kind=='a':
        if open_q is not None: open_q['anulada']=True
    else:
        if open_q is None: continue
        alt={'verdict':v[0],'letter':v[1],'rows':[],'q':open_q}
        open_q['alts'].append(alt); lab2alt[(pi,top)]=alt
if open_q is not None: questions.append(open_q)

# pass 2: distribute rows; pending flushes into the owner of the next label
stream2=sorted(events+[(pi,top,'t',(top,left,s)) for pi,top,left,s in rows],
               key=lambda e:(e[0],e[1]))
pending=[]
for pi,top,kind,v in stream2:
    if kind=='l':
        alt=lab2alt[(pi,top)]
        if pending:
            alt['q']['enun_rows'].extend(pending); pending=[]
    elif kind=='t':
        top,left,s=v
        cands=[lt for lt in page_labels[pi] if abs(top-lt)<=CUTOFF]
        if cands:
            lt=min(cands,key=lambda lt:abs(top-lt))
            lab2alt[(pi,lt)]['rows'].append(v)
        else:
            pending.append(v)

print(len(questions),'questions')
probs=[]
for q in questions:
    cor=[a for a in q['alts'] if a['verdict'] in ('CORRETO','CORRETA','CERTO','CERTA')]
    alts=[]
    for a in q['alts']:
        a['rows'].sort(key=lambda r:(r[0],r[1]))
        a['txt']=' '.join(' '.join(t.split()) for _,_,t in a['rows']).strip()
        alts.append(a['txt'])
    q['enun_rows'].sort(key=lambda r:(r[0],r[1]))
    q['enunciado']=' '.join(' '.join(t.split()) for _,_,t in q['enun_rows']).strip()
    if not q['anulada'] and len(cor)!=1: probs.append(('gab',q['num'],len(cor)))
    if len(q['alts'])!=4: probs.append(('alts',q['num'],len(q['alts'])))
    if len(q['enunciado'])<15: probs.append(('short_enun',q['num'],q['enunciado'][:60]))
    if any(len(a)<3 for a in alts): probs.append(('short_alt',q['num'],alts))
    if re.search(r'[\ue000-\uf8ff]',q['enunciado']+' '.join(alts)): probs.append(('PUA',q['num'],''))
print('problems:',probs)
print('anuladas:',[q['num'] for q in questions if q['anulada']])
for q in questions:
    for a in q['alts']: a.pop('q',None)
json.dump(questions,open('/tmp/agu_23_estagiario/parsed.json','w'),ensure_ascii=False,indent=1)
