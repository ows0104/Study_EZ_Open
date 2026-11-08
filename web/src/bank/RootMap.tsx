import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react';
import type { RootMapData, RootSummary } from '../types/rootLearning';
import { ancestors, buildTree, lanes, lanesPerRow, questionsOf, STATUS_LABEL, type Status, type TreeNode } from './rootMapTree';

/*
 * 개념 지도 — 가지 보기(2026-11-09).
 *
 * 강의 제목 아래로 최상위 주제마다 열(가지)이 하나씩, 열 안에서 하위 주제가 위→아래로 내려간다.
 * 처음부터 모든 주제가 보이고(접힌 것이 없다), 문항은 주제 줄 끝의 상태 점이다.
 * 주제를 누르면 그 줄 아래로 문항이 펼쳐지고, 계통·다른 가지와의 연결선이 강조되며, 지도 위에 패널이 겹친다.
 *
 * 화면은 지도 하나다(사용자 2026-11-09 「필요없는 거 싹 다 날리고 화면을 최대한 넓게, 안 움직이게」).
 * 남은 화면을 다 채우고, 확대·끌기 없이 항상 틀에 맞춘다. 너무 작아지면(0.5 미만) 폭에 맞추고 틀 안에서만 세로로 스크롤한다.
 * 줄은 HTML로 그리고, 가지선·연결선만 SVG 겹침층에 그린다. 좁은 화면은 세로 목록이다.
 */
const STATUSES:Status[]=['is-new','is-learning','is-recalled','is-unready'];
const PAD=20,TOOLS=46,MIN_READ=0.5,MAX_K=1.2,LANE_W=236,LANE_GAP=16,BOTTOM=12,MIN_FRAME=360;
const HUES=['#5466cf','#cf4f68','#b07a12','#8a5cc7','#18978a','#2d83c6','#4c9a35','#c0622b'];
const NARROW='(max-width:760px)';
type Fit={x:number;y:number;k:number;scroll:boolean};
type Box={x:number;y:number;w:number;h:number};
type Geo={w:number;h:number;boxes:Map<string,Box>};
const pageText=(pages:number[])=>!pages.length?'':pages.length===1?`p.${pages[0]}`:`p.${pages[0]}–${pages[pages.length-1]}`;
const total=(n:TreeNode)=>STATUSES.reduce((s,k)=>s+n.counts[k],0);
/** 판의 관계는 뜻을 `condition`에, 검수 메모를 `reason`에 둔다. 뜻이 있으면 그것을 보인다. */
const meaning=(r:{reason:string})=>(r as {condition?:string}).condition?.trim()||r.reason;

function useNarrow(){
  const [narrow,setNarrow]=useState(()=>typeof matchMedia==='function'&&matchMedia(NARROW).matches);
  useEffect(()=>{const m=matchMedia(NARROW),f=()=>setNarrow(m.matches);f();m.addEventListener('change',f);return()=>m.removeEventListener('change',f);},[]);
  return narrow;
}

function Counts({node}:{node:TreeNode}){
  if(!total(node))return null;
  return <span className="main-quiz-tree-bar" aria-hidden="true">{STATUSES.map(k=>node.counts[k]?
    <i key={k} className={k} style={{flexGrow:node.counts[k]}}/>:null)}</span>;
}

/** 위치는 transform을 무시한 world 좌표다(offset 사슬). */
function boxOf(el:HTMLElement,world:HTMLElement):Box{
  let x=0,y=0;
  for(let e:HTMLElement|null=el;e&&e!==world;e=e.offsetParent as HTMLElement|null){x+=e.offsetLeft;y+=e.offsetTop;}
  return {x,y,w:el.offsetWidth,h:el.offsetHeight};
}
/** 다른 가지면 가로질러, 같은 가지면 오른쪽으로 고리를 그린다. */
function crossPath(a:Box,b:Box){
  const ay=a.y+Math.min(a.h/2,16),by=b.y+Math.min(b.h/2,16),acx=a.x+a.w/2,bcx=b.x+b.w/2;
  if(Math.abs(acx-bcx)<LANE_W/2){
    const x=Math.max(a.x+a.w,b.x+b.w),bulge=24+Math.min(60,Math.abs(ay-by)*0.18);
    return `M${a.x+a.w} ${ay} C${x+bulge} ${ay} ${x+bulge} ${by} ${b.x+b.w} ${by}`;
  }
  const right=acx<bcx,x1=right?a.x+a.w:a.x,x2=right?b.x:b.x+b.w;
  const dx=Math.max(40,Math.abs(x2-x1)*0.45)*(right?1:-1);
  return `M${x1} ${ay} C${x1+dx} ${ay} ${x2-dx} ${by} ${x2} ${by}`;
}

export function RootMap({map,summary,title='강의 전체'}:{map:RootMapData;summary:RootSummary;position?:string;title?:string}) {
  const tree=useMemo(()=>buildTree(map,summary,title),[map,summary,title]);
  const columns=useMemo(()=>lanes(tree),[tree]);
  const laneOf=useMemo(()=>{const m=new Map<string,number>();columns.forEach((l,i)=>{m.set(l.head,i);
    for(const r of l.rows){m.set(r.id,i);for(const q of questionsOf(tree,r.id))m.set(q,i);}
    for(const q of questionsOf(tree,l.head))m.set(q,i);});return m;},[columns,tree]);
  const narrow=useNarrow();
  const [open,setOpen]=useState(()=>{const s=new Set<string>(),c=tree.currentId?tree.nodes.get(tree.currentId):null;
    if(c?.parent&&c.parent!==tree.rootId)s.add(c.parent);return s;});
  const [allOpen,setAllOpen]=useState(false);
  const [showAll,setShowAll]=useState(false);
  const [selected,setSelected]=useState<string|null>(null);
  const [side,setSide]=useState<'left'|'right'>('right');
  const [large,setLarge]=useState(false);
  const [fit,setFit]=useState<Fit>({x:PAD,y:PAD,k:1,scroll:false});
  const [geo,setGeo]=useState<Geo|null>(null);
  const [frameH,setFrameH]=useState<number|null>(null);
  const frame=useRef<HTMLDivElement>(null);
  const stage=useRef<HTMLDivElement>(null);
  const world=useRef<HTMLDivElement>(null);
  const reveal=useRef<string|null>(null);
  const byId=new Map(map.concepts.map(c=>[c.concept_id,c]));
  const targets=new Map(map.targets.map(t=>[t.target_id,t]));
  const node=selected?tree.nodes.get(selected)??null:null;

  // Cross links: concept relations whose ends are both tree topics (answer nodes are not topics).
  const nodeOf=useMemo(()=>{const m=new Map<string,string>();
    for(const n of tree.nodes.values())if(n.kind==='concept')for(const id of n.conceptIds)m.set(id,n.id);return m;},[tree]);
  const allLinks=useMemo(()=>{const seen=new Set<string>();
    return map.relations.map(r=>({...r,a:nodeOf.get(r.from_id),b:nodeOf.get(r.to_id)}))
      .filter((r):r is typeof r&{a:string;b:string}=>{
        if(!r.a||!r.b||r.a===r.b)return false;const key=[r.a,r.b].sort().join('|');if(seen.has(key))return false;seen.add(key);return true;});},[map.relations,nodeOf]);
  const linked=node?.kind==='concept'?allLinks.filter(r=>r.a===node.id||r.b===node.id).slice(0,20):[];
  const linkedIds=new Set(linked.map(r=>r.a===node?.id?r.b:r.a));

  // Lit context of the selection: its ancestors and everything under it.
  const context=useMemo(()=>{
    const set=new Set<string>();if(!selected||!tree.nodes.has(selected))return set;
    for(const a of ancestors(tree,selected))set.add(a);
    (function down(id:string){for(const c of tree.nodes.get(id)!.children){set.add(c);down(c);}})(selected);
    return set;
  },[selected,tree]);
  const tone=(id:string)=>!selected?'':id===selected?' is-selected':linkedIds.has(id)?' is-linked':context.has(id)?' is-context':' is-dim';
  const shown=(id:string)=>allOpen||open.has(id);

  /** Fit the whole map. Below MIN_READ, fit the width and let the frame scroll vertically.
   *  `keep`: a click opened or closed question rows — keep scale and place (the map must not jump);
   *  only switch scrolling on if the rows now run past the frame. */
  function fitTo(g:Geo|null,keep=false){
    const s=stage.current;if(!g||!s||narrow)return;
    const w=s.clientWidth,h=s.clientHeight-TOOLS;
    if(keep){setFit(f=>{const scroll=g.h*f.k+f.y+PAD>h;return scroll===f.scroll?f:{...f,scroll};});return;}
    let k=Math.min((w-PAD*2)/g.w,(h-PAD*2)/g.h,MAX_K),scroll=false;
    if(k<MIN_READ){k=Math.max(MIN_READ,Math.min((w-PAD*2)/g.w,MAX_K));scroll=g.h*k+PAD*2>h;}
    const x=Math.max(PAD,(w-g.w*k)/2),y=scroll?PAD:Math.max(PAD,(h-g.h*k)/2*0.4);
    setFit(f=>f.x===x&&f.y===y&&f.k===k&&f.scroll===scroll?f:{x,y,k,scroll});
  }
  function measure(){
    const w=world.current;if(!w)return null;
    const boxes=new Map<string,Box>();
    w.querySelectorAll<HTMLElement>('[data-node]').forEach(el=>boxes.set(el.dataset.node!,boxOf(el,w)));
    const g={w:w.offsetWidth,h:w.offsetHeight,boxes};setGeo(g);return g;
  }
  // Full re-fit only when what the map shows as a whole changes; a click keeps the map still.
  const shape=useRef('');
  useLayoutEffect(()=>{
    const g=measure(),now=[tree.rootId,tree.leaves,allOpen,narrow].join('|');
    fitTo(g,shape.current===now);shape.current=now;
    if(reveal.current){const id=reveal.current;reveal.current=null;
      world.current?.querySelector<HTMLElement>(`[data-node="${CSS.escape(id)}"]`)?.scrollIntoView({block:'nearest'});}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[open,allOpen,selected,narrow,tree,showAll]);
  // The frame fills what is left of the window below it; re-fit whenever the frame or the map changes size.
  useLayoutEffect(()=>{
    const place=()=>{const f=frame.current;if(!f)return;
      setFrameH(Math.max(MIN_FRAME,Math.floor(innerHeight-(f.getBoundingClientRect().top+scrollY)-BOTTOM)));};
    place();addEventListener('resize',place);return()=>removeEventListener('resize',place);
  },[]);
  useEffect(()=>{
    if(typeof ResizeObserver!=='function')return;
    // Frame resized (window, 크게 보기) → re-fit. Map resized (fonts, rows) → re-measure lines, keep the fit.
    const ro=new ResizeObserver(()=>fitTo(measure()));
    const rw=new ResizeObserver(()=>fitTo(measure(),true));
    if(stage.current)ro.observe(stage.current);if(world.current)rw.observe(world.current);
    return()=>{ro.disconnect();rw.disconnect();};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[narrow]);

  /** Topic: select and open its questions (again → close). Question: select, keep its topic open.
   *  The panel lies over the map on the side away from what was picked, so the map never moves. */
  function choose(id:string,{toggle=false}={}){
    const n=tree.nodes.get(id);if(!n)return;
    if(n.kind==='root'){setSelected(null);return;}
    const next=new Set(open);
    if(n.kind==='concept'&&toggle&&selected===id){next.delete(id);setOpen(next);setSelected(null);return;}
    if(n.kind==='concept'&&questionsOf(tree,id).length)next.add(id);
    if(n.kind==='target'&&n.parent)next.add(n.parent);
    const b=geo?.boxes.get(id),w=stage.current?.clientWidth??0;
    if(b&&w)setSide(b.x*fit.k+fit.x+b.w*fit.k/2>w/2?'left':'right');
    setOpen(next);setSelected(id);reveal.current=id;
  }
  useEffect(()=>{
    const key=(e:KeyboardEvent)=>{
      if(e.key!=='Escape'||(e.target as HTMLElement).closest('input,textarea,select'))return;
      if(large)setLarge(false);else setSelected(null);
    };
    addEventListener('keydown',key);return()=>removeEventListener('keydown',key);
  },[large]);

  const target=node?.targetId?targets.get(node.targetId):undefined;
  const rootNode=tree.nodes.get(tree.rootId)!;
  const perRow=lanesPerRow(columns.length);
  const topics=[...tree.nodes.values()].filter(n=>n.kind==='concept').length;

  const press=(id:string)=>({onClick:()=>choose(id,{toggle:true}),
    onKeyDown:(e:ReactKeyboardEvent)=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(id,{toggle:true});}}});

  function questionRows(id:string){
    const qs=questionsOf(tree,id);
    if(!qs.length||!shown(id))return null;
    return <div className="mq-lane-questions">{qs.map(q=>{const t=tree.nodes.get(q)!;
      return <div key={q} data-node={q} role="button" tabIndex={0} aria-pressed={selected===q}
        aria-label={`문항 ${t.label} · ${STATUS_LABEL[t.status!]}${t.current?' · 현재 문제':''}`}
        className={`mq-lane-q ${t.status}${t.current?' is-current':''}${tone(q)}`} {...press(q)}>
        <i className="mq-lane-dot" aria-hidden="true"/>
        <span className="mq-lane-qtext">{t.label}{t.current&&<em>현재</em>}</span>
        {t.pages.length>0&&<small>{pageText(t.pages)}</small>}
      </div>;})}</div>;
  }
  function dots(id:string){
    const qs=questionsOf(tree,id);
    if(!qs.length)return null;
    return <span className="mq-lane-dots" aria-hidden="true">{qs.map(q=>{const t=tree.nodes.get(q)!;
      return <i key={q} className={`${t.status}${t.current?' is-current':''}`}/>;})}</span>;
  }
  function topic(id:string,head:boolean,index=0){
    const n=tree.nodes.get(id)!,qs=questionsOf(tree,id),sum=total(n);
    return <div data-node={id} role="button" tabIndex={0} aria-pressed={selected===id}
      aria-expanded={qs.length?shown(id):undefined}
      aria-label={`주제 ${n.label} · 문항 ${sum}개`}
      className={`mq-lane-node${head?' is-head':''}${n.current?' is-current':''}${tone(id)}`} {...press(id)}>
      {head&&<span className="mq-lane-num">{String(index+1).padStart(2,'0')}</span>}
      <span className="mq-lane-row"><b>{n.label}</b>{dots(id)}</span>
      {head&&<><small>{n.pages.length?pageText(n.pages)+' · ':''}문항 {sum}개</small><Counts node={n}/></>}
    </div>;
  }
  function branch(id:string):ReactNode{
    const kids=tree.nodes.get(id)!.children.filter(c=>tree.nodes.get(c)!.kind==='concept');
    return <li key={id}>{topic(id,false)}{questionRows(id)}{kids.length>0&&<ul>{kids.map(branch)}</ul>}</li>;
  }

  // Lines in world coordinates: lecture → each first-row lane head, then the selected (or all) cross links.
  let wires:ReactNode=null;
  if(geo&&!narrow){
    const root=geo.boxes.get(tree.rootId),heads=columns.map(l=>geo.boxes.get(l.head)).filter(Boolean) as Box[];
    const firstY=Math.min(...heads.map(b=>b.y)),row=heads.filter(b=>Math.abs(b.y-firstY)<2);
    const busY=root?root.y+root.h+(firstY-root.y-root.h)/2:0;
    const cross=(showAll?allLinks:linked).map(r=>{const a=geo.boxes.get(r.a),b=geo.boxes.get(r.b);if(!a||!b)return null;
      const lit=!!node&&(r.a===node.id||r.b===node.id),other=r.a===node?.id?r.b:r.a;
      return <path key={r.relation_id} className={`mq-lane-cross${lit?' is-lit':''}`}
        style={{'--lane':HUES[(laneOf.get(lit?other:r.a)??0)%HUES.length]} as CSSProperties} d={crossPath(a,b)}><title>{meaning(r)}</title></path>;});
    wires=<svg className="mq-lane-wires" width={geo.w} height={geo.h} aria-hidden="true">
      {root&&row.length>0&&<path className="mq-lane-bus" d={`M${root.x+root.w/2} ${root.y+root.h} V${busY} M${Math.min(...row.map(b=>b.x+b.w/2))} ${busY} H${Math.max(...row.map(b=>b.x+b.w/2))}`
        +row.map(b=>` M${b.x+b.w/2} ${busY} V${b.y}`).join('')}/>}
      {cross}
    </svg>;
  }

  return <section className={`main-quiz-map${large?' is-large':''}`}>
    <h2 className="sr-only">개념 지도</h2>
    <div ref={frame} className="main-quiz-tree-frame" style={large||frameH==null?undefined:{height:frameH}}>
      <div ref={stage} className={`main-quiz-tree-stage${narrow?' is-narrow':fit.scroll?' is-scroll':''}`}
        onClick={e=>{if(!(e.target as Element).closest('[data-node],.main-quiz-tree-tools'))setSelected(null);}}>
        <div ref={world} role="group" aria-label="개념 트리" className={`mq-lanes-world${selected?' has-selection':''}`}
          style={narrow?undefined:{transform:`translate(${fit.x}px,${fit.y}px) scale(${fit.k})`}}>
          {wires}
          <div data-node={tree.rootId} role="button" tabIndex={0} aria-label={`강의 ${rootNode.label} · 가지 ${columns.length}개 · 주제 ${topics}개 · 문항 ${tree.leaves}개`}
            className="mq-lane-root" {...press(tree.rootId)}>
            <b>{rootNode.label}</b><small>가지 {columns.length}개 · 주제 {topics}개 · 문항 {tree.leaves}개</small><Counts node={rootNode}/>
          </div>
          <div className="mq-lanes" style={narrow?undefined:{gridTemplateColumns:`repeat(${perRow},${LANE_W}px)`,gap:`28px ${LANE_GAP}px`}}>
            {columns.map((l,i)=>{const kids=tree.nodes.get(l.head)!.children.filter(c=>tree.nodes.get(c)!.kind==='concept');
              return <section key={l.head} className="mq-lane" style={{'--lane':HUES[i%HUES.length]} as CSSProperties}>
                {topic(l.head,true,i)}
                {questionRows(l.head)}
                {kids.length>0&&<ul className="mq-lane-tree">{kids.map(branch)}</ul>}
              </section>;})}
          </div>
        </div>
        {fit.scroll&&geo&&!narrow&&<div className="mq-lanes-spacer" style={{height:geo.h*fit.k+PAD*2}} aria-hidden="true"/>}
      </div>
      <div className="main-quiz-tree-tools">
        <span className="mq-map-legend" aria-label="학습 상태 색">{STATUSES.map(s=><span key={s} className={s}>{STATUS_LABEL[s]}</span>)}</span>
        {tree.currentId&&<button onClick={()=>choose(tree.currentId!)}>현재 문제</button>}
        <button aria-pressed={allOpen} onClick={()=>{setAllOpen(!allOpen);if(allOpen)setOpen(new Set());}}>{allOpen?'문항 접기':'문항 펼치기'}</button>
        {!narrow&&<button aria-pressed={showAll} onClick={()=>setShowAll(!showAll)}>연결선 {showAll?'숨기기':'전체'}</button>}
        <button onClick={()=>setLarge(!large)}>{large?'작게 보기':'크게 보기'}</button>
      </div>
      {node&&node.kind!=='root'&&<aside className={`main-quiz-tree-panel is-${side}`} aria-label="선택한 항목">
        <button className="main-quiz-tree-close" onClick={()=>setSelected(null)} aria-label="닫기">×</button>
        <p className="main-quiz-tree-kicker">{node.kind==='concept'?'주제':'문항'}{node.pages.length?' · '+pageText(node.pages):''}
          {node.status&&<span className={`main-quiz-tree-chip ${node.status}`}>{STATUS_LABEL[node.status]}</span>}
          {node.current&&node.kind==='target'&&<span className="main-quiz-tree-chip is-current">현재 문제</span>}</p>
        <h3>{node.label}</h3>
        {node.parent&&node.parent!==tree.rootId&&<p className="bank-note"><button className="main-quiz-tree-link" onClick={()=>choose(node.parent!)}>‹ {tree.nodes.get(node.parent)!.label}</button></p>}
        {node.kind==='concept'&&<>
          <p className="main-quiz-tree-counts">{STATUSES.filter(s=>node.counts[s]).map(s=><span key={s} className={s}>{STATUS_LABEL[s]} {node.counts[s]}</span>)}</p>
          <ul className="main-quiz-tree-children">{node.children.map(c=>{const child=tree.nodes.get(c)!;return <li key={c}>
            <button className={`main-quiz-tree-link ${child.status??''}`} onClick={()=>choose(c)}>{child.label}</button>
            <span className="bank-note">{child.kind==='target'?`${STATUS_LABEL[child.status!]}${child.pages.length?' · '+pageText(child.pages):''}${child.current?' · 현재 문제':''}`:'주제'}</span></li>;})}</ul>
          {linked.length>0&&<><h4>다른 주제와의 연결</h4><ul>{linked.map(r=>{const other=r.a===node.id?r.b:r.a;return <li key={r.relation_id}>
            <button className="main-quiz-tree-link" onClick={()=>choose(other)}>{byId.get(r.from_id)?.label??r.from_id} → {byId.get(r.to_id)?.label??r.to_id}</button>
            <p className="bank-note">{meaning(r)}</p></li>;})}</ul></>}
        </>}
        {target&&<>
          {target.directions.length>1&&<ul>{target.directions.map(d=><li key={d.direction_id}>{d.cue}</li>)}</ul>}
          <details className="main-quiz-details"><summary>답 범위 보기</summary>
            {target.directions.map(d=><p key={d.direction_id}>{target.directions.length>1&&<span className="bank-note">{d.cue} → </span>}{d.answer_scope}
              {map.readyDirectionIds&&!map.readyDirectionIds.includes(d.direction_id)&&<span className="bank-note"> · 학습 연결 준비 전</span>}</p>)}
          </details>
          <details className="main-quiz-details"><summary>중요도 근거</summary><dl>{(['structural','exam','clinical'] as const).map((axis,i)=>
            target.importance[axis]&&<div key={axis}><dt>{['이해의 뼈대','시험 근거','임상 근거'][i]}</dt><dd>{target.importance[axis].reason}</dd></div>)}</dl></details>
        </>}
      </aside>}
    </div>
  </section>;
}
