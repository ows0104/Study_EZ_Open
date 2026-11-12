import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react';
import type { RootMapData, RootSummary } from '../types/rootLearning';
import { useFlagPreference } from '../preferences';
import { ancestors, buildTree, lanes, lanesPerRow, questionsOf, STATUS_LABEL, type Status, type TreeNode } from './rootMapTree';

/*
 * 개념 지도 — 가지 보기(2026-11-09).
 *
 * 강의 제목 아래로 최상위 주제마다 열(가지)이 하나씩, 열 안에서 하위 주제가 위→아래로 내려간다.
 * 처음부터 모든 주제가 보이고(접힌 것이 없다), 문항은 주제 줄 끝의 상태 점이다.
 * 주제를 누르면 그 줄 아래로 문항이 펼쳐지고, 계통·다른 가지와의 연결선이 강조되며, 지도 위에 패널이 겹친다.
 *
 * 화면은 지도 하나다(사용자 2026-11-09 「필요없는 거 싹 다 날리고 화면을 최대한 넓게」). 남은 화면을 다 채운다.
 * 처음엔 전체가 맞춰져 있고, 끌기·휠·두 손가락으로 움직이고 확대한다(같은 날 「움직이고 확대할 수 있게」).
 * 아직 움직이지 않았으면 영역이 바뀔 때(창·크게 보기·패널) 다시 맞춘다. 패널은 지도 옆에 붙어 지도를 가리지 않는다.
 * 줄은 HTML로 그리고, 가지선·연결선만 SVG 겹침층에 그린다. 좁은 화면은 세로 목록이다.
 */
const STATUSES:Status[]=['is-new','is-learning','is-recalled','is-unready'];
const PAD=20,TOOLS=46,FIT_MAX=1.2,MIN_K=0.25,MAX_K=2.6,LANE_W=236,LANE_GAP=16,MIN_FRAME=360;
const HUES=['#5466cf','#cf4f68','#b07a12','#8a5cc7','#18978a','#2d83c6','#4c9a35','#c0622b'];
const NARROW='(max-width:760px)';
type View={x:number;y:number;k:number};
const clamp=(v:number,a:number,b:number)=>Math.max(a,Math.min(b,v));
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

export function RootMap({map,summary,title='강의 전체',onBack,backTo='question'}:{map:RootMapData;summary:RootSummary;title?:string;onBack?:()=>void;
  /** Opened from the start screen without a session (2026-11-12): back goes to 오늘 추천. */
  backTo?:'question'|'today'}) {
  const tree=useMemo(()=>buildTree(map,summary,title),[map,summary,title]);
  const columns=useMemo(()=>lanes(tree),[tree]);
  const laneOf=useMemo(()=>{const m=new Map<string,number>();columns.forEach((l,i)=>{m.set(l.head,i);
    for(const r of l.rows){m.set(r.id,i);for(const q of questionsOf(tree,r.id))m.set(q,i);}
    for(const q of questionsOf(tree,l.head))m.set(q,i);});return m;},[columns,tree]);
  const narrow=useNarrow();
  const [open,setOpen]=useState(()=>{const s=new Set<string>(),c=tree.currentId?tree.nodes.get(tree.currentId):null;
    if(c?.parent&&c.parent!==tree.rootId)s.add(c.parent);return s;});
  // 한 번 누른 값을 이 브라우저에 기억한다(2026-11-11).
  const [allOpen,setAllOpen]=useFlagPreference('studyez-map-questions');
  const [showAll,setShowAll]=useFlagPreference('studyez-map-links');
  const [selected,setSelected]=useState<string|null>(null);
  const [large,setLarge]=useState(false);
  const [view,setView]=useState<View>({x:PAD,y:PAD,k:1});
  const [geo,setGeo]=useState<Geo|null>(null);
  const [frameH,setFrameH]=useState<number|null>(null);
  const frame=useRef<HTMLDivElement>(null);
  const stage=useRef<HTMLDivElement>(null);
  const world=useRef<HTMLDivElement>(null);
  const reveal=useRef<string|null>(null);
  const viewRef=useRef(view);viewRef.current=view;
  const geoRef=useRef<Geo|null>(null);
  /** The learner moved or zoomed: from then on keep their view instead of re-fitting. 「전체」 clears it. */
  const moved=useRef(false);
  const anim=useRef<number>(0);
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

  function size(){const r=stage.current;return {w:r?.clientWidth||800,h:(r?.clientHeight||560)-TOOLS};}
  function flyTo(next:View,ms=380){
    cancelAnimationFrame(anim.current);
    const from=viewRef.current,t0=performance.now();
    const step=(now:number)=>{const p=Math.min(1,(now-t0)/ms),e=p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;
      setView({x:from.x+(next.x-from.x)*e,y:from.y+(next.y-from.y)*e,k:from.k+(next.k-from.k)*e});
      if(p<1)anim.current=requestAnimationFrame(step);};
    if(matchMedia('(prefers-reduced-motion: reduce)').matches)setView(next);else anim.current=requestAnimationFrame(step);
  }
  /** Whole map in the map area (beside the panel, never under it). */
  function fitAll(g=geoRef.current,animate=false){
    if(!g||narrow||!stage.current)return;
    const {w,h}=size(),k=clamp(Math.min((w-PAD*2)/g.w,(h-PAD*2)/g.h,FIT_MAX),MIN_K,MAX_K);
    const next={k,x:Math.max(PAD,(w-g.w*k)/2),y:Math.max(PAD,(h-g.h*k)/2*0.4)};
    moved.current=false;
    if(animate)flyTo(next);else{cancelAnimationFrame(anim.current);setView(next);}
  }
  /** Bring one node into the map area, keeping the learner's zoom. */
  function bring(id:string,g=geoRef.current){
    const b=g?.boxes.get(id);if(!b||!stage.current)return;
    if(narrow){world.current?.querySelector<HTMLElement>(`[data-node="${CSS.escape(id)}"]`)?.scrollIntoView({block:'nearest'});return;}
    const v=viewRef.current,{w,h}=size(),bh=Math.min(b.h,140);
    const sx=b.x*v.k+v.x,sy=b.y*v.k+v.y;
    if(sx>=PAD/2&&sx+b.w*v.k<=w-PAD/2&&sy>=PAD/2&&sy+bh*v.k<=h-PAD/2)return;
    flyTo({k:v.k,x:w/2-(b.x+b.w/2)*v.k,y:h*0.4-(b.y+bh/2)*v.k});
  }
  /** Area or map changed: re-fit unless the learner has moved; otherwise keep their view and the pick in sight. */
  function settle(g:Geo|null){
    if(!g)return;
    if(!moved.current)fitAll(g);else if(selected)bring(selected,g);
  }
  function measure(){
    const w=world.current;if(!w)return null;
    const boxes=new Map<string,Box>();
    w.querySelectorAll<HTMLElement>('[data-node]').forEach(el=>boxes.set(el.dataset.node!,boxOf(el,w)));
    const g={w:w.offsetWidth,h:w.offsetHeight,boxes};geoRef.current=g;setGeo(g);return g;
  }
  // Re-measure after every layout change. A whole-map change (data, 문항 펼치기) re-fits an unmoved map;
  // a click that opens rows keeps the view and only brings the pick into sight.
  const shape=useRef('');
  useLayoutEffect(()=>{
    const g=measure(),now=[tree.rootId,tree.leaves,allOpen,narrow].join('|');
    if(shape.current!==now&&!moved.current)fitAll(g);
    shape.current=now;
    if(reveal.current){const id=reveal.current;reveal.current=null;bring(id,g);}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[open,allOpen,selected,narrow,tree,showAll]);
  // The frame fills what is left of the window below it; re-fit whenever the frame or the map changes size.
  useLayoutEffect(()=>{
    const place=()=>{const f=frame.current;if(!f)return;
      setFrameH(Math.max(MIN_FRAME,Math.floor(innerHeight-(f.getBoundingClientRect().top+scrollY))));};
    place();addEventListener('resize',place);return()=>removeEventListener('resize',place);
  },[]);
  useEffect(()=>{
    if(typeof ResizeObserver!=='function')return;
    // Map area resized (window, 크게 보기, panel opened/closed) → settle. Map resized (fonts, rows) → re-measure lines only.
    const ro=new ResizeObserver(()=>settle(measure()));
    const rw=new ResizeObserver(()=>measure());
    if(stage.current)ro.observe(stage.current);if(world.current)rw.observe(world.current);
    return()=>{ro.disconnect();rw.disconnect();};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[narrow,selected]);
  useEffect(()=>()=>cancelAnimationFrame(anim.current),[]);

  /** Topic: select and open its questions (again → close). Question: select, keep its topic open. */
  function choose(id:string,{toggle=false}={}){
    const n=tree.nodes.get(id);if(!n)return;
    if(n.kind==='root'){setSelected(null);return;}
    const next=new Set(open);
    if(n.kind==='concept'&&toggle&&selected===id){next.delete(id);setOpen(next);setSelected(null);return;}
    if(n.kind==='concept'&&questionsOf(tree,id).length)next.add(id);
    if(n.kind==='target'&&n.parent)next.add(n.parent);
    setOpen(next);setSelected(id);reveal.current=id;
  }
  function zoomAt(factor:number,cx?:number,cy?:number){
    const v=viewRef.current,{w,h}=size(),px=cx??w/2,py=cy??h/2;
    const k=clamp(v.k*factor,MIN_K,MAX_K),wx=(px-v.x)/v.k,wy=(py-v.y)/v.k;
    moved.current=true;cancelAnimationFrame(anim.current);setView({k,x:px-wx*k,y:py-wy*k});
  }
  /** Buttons and keys zoom around the picked node when there is one, else the middle of the map area. */
  function zoomStep(factor:number){
    const b=selected?geoRef.current?.boxes.get(selected):undefined,v=viewRef.current;
    if(b)zoomAt(factor,(b.x+b.w/2)*v.k+v.x,(b.y+Math.min(b.h,140)/2)*v.k+v.y);else zoomAt(factor);
  }
  useEffect(()=>{
    const el=stage.current;if(!el||narrow)return;
    const wheel=(e:WheelEvent)=>{e.preventDefault();const r=el.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY*(e.ctrlKey?0.01:0.0018)),e.clientX-r.left,e.clientY-r.top);};
    el.addEventListener('wheel',wheel,{passive:false});return()=>el.removeEventListener('wheel',wheel);
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
      moved.current=true;cancelAnimationFrame(anim.current);setView({...d.start,x:d.start.x+dx,y:d.start.y+dy});}
  }
  function pointerUp(e:ReactPointerEvent){const d=drag.current;d.pointers.delete(e.pointerId);if(!d.pointers.size){d.start=undefined;d.pinch=undefined;}}
  useEffect(()=>{
    const key=(e:KeyboardEvent)=>{
      const target=e.target as HTMLElement;
      if(target.closest('input,textarea,select'))return;
      if(e.key==='Escape'){if(large)setLarge(false);else setSelected(null);return;}
      if(narrow||!frame.current?.contains(target)&&target!==document.body)return;
      if(e.key==='+'||e.key==='=')zoomStep(1.25);
      else if(e.key==='-'||e.key==='_')zoomStep(0.8);
      else if(e.key==='0')fitAll(undefined,true);
      else return;
      e.preventDefault();
    };
    addEventListener('keydown',key);return()=>removeEventListener('keydown',key);
  });

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
      <div ref={stage} className={`main-quiz-tree-stage${narrow?' is-narrow':''}`}
        onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp}
        onClickCapture={e=>{if(drag.current.moved>4){e.stopPropagation();e.preventDefault();drag.current.moved=0;}}}
        onClick={e=>{if(!(e.target as Element).closest('[data-node]'))setSelected(null);}}
        onDoubleClick={e=>{if(!(e.target as Element).closest('[data-node]'))fitAll(undefined,true);}}>
        <div ref={world} role="group" aria-label="개념 트리" className={`mq-lanes-world${selected?' has-selection':''}`}
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
        <div className="main-quiz-tree-tools" onPointerDown={e=>e.stopPropagation()} onClick={e=>e.stopPropagation()}>
          {onBack&&<button className="mq-map-back" onClick={onBack} aria-label={backTo==='today'?'오늘 추천으로 돌아가기':'문제로 돌아가기'}>{backTo==='today'?'← 오늘':'← 문제'}</button>}
          {!narrow&&<><button onClick={()=>zoomStep(1.25)} aria-label="확대">＋</button>
          <button onClick={()=>zoomStep(0.8)} aria-label="축소">－</button>
          <button onClick={()=>fitAll(undefined,true)}>전체</button></>}
        <span className="mq-map-legend" aria-label="학습 상태 색">{STATUSES.map(s=><span key={s} className={s}>{STATUS_LABEL[s]}</span>)}</span>
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
  </section>;
}
