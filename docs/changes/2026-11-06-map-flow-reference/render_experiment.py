"""Offline preview of the unchanged experiment JSON; no authoring or model calls."""
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'runs/_map-flow-experiment/2026-11-06-infection-short'

TEMPLATE = r'''<!doctype html><html lang="ko"><meta charset="utf-8">
<title>Concept Map 실험</title>
<style>
*{box-sizing:border-box}body{margin:0;font:15px "Malgun Gothic",sans-serif;color:#172554;background:#f5f7fb}
header{background:white;padding:22px 28px;border-bottom:1px solid #dce3ef}h1{font-size:24px;margin:0 0 8px}
header p{margin:5px 0;line-height:1.6;max-width:1100px}.muted{color:#64748b;font-size:13px}
nav{padding:12px 28px;display:flex;gap:10px;align-items:center;background:#fff}
button,input{font:inherit;padding:7px 12px;border:1px solid #cbd5e1;border-radius:7px;background:white}
main{display:grid;grid-template-columns:minmax(0,1fr) 340px;height:calc(100vh - 200px)}
#canvas{overflow:auto;background:#f5f7fb}aside{overflow:auto;padding:22px;background:white;border-left:1px solid #dce3ef}
aside h2{margin-top:0;font-size:20px}aside li{line-height:1.6;margin:9px 0}
.node{cursor:pointer}.node:hover rect{stroke:#2563eb;stroke-width:3}
#notes{padding:16px 28px;background:white;white-space:pre-wrap}
@media(max-width:800px){main{grid-template-columns:1fr;height:70vh}aside{max-height:300px;border-top:1px solid #ddd}}
</style>
<header><h1 id="title"></h1><p id="overview"></p><p class="muted" id="stats"></p></header>
<nav><button id="out">−</button><button id="fit">전체 보기</button><button id="in">＋</button>
<input id="search" placeholder="개념 검색" aria-label="개념 검색"><span class="muted">노드를 선택하면 내용·연결·근거를 볼 수 있습니다.</span></nav>
<main><div id="canvas"><svg id="map" xmlns="http://www.w3.org/2000/svg"></svg></div>
<aside id="detail"><h2>개념과 연결</h2><p>지도에서 개념을 선택하세요.</p></aside></main><section id="notes"></section>
<script>
const data=__DATA__;
document.title=data.title+" · 짧은 지시문 Map 실험";
document.querySelector("#title").textContent=data.title;
document.querySelector("#overview").textContent=data.overview;
document.querySelector("#stats").textContent=data.concepts.length+"개 개념 · "+data.relations.length+"개 연결 · 원본 추출 결과 미리보기";
const svg=document.querySelector("#map"),ns=svg.namespaceURI,nodes=new Map(data.concepts.map(x=>[x.concept_id,x]));
const outgoing=new Map([...nodes.keys()].map(k=>[k,[]])),incoming=new Map([...nodes.keys()].map(k=>[k,0]));
for(const e of data.relations){outgoing.get(e.from_id).push(e);incoming.set(e.to_id,incoming.get(e.to_id)+1)}
let roots=[...nodes.keys()].filter(k=>incoming.get(k)===0);
if(!roots.length&&nodes.size)roots=[[...nodes.keys()].sort((a,b)=>outgoing.get(b).length-outgoing.get(a).length)[0]];
const levels=new Map(),primary=new Set(),queue=[];
for(const id of roots){levels.set(id,0);queue.push(id)}
for(let i=0;i<queue.length;i++){const id=queue[i];for(const e of outgoing.get(id)){if(!levels.has(e.to_id)){levels.set(e.to_id,levels.get(id)+1);queue.push(e.to_id);primary.add(e)}}}
for(const id of nodes.keys())if(!levels.has(id))levels.set(id,0);
const rows=[];for(const[id,l]of levels){(rows[l]??=[]).push(id)}
const width=Math.max(850,...rows.map(r=>(r?.length||0)*310+40)),height=Math.max(500,rows.length*200+70),positions=new Map();
rows.forEach((row,l)=>row?.forEach((id,i)=>positions.set(id,{x:(width-row.length*310)/2+i*310+15,y:35+l*200})));
svg.setAttribute("viewBox","0 0 "+width+" "+height);
function make(tag,attrs={},text){const el=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el}
const defs=make("defs"),marker=make("marker",{id:"arrow",viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:7,markerHeight:7,orient:"auto-start-reverse"});
marker.append(make("path",{d:"M0 0L10 5L0 10Z",fill:"#94a3b8"}));defs.append(marker);svg.append(defs);
for(const e of data.relations){const a=positions.get(e.from_id),b=positions.get(e.to_id),x1=a.x+140,y1=a.y+125,x2=b.x+140,y2=b.y;
const path=make("path",{d:"M"+x1+","+y1+" C"+x1+","+(y1+45)+" "+x2+","+(y2-45)+" "+x2+","+y2,stroke:"#94a3b8",fill:"none","stroke-width":1.5,"marker-end":"url(#arrow)"});
if(!primary.has(e))path.setAttribute("stroke-dasharray","5 4");path.append(make("title",{},e.relation));svg.append(path)}
const colors=["#dbeafe","#d1fae5","#fef3c7","#ede9fe","#fee2e2"];
function wrap(s,n=25){const chars=Array.from(s),lines=[];for(let i=0;i<chars.length;i+=n)lines.push(chars.slice(i,i+n).join(""));return lines}
function show(id){const n=nodes.get(id),panel=document.querySelector("#detail");panel.replaceChildren();
const title=document.createElement("h2");title.textContent=n.title;panel.append(title);
const facts=document.createElement("ul");for(const f of n.core_facts){const li=document.createElement("li");li.textContent=f;facts.append(li)}panel.append(facts);
const h=document.createElement("h3");h.textContent="연결";panel.append(h);
for(const e of data.relations.filter(e=>e.from_id===id||e.to_id===id)){const p=document.createElement("p");p.textContent=nodes.get(e.from_id).title+" → "+nodes.get(e.to_id).title+" : "+e.relation;panel.append(p)}
const h2=document.createElement("h3");h2.textContent="원본 근거";panel.append(h2);
for(const r of n.source_refs){const p=document.createElement("p");p.className="muted";p.textContent=r.source_id+(r.pages.length?" · "+r.pages.join(", ")+"쪽":"")+(r.locator?" · "+r.locator:"");panel.append(p)}}
for(const[id,n]of nodes){const p=positions.get(id),g=make("g",{class:"node","data-id":id});
g.append(make("rect",{x:p.x,y:p.y,width:280,height:125,rx:12,fill:colors[levels.get(id)%colors.length],stroke:"#a5b4cf"}));
const lines=wrap(n.title,23);lines.slice(0,2).forEach((s,i)=>g.append(make("text",{x:p.x+14,y:p.y+26+i*22,"font-size":16,"font-weight":600},s)));
const fact=wrap(n.core_facts.join(" · "),27);fact.slice(0,2).forEach((s,i)=>g.append(make("text",{x:p.x+14,y:p.y+79+i*20,"font-size":13,fill:"#334155"},s+(i===1&&fact.length>2?"…":""))));
g.append(make("title",{},n.title+"\n"+n.core_facts.join("\n")));g.onclick=()=>show(id);svg.append(g)}
let scale=1;function zoom(v){scale=Math.max(.15,Math.min(2,v));svg.style.width=width*scale+"px";svg.style.height=height*scale+"px"}
function fit(){zoom(Math.min(1,document.querySelector("#canvas").clientWidth/width))}
document.querySelector("#fit").onclick=fit;document.querySelector("#in").onclick=()=>zoom(scale*1.25);document.querySelector("#out").onclick=()=>zoom(scale/1.25);
document.querySelector("#search").oninput=e=>{const q=e.target.value.toLowerCase();for(const g of svg.querySelectorAll(".node")){const n=nodes.get(g.dataset.id);g.style.opacity=!q||(n.title+" "+n.core_facts.join(" ")).toLowerCase().includes(q)?1:.18}};
document.querySelector("#notes").textContent=data.notes.length?"확인 사항\n"+data.notes.join("\n"):"";
fit();
</script></html>'''


for slug in ('endocarditis', 'cns-infection'):
    folder = OUT / slug
    value = json.loads((folder / 'concept-map.json').read_text(encoding='utf-8'))
    payload = json.dumps(value, ensure_ascii=False).replace('<', r'\u003c')
    (folder / 'map-preview.html').write_text(TEMPLATE.replace('__DATA__', payload), encoding='utf-8')
    def label(s):
        return s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')
    mermaid = ['flowchart TD']
    for n in value['concepts']:
        text = label(n['title']) + '<br/>' + '<br/>'.join(label(f) for f in n['core_facts'])
        mermaid.append('    ' + n['concept_id'] + '["' + text + '"]')
    for e in value['relations']:
        mermaid.append('    ' + e['from_id'] + ' -->|"' + label(e['relation']) + '"| ' + e['to_id'])
    (folder / 'concept-map.mmd').write_text('\n'.join(mermaid) + '\n', encoding='utf-8')
    print(str(folder / 'map-preview.html'))

    # Materially safer visual QA alternative: local raster drawing, no browser.
    from PIL import Image, ImageDraw, ImageFont
    font = lambda size, bold=False: ImageFont.truetype(
        'C:/Windows/Fonts/malgunbd.ttf' if bold else 'C:/Windows/Fonts/malgun.ttf', size)
    nodes = {n['concept_id']: n for n in value['concepts']}
    degree = {key: 0 for key in nodes}
    outgoing = {key: [] for key in nodes}
    for i, edge in enumerate(value['relations']):
        outgoing[edge['from_id']].append((i, edge['to_id']))
        degree[edge['to_id']] += 1
    roots = [key for key in nodes if degree[key] == 0]
    if not roots and nodes:
        roots = [max(nodes, key=lambda x: len(outgoing[x]))]
    levels = {key: 0 for key in roots}
    primary = set()
    queue = list(roots)
    for key in queue:
        for index, child in outgoing[key]:
            if child not in levels:
                levels[child] = levels[key] + 1
                primary.add(index)
                queue.append(child)
    for key in nodes:
        levels.setdefault(key, 0)
    rows = [[] for _ in range(max(levels.values(), default=0) + 1)]
    for key in nodes:
        rows[levels[key]].append(key)
    width = max(1500, max(map(len, rows), default=1) * 500 + 60)
    height = 180 + len(rows) * 280
    canvas = Image.new('RGB', (width, height), '#f5f7fb')
    draw = ImageDraw.Draw(canvas)
    draw.text((35, 22), value['title'], font=font(32, True), fill='#172554')
    draw.text((35, 73), f"개념 {len(nodes)}개 · 연결 {len(value['relations'])}개 · 짧은 지시문 추출 실험", font=font(20), fill='#475569')
    draw.text((35, 110), '노드에는 핵심 내용 일부를 표시합니다. 전체 내용·연결 설명·근거는 JSON/HTML에서 확인할 수 있습니다.', font=font(18), fill='#64748b')
    positions = {}
    for level, row in enumerate(rows):
        for i, key in enumerate(row):
            positions[key] = ((width - len(row) * 500) // 2 + i * 500 + 20, 170 + level * 280)
    for i, edge in enumerate(value['relations']):
        x, y = positions[edge['from_id']]
        xx, yy = positions[edge['to_id']]
        a, b = (x + 230, y + 220), (xx + 230, yy)
        c, d = (a[0], a[1] + 45), (b[0], b[1] - 45)
        pts = []
        for j in range(41):
            t = j / 40
            pts.append(tuple((1-t)**3*a[k] + 3*(1-t)**2*t*c[k] + 3*(1-t)*t*t*d[k] + t**3*b[k] for k in (0, 1)))
        color = '#94a3b8' if i in primary else '#a78bfa'
        if i in primary:
            draw.line(pts, fill=color, width=3)
        else:
            for j in range(0, 40, 4):
                draw.line(pts[j:j+3], fill=color, width=3)
        angle = math.atan2(pts[-1][1]-pts[-2][1], pts[-1][0]-pts[-2][0])
        arrow = [b, (b[0]-12*math.cos(angle-.4), b[1]-12*math.sin(angle-.4)), (b[0]-12*math.cos(angle+.4), b[1]-12*math.sin(angle+.4))]
        draw.polygon(arrow, fill=color)
    palette = ['#dbeafe', '#d1fae5', '#fef3c7', '#ede9fe', '#fee2e2']
    for key, node in nodes.items():
        x, y = positions[key]
        draw.rounded_rectangle((x, y, x+460, y+220), radius=16, fill=palette[levels[key] % len(palette)], outline='#a5b4cf', width=2)
        title = node['title']
        title_lines = [title[i:i+21] for i in range(0, len(title), 21)]
        for j, line in enumerate(title_lines[:2]):
            draw.text((x+15, y+14+j*30), line, font=font(23, True), fill='#172554')
        facts = ' · '.join(node['core_facts'])
        lines = [facts[i:i+27] for i in range(0, len(facts), 27)]
        for j, line in enumerate(lines[:4]):
            suffix = '…' if j == 3 and len(lines) > 4 else ''
            draw.text((x+15, y+85+j*27), line+suffix, font=font(18), fill='#334155')
    canvas.save(folder / 'map-preview.png')
    print(str(folder / 'map-preview.png'))
