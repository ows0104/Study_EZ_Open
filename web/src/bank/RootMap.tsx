import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react';
import type { RootMapData, RootSummary } from '../types/rootLearning';
import { ancestors, buildTree, lanes, lanesPerRow, questionsOf, STATUS_LABEL, type Status, type Tree, type TreeNode } from './rootMapTree';

/*
 * 개념 지도 — 가지 보기(2026-11-09).
 *
 * 강의 제목 아래로 최상위 주제마다 열(가지)이 하나씩, 열 안에서 하위 주제가 위→아래로 내려간다.
 * 처음부터 모든 주제가 보이고(접힌 것이 없다), 문항은 주제 줄 끝의 상태 점이다.
 * 주제를 누르면 그 줄 아래로 문항이 펼쳐지고, 계통·다른 가지와의 연결선이 강조되며, 옆 패널에 자세한 내용이 나온다.
 * 줄은 HTML로 그리고(글자 줄바꿈), 가지선·연결선만 SVG 겹침층에 그린다. 좁은 화면은 확대 캔버스 대신 세로 목록이다.
 */
const STATUSES:Status[]=['is-new','is-learning','is-recalled','is-unready'];
const POINT_STATUS:Record<string,string>={covered:'충족',partial:'일부 충족',gap:'미출제',unknown:'검토 필요',excluded:'범위 제외'};
const PAD=24,TOOLS=48,MIN_K=0.25,MAX_K=2.6,FIT_MIN_K=0.55,DETAIL_K=1.15,LANE_W=236,LANE_GAP=16;
const HUES=['#5466cf','#cf4f68','#b07a12','#8a5cc7','#18978a','#2d83c6','#4c9a35','#c0622b'];
const NARROW='(max-width:760px)';
type View={x:number;y:number;k:number};
type Box={x:number;y:number;w:number;h:number};
type Geo={w:number;h:number;boxes:Map<string,Box>};
const clamp=(v:number,a:number,b:number)=>Math.max(a,Math.min(b,v));
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
  const sum=total(node);
  if(!sum)return null;
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

function initialOpen(tree:Tree){
  const open=new Set<string>();
  const current=tree.currentId?tree.nodes.get(tree.currentId):null;
  if(current?.parent&&current.parent!==tree.rootId)open.add(current.parent);
  return open;
}

export function RootMap({map,summary,position,title='강의 전체'}:{map:RootMapData;summary:RootSummary;position:string;title?:string}) {
  const tree=useMemo(()=>buildTree(map,summary,title),[map,summary,title]);
  const columns=useMemo(()=>lanes(tree),[tree]);
  const laneOf=useMemo(()=>{const m=new Map<string,number>();columns.forEach((l,i)=>{m.set(l.head,i);
    for(const r of l.rows){m.set(r.id,i);for(const q of questionsOf(tree,r.id))m.set(q,i);}
    for(const q of questionsOf(tree,l.head))m.set(q,i);});return m;},[columns,tree]);
  const narrow=useNarrow();
  const [open,setOpen]=useState(()=>initialOpen(tree));
  const [allOpen,setAllOpen]=useState(false);
  const [showAll,setShowAll]=useState(false);
  const [selected,setSelected]=useState<string|null>(null);
  const [search,setSearch]=useState('');
  const [large,setLarge]=useState(false);
  const [view,setView]=useState<View>({x:PAD,y:PAD,k:1});
  const [geo,setGeo]=useState<Geo|null>(null);
  const stage=useRef<HTMLDivElement>(null);
  const world=useRef<HTMLDivElement>(null);
  const viewRef=useRef(view);viewRef.current=view;
  const geoRef=useRef(geo);geoRef.current=geo;
  const anim=useRef<number>(0);
  const reveal=useRef<string|null>(null);
  const fitted=useRef(false);
  const drag=useRef<{pointers:Map<number,{x:number;y:number}>;start?:View;origin?:{x:number;y:number};pinch?:{d:number;k:number};moved:number}>({pointers:new Map(),moved:0});
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

  function size(){const r=stage.current?.getBoundingClientRect();return {w:r?.width||800,h:r?.height||560};}
  function flyTo(next:View,ms=420){
    cancelAnimationFrame(anim.current);
    const from=viewRef.current,start=performance.now();
    const step=(now:number)=>{const p=Math.min(1,(now-start)/ms),e=p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;
      setView({x:from.x+(next.x-from.x)*e,y:from.y+(next.y-from.y)*e,k:from.k+(next.k-from.k)*e});
      if(p<1)anim.current=requestAnimationFrame(step);};
    if(matchMedia('(prefers-reduced-motion: reduce)').matches)setView(next);else anim.current=requestAnimationFrame(step);
  }
  /** Whole map in the frame. Too big to stay readable → keep FIT_MIN_K and show it from the top. */
  function fitAll(animate=true,g=geoRef.current){
    if(!g||narrow)return;
    const {w,h}=size(),usable=h-TOOLS;
    const k=clamp(Math.min((w-PAD*2)/g.w,(usable-PAD*2)/g.h,1),FIT_MIN_K,MAX_K);
    const x=g.w*k<=w-PAD*2?(w-g.w*k)/2:PAD,y=g.h*k<=usable-PAD*2?Math.max(PAD,(usable-g.h*k)/2*0.4):PAD;
    if(animate)flyTo({x,y,k});else setView({x,y,k});
  }
  /** Bring one node into view without changing a readable zoom. */
  function bring(id:string,g=geoRef.current){
    const b=g?.boxes.get(id);if(!b)return;
    if(narrow){world.current?.querySelector<HTMLElement>(`[data-node="${CSS.escape(id)}"]`)?.scrollIntoView({block:'center',behavior:'smooth'});return;}
    const v=viewRef.current,{w,h}=size(),usable=h-TOOLS,k=Math.max(v.k,0.85);
    const sx=b.x*k+v.x,sy=b.y*k+v.y;
    if(k===v.k&&sx>PAD&&sx+b.w*k<w-PAD&&sy>PAD&&sy+Math.min(b.h,120)*k<usable-PAD)return;
    flyTo({k,x:w/2-(b.x+b.w/2)*k,y:usable*0.4-(b.y+Math.min(b.h,120)/2)*k});
  }

  // Measure after every layout change; lines and framing read these boxes.
  function measure(){
    const w=world.current;if(!w)return null;
    const boxes=new Map<string,Box>();
    w.querySelectorAll<HTMLElement>('[data-node]').forEach(el=>boxes.set(el.dataset.node!,boxOf(el,w)));
    const g={w:w.offsetWidth,h:w.offsetHeight,boxes};setGeo(g);return g;
  }
  useLayoutEffect(()=>{
    const g=measure();if(!g)return;
    if(!fitted.current){fitted.current=true;fitAll(false,g);}
    if(reveal.current){const id=reveal.current;reveal.current=null;bring(id,g);}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[open,allOpen,selected,narrow,tree,large]);
  useEffect(()=>{
    const w=world.current;if(!w||typeof ResizeObserver!=='function')return;
    let last='';const ro=new ResizeObserver(()=>{const key=w.offsetWidth+'x'+w.offsetHeight;if(key!==last){last=key;measure();}});
    ro.observe(w);return()=>ro.disconnect();
  },[]);
  useEffect(()=>()=>cancelAnimationFrame(anim.current),[]);

  function zoomAt(factor:number,cx?:number,cy?:number){
    const v=viewRef.current,{w,h}=size(),px=cx??w/2,py=cy??h/2;
    const k=clamp(v.k*factor,MIN_K,MAX_K),wx=(px-v.x)/v.k,wy=(py-v.y)/v.k;
    cancelAnimationFrame(anim.current);setView({k,x:px-wx*k,y:py-wy*k});
  }
  useEffect(()=>{
    const el=stage.current;if(!el||narrow)return;
    const wheel=(e:WheelEvent)=>{e.preventDefault();const r=el.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY*(e.ctrlKey?0.01:0.0018)),e.clientX-r.left,e.clientY-r.top);};
    el.addEventListener('wheel',wheel,{passive:false});return()=>el.removeEventListener('wheel',wheel);
  },[narrow]);
  function pointerDown(e:ReactPointerEvent){
    if(narrow||e.button!==0)return;
    const d=drag.current;d.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(d.pointers.size===1){d.start=viewRef.current;d.origin={x:e.clientX,y:e.clientY};d.moved=0;d.pinch=undefined;}
    if(d.pointers.size===2){const [a,b]=[...d.pointers.values()];d.pinch={d:Math.hypot(a.x-b.x,a.y-b.y),k:viewRef.current.k};}
  }
  function pointerMove(e:ReactPointerEvent){
    const d=drag.current;if(!d.pointers.has(e.pointerId))return;
    d.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(d.pinch&&d.pointers.size===2){const [a,b]=[...d.pointers.values()],r=stage.current!.getBoundingClientRect();
      zoomAt(d.pinch.k*Math.hypot(a.x-b.x,a.y-b.y)/d.pinch.d/viewRef.current.k,(a.x+b.x)/2-r.left,(a.y+b.y)/2-r.top);d.moved=99;return;}
    if(!d.start||!d.origin)return;
    const dx=e.clientX-d.origin.x,dy=e.clientY-d.origin.y;d.moved=Math.max(d.moved,Math.hypot(dx,dy));
    if(d.moved>4){if(!stage.current!.hasPointerCapture(e.pointerId))stage.current!.setPointerCapture(e.pointerId);
      cancelAnimationFrame(anim.current);setView({...d.start,x:d.start.x+dx,y:d.start.y+dy});}
  }
  function pointerUp(e:ReactPointerEvent){const d=drag.current;d.pointers.delete(e.pointerId);if(!d.pointers.size){d.start=undefined;d.pinch=undefined;}}

  /** Topic: select and open its questions (again → close). Question: select, keep its topic open. */
  function choose(id:string,{toggle=false}={}){
    const n=tree.nodes.get(id);if(!n)return;
    if(n.kind==='root'){setSelected(null);fitAll();return;}
    const next=new Set(open);
    if(n.kind==='concept'&&toggle&&selected===id){next.delete(id);setOpen(next);setSelected(null);return;}
    if(n.kind==='concept'&&questionsOf(tree,id).length)next.add(id);
    if(n.kind==='target'&&n.parent)next.add(n.parent);
    setOpen(next);setSelected(id);reveal.current=id;
  }
  useEffect(()=>{
    const key=(e:KeyboardEvent)=>{
      const target=e.target as HTMLElement;
      if(!stage.current?.parentElement?.contains(target)&&target!==document.body)return;
      if(target.closest('input,textarea,select'))return;
      if(e.key==='+'||e.key==='=')zoomAt(1.25);
      else if(e.key==='-'||e.key==='_')zoomAt(0.8);
      else if(e.key==='0')fitAll();
      else if(e.key==='Escape'){if(large)setLarge(false);else setSelected(null);}
      else return;
      e.preventDefault();
    };
    window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);
  });
  // Re-fit only when the frame size actually changes (크게 보기), not on the first render.
  const sized=useRef(false);
  useEffect(()=>{if(!sized.current){sized.current=true;return;}const t=setTimeout(()=>fitAll(),30);return()=>clearTimeout(t);},[large]);

  const query=search.trim().toLocaleLowerCase();
  const hits=query?[...tree.nodes.values()].filter(n=>n.kind!=='root'&&n.label.toLocaleLowerCase().includes(query)).slice(0,12):[];
  const detail=!narrow&&view.k>=DETAIL_K;
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
      {head?<><small>{n.pages.length?pageText(n.pages)+' · ':''}문항 {sum}개</small><Counts node={n}/></>
        :detail&&<small className="mq-lane-meta">{n.pages.length?pageText(n.pages)+' · ':''}문항 {sum}개</small>}
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
    <header className="bank-cmap-heading"><h2>개념 지도</h2><span>{position}</span></header>
    <p className="bank-note">강의 전체가 한 화면에 있어요. 주제를 누르면 문항과 연결이 보이고, 휠·두 손가락으로 확대합니다.</p>
    <div className="main-quiz-map-search">
      <label>찾기 <input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="주제·문항"/></label>
      <span className="bank-note">주제 {topics}개 · 문항 {tree.leaves}개</span>
      {hits.length>0&&<ul>{hits.map(n=><li key={n.id}><button onClick={()=>{choose(n.id);setSearch('');}}>
        <span className="bank-note">{n.kind==='concept'?'주제':'문항'}</span> {n.label}</button></li>)}</ul>}
      {query&&!hits.length&&<span className="bank-note">찾는 항목이 없어요</span>}
    </div>
    <p className="main-quiz-map-legend">{STATUSES.map(s=><span key={s} className={s}>{STATUS_LABEL[s]}</span>)}<span className="is-current">현재 문제</span><span className="is-line">다른 주제와의 연결</span></p>
    <div className="main-quiz-tree-frame">
      <div ref={stage} className={`main-quiz-tree-stage${narrow?' is-narrow':''}`} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp}
        onClickCapture={e=>{if(drag.current.moved>4){e.stopPropagation();e.preventDefault();drag.current.moved=0;}}}
        onClick={e=>{if(!(e.target as Element).closest('[data-node],.main-quiz-tree-tools'))setSelected(null);}}
        onDoubleClick={e=>{if(!(e.target as Element).closest('[data-node]'))fitAll();}}>
        <div ref={world} role="group" aria-label="개념 트리" className={`mq-lanes-world${selected?' has-selection':''}${detail?' is-detail':''}`}
          style={narrow?undefined:{transform:`translate(${view.x}px,${view.y}px) scale(${view.k})`}}>
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
        <div className="main-quiz-tree-tools" onPointerDown={e=>e.stopPropagation()}>
          {!narrow&&<><button onClick={()=>zoomAt(1.25)} aria-label="확대">＋</button>
          <button onClick={()=>zoomAt(0.8)} aria-label="축소">－</button>
          <button onClick={()=>fitAll()}>전체</button></>}
          {tree.currentId&&<button onClick={()=>choose(tree.currentId!)}>현재 문제</button>}
          <button aria-pressed={allOpen} onClick={()=>{setAllOpen(!allOpen);if(allOpen)setOpen(new Set());}}>{allOpen?'문항 접기':'문항 펼치기'}</button>
          {!narrow&&<button aria-pressed={showAll} onClick={()=>setShowAll(!showAll)}>연결선 {showAll?'숨기기':'전체'}</button>}
          <button onClick={()=>setLarge(!large)}>{large?'작게 보기':'크게 보기'}</button>
        </div>
      </div>
      {node&&node.kind!=='root'&&<aside className="main-quiz-tree-panel" aria-label="선택한 항목">
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
    <details className="main-quiz-details"><summary>목록으로 보기</summary>
      <ol className="main-quiz-tree-outline">{rootNode.children.map(function item(id:string):ReactNode{const n=tree.nodes.get(id)!;
        return <li key={id}><button className={`main-quiz-tree-link ${n.status??''}`} onClick={()=>choose(id)}>{n.label}</button>
          <span className="bank-note"> {n.kind==='target'?STATUS_LABEL[n.status!]:`문항 ${total(n)}개`}{n.pages.length?' · '+pageText(n.pages):''}</span>
          {n.children.length>0&&<ol>{n.children.map(item)}</ol>}</li>;})}</ol>
    </details>
    <details className="main-quiz-details"><summary>자료 범위·출제포인트</summary><p>{map.scope.label}</p>{map.scope.limitations.map((text,i)=><p className="bank-note" key={i}>{text}</p>)}
      {map.points?.map(p=><p key={p.point_id}>{p.text} · {POINT_STATUS[map.coverage?.find(c=>c.point_id===p.point_id)?.status??'unknown']}</p>)}
    </details>
  </section>;
}
