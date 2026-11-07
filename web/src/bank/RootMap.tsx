import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react';
import type { RootMapData, RootSummary } from '../types/rootLearning';
import { ancestors, buildTree, layout, STATUS_LABEL, type Status, type Tree, type TreeNode } from './rootMapTree';

const STATUSES:Status[]=['is-new','is-learning','is-recalled','is-unready'];
const POINT_STATUS:Record<string,string>={covered:'충족',partial:'일부 충족',gap:'미출제',unknown:'검토 필요',excluded:'범위 제외'};
const PAD=32,TOOLS=48,MIN_K=0.25,MAX_K=2.6,DETAIL_K=1.15;
type View={x:number;y:number;k:number};
const clamp=(v:number,a:number,b:number)=>Math.max(a,Math.min(b,v));
const pageText=(pages:number[])=>!pages.length?'':pages.length===1?`p.${pages[0]}`:`p.${pages[0]}–${pages[pages.length-1]}`;

function initialExpanded(tree:Tree){
  const open=new Set<string>();
  if(tree.leaves<=12)for(const n of tree.nodes.values())if(n.kind==='concept')open.add(n.id);
  if(tree.currentId)for(const id of ancestors(tree,tree.currentId))open.add(id);
  return open;
}

function Counts({node}:{node:TreeNode}){
  const total=STATUSES.reduce((s,k)=>s+node.counts[k],0);
  if(!total)return null;
  return <span className="main-quiz-tree-bar" aria-hidden="true">{STATUSES.map(k=>node.counts[k]?
    <i key={k} className={k} style={{flexGrow:node.counts[k]}}/>:null)}</span>;
}

export function RootMap({map,summary,position,title='강의 전체'}:{map:RootMapData;summary:RootSummary;position:string;title?:string}) {
  const tree=useMemo(()=>buildTree(map,summary,title),[map,summary,title]);
  const [expanded,setExpanded]=useState(()=>initialExpanded(tree));
  const [selected,setSelected]=useState<string|null>(tree.currentId);
  const [search,setSearch]=useState('');
  const [large,setLarge]=useState(false);
  const [view,setView]=useState<View>({x:PAD,y:PAD,k:1});
  const stage=useRef<HTMLDivElement>(null);
  const viewRef=useRef(view);viewRef.current=view;
  const anim=useRef<number>(0);
  const drag=useRef<{pointers:Map<number,{x:number;y:number}>;start?:View;origin?:{x:number;y:number};pinch?:{d:number;k:number};moved:number}>({pointers:new Map(),moved:0});
  const graph=useMemo(()=>layout(tree,expanded),[tree,expanded]);
  const byId=new Map(map.concepts.map(c=>[c.concept_id,c]));
  const targets=new Map(map.targets.map(t=>[t.target_id,t]));
  const node=selected?tree.nodes.get(selected)??null:null;

  function size(){const r=stage.current?.getBoundingClientRect();return {w:r?.width||800,h:r?.height||560};}
  function flyTo(next:View,ms=420){
    cancelAnimationFrame(anim.current);
    const from=viewRef.current,start=performance.now();
    const step=(now:number)=>{const p=Math.min(1,(now-start)/ms),e=p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;
      setView({x:from.x+(next.x-from.x)*e,y:from.y+(next.y-from.y)*e,k:from.k+(next.k-from.k)*e});
      if(p<1)anim.current=requestAnimationFrame(step);};
    if(matchMedia('(prefers-reduced-motion: reduce)').matches)setView(next);else anim.current=requestAnimationFrame(step);
  }
  /** Show the given nodes. With minK, text stays readable: a group too tall/wide for the
   *  frame is shown from its top-left (the topic and its first questions) instead of shrunk. */
  function frame(ids:string[],placed=graph.placed,{maxK=1.2,minK=MIN_K,animate=true,anchor}:{maxK?:number;minK?:number;animate?:boolean;anchor?:string}={}){
    const boxes=ids.map(id=>placed.get(id)).filter(Boolean) as {x:number;y:number;w:number;h:number}[];
    if(!boxes.length)return;
    const x0=Math.min(...boxes.map(b=>b.x)),y0=Math.min(...boxes.map(b=>b.y));
    const x1=Math.max(...boxes.map(b=>b.x+b.w)),y1=Math.max(...boxes.map(b=>b.y+b.h));
    // The tool row sits on the bottom edge; keep framed nodes above it.
    const {w,h}=size(),usable=h-TOOLS,k=clamp(Math.min((w-PAD*2)/(x1-x0||1),(usable-PAD*2)/(y1-y0||1),maxK),Math.max(MIN_K,minK),MAX_K);
    let x=(x1-x0)*k<=w-PAD*2?w/2-(x0+x1)/2*k:PAD-x0*k;
    let y=(y1-y0)*k<=usable-PAD*2?usable/2-(y0+y1)/2*k:PAD-y0*k;
    // Keep the anchor (e.g. the current question) inside the frame when the group overflows.
    const a=anchor?placed.get(anchor):undefined;
    if(a){if(a.y*k+y+a.h*k>usable-PAD)y=usable/2-(a.y+a.h/2)*k;if(a.x*k+x+a.w*k>w-PAD)x=w-PAD-(a.x+a.w)*k;}
    const next={k,x,y};
    if(animate)flyTo(next);else setView(next);
  }
  const fitAll=(placed=graph.placed)=>frame([...placed.keys()],placed,{maxK:1});
  // First frame: the current question's topic at a readable scale, else the whole tree.
  useEffect(()=>{
    const current=tree.currentId?tree.nodes.get(tree.currentId):null,parent=current?.parent?tree.nodes.get(current.parent):null;
    if(current&&parent&&parent.kind!=='root')frame([parent.id,...parent.children],graph.placed,{maxK:1,minK:0.8,animate:false,anchor:current.id});
    else frame([...graph.placed.keys()],graph.placed,{maxK:1,animate:false});
  },[]);
  useEffect(()=>()=>cancelAnimationFrame(anim.current),[]);

  function zoomAt(factor:number,cx?:number,cy?:number){
    const v=viewRef.current,{w,h}=size(),px=cx??w/2,py=cy??h/2;
    const k=clamp(v.k*factor,MIN_K,MAX_K),wx=(px-v.x)/v.k,wy=(py-v.y)/v.k;
    cancelAnimationFrame(anim.current);setView({k,x:px-wx*k,y:py-wy*k});
  }
  useEffect(()=>{
    const el=stage.current;if(!el)return;
    const wheel=(e:WheelEvent)=>{e.preventDefault();const r=el.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY*(e.ctrlKey?0.01:0.0018)),e.clientX-r.left,e.clientY-r.top);};
    el.addEventListener('wheel',wheel,{passive:false});return()=>el.removeEventListener('wheel',wheel);
  },[]);
  function pointerDown(e:ReactPointerEvent){
    if(e.button!==0)return;
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

  function choose(id:string,{toggle=false,focus=true}={}){
    const n=tree.nodes.get(id);if(!n)return;
    const next=new Set(expanded);for(const a of ancestors(tree,id))next.add(a);
    if(n.kind==='concept'&&toggle){if(next.has(id)&&selected===id)next.delete(id);else next.add(id);}
    setExpanded(next);setSelected(id);
    if(!focus)return;
    const placed=layout(tree,next).placed;
    const group=n.kind==='concept'&&next.has(id)?[id,...n.children]:n.kind==='target'?[id,n.parent!]:[id];
    frame(group,placed,{maxK:n.kind==='target'?1.2:1.05,minK:0.8,anchor:id});
  }
  function setAll(open:boolean){
    const next=new Set(open?[...tree.nodes.values()].filter(n=>n.kind==='concept').map(n=>n.id):[]);
    if(!open&&tree.currentId)for(const a of ancestors(tree,tree.currentId))next.add(a);
    setExpanded(next);const placed=layout(tree,next).placed;fitAll(placed);
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
  const detail=view.k>=DETAIL_K;
  const target=node?.targetId?targets.get(node.targetId):undefined;
  const crossLinks=node?.kind==='concept'?map.relations.filter(r=>node.conceptIds.includes(r.from_id)||node.conceptIds.includes(r.to_id))
    .filter(r=>{const a=byId.get(r.from_id),b=byId.get(r.to_id);return a&&b&&!(a.label===b.label);}).slice(0,20):[];
  const nodeOf=new Map<string,string>();
  for(const n of tree.nodes.values())if(n.kind==='concept')for(const id of n.conceptIds)nodeOf.set(id,n.id);
  const linked=crossLinks.map(r=>({...r,a:nodeOf.get(r.from_id),b:nodeOf.get(r.to_id)}))
    .filter((r):r is typeof r&{a:string;b:string}=>!!r.a&&!!r.b&&r.a!==r.b&&graph.placed.has(r.a)&&graph.placed.has(r.b));

  return <section className={`main-quiz-map${large?' is-large':''}`}>
    <header className="bank-cmap-heading"><h2>개념 지도</h2><span>{position}</span></header>
    <p className="bank-note">주제를 누르면 문항이 펼쳐지고, 확대하면 쪽·상태가 더 보여요. 끌어서 옮기고 휠·두 손가락으로 확대합니다.</p>
    <div className="main-quiz-map-search">
      <label>찾기 <input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="주제·문항"/></label>
      <span className="bank-note">주제 {[...tree.nodes.values()].filter(n=>n.kind==='concept').length}개 · 문항 {tree.leaves}개</span>
      {hits.length>0&&<ul>{hits.map(n=><li key={n.id}><button onClick={()=>{choose(n.id);setSearch('');}}>
        <span className="bank-note">{n.kind==='concept'?'주제':'문항'}</span> {n.label}</button></li>)}</ul>}
      {query&&!hits.length&&<span className="bank-note">찾는 항목이 없어요</span>}
    </div>
    <p className="main-quiz-map-legend">{STATUSES.map(s=><span key={s} className={s}>{STATUS_LABEL[s]}</span>)}<span className="is-current">현재 문제</span></p>
    <div className="main-quiz-tree-frame">
      <div ref={stage} className="main-quiz-tree-stage" onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp}
        onClickCapture={e=>{if(drag.current.moved>4){e.stopPropagation();e.preventDefault();drag.current.moved=0;}}}
        onDoubleClick={e=>{if(!(e.target as Element).closest('.main-quiz-tree-node'))fitAll();}}>
        <svg className="main-quiz-tree" role="group" aria-label="개념 트리">
          <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            {graph.edges.map(({from,to})=>{const a=graph.placed.get(from)!,b=graph.placed.get(to)!;
              const x1=a.x+a.w,y1=a.y+a.h/2,x2=b.x,y2=b.y+b.h/2,dx=(x2-x1)/2;
              const lit=selected!=null&&(to===selected||from===selected||tree.nodes.get(to)!.current);
              return <path key={to} className={`main-quiz-tree-edge${lit?' is-lit':''}`} d={`M${x1} ${y1} C${x1+dx} ${y1} ${x2-dx} ${y2} ${x2} ${y2}`}/>;})}
            {linked.map(r=>{const a=graph.placed.get(r.a)!,b=graph.placed.get(r.b)!;
              const x1=a.x+a.w/2,y1=a.y+a.h/2,x2=b.x+b.w/2,y2=b.y+b.h/2;
              return <path key={r.relation_id} className="main-quiz-tree-cross" d={`M${x1} ${y1} Q${(x1+x2)/2+60} ${(y1+y2)/2} ${x2} ${y2}`}><title>{r.reason}</title></path>;})}
            {[...graph.placed.values()].map(p=>{const n=tree.nodes.get(p.id)!;
              const open=n.kind==='concept'&&expanded.has(n.id),hidden=n.kind==='concept'&&!open?n.children.length:0;
              const state=n.kind==='target'?STATUS_LABEL[n.status!]:n.kind==='concept'?`문항 ${STATUSES.reduce((s,k)=>s+n.counts[k],0)}개`:'';
              return <g key={n.id} transform={`translate(${p.x} ${p.y})`} role="button" tabIndex={0}
                aria-label={`${n.kind==='concept'?'주제':n.kind==='target'?'문항':'강의'} ${n.label}${state?' · '+state:''}${n.current&&n.kind==='target'?' · 현재 문제':''}`}
                aria-pressed={selected===n.id} aria-expanded={n.kind==='concept'?open:undefined}
                className={`main-quiz-tree-node is-${n.kind} ${n.status??''}${selected===n.id?' is-selected':''}${n.current?' is-current':''}`}
                onClick={()=>choose(n.id,{toggle:true})}
                onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(n.id,{toggle:true});}}}>
                <rect width={p.w} height={p.h} rx={n.kind==='target'?10:14}/>
                <foreignObject x="0" y="0" width={p.w} height={p.h}>
                  <div className="main-quiz-tree-label">
                    <b className={n.kind==='target'&&!detail?'is-one-line':''}>{n.label}</b>
                    {n.kind==='concept'&&<small>{pageText(n.pages)}{n.pages.length?' · ':''}{state}{hidden?` · 펼치기 +${hidden}`:''}</small>}
                    {n.kind==='target'&&<small>{n.current?<em>현재 문제</em>:null}{detail?`${state}${n.pages.length?' · '+pageText(n.pages):''}`:n.current?'':state}</small>}
                    {n.kind==='root'&&<small>주제 {n.children.length}개 · 문항 {tree.leaves}개</small>}
                  </div>
                </foreignObject>
                {n.kind!=='target'&&<foreignObject x="10" y={p.h-9} width={p.w-20} height="6"><Counts node={n}/></foreignObject>}
              </g>;})}
          </g>
        </svg>
        <div className="main-quiz-tree-tools" onPointerDown={e=>e.stopPropagation()}>
          <button onClick={()=>zoomAt(1.25)} aria-label="확대">＋</button>
          <button onClick={()=>zoomAt(0.8)} aria-label="축소">－</button>
          <button onClick={()=>fitAll()}>전체</button>
          {tree.currentId&&<button onClick={()=>choose(tree.currentId!)}>현재 문제</button>}
          <button onClick={()=>setAll(true)}>모두 펼치기</button>
          <button onClick={()=>setAll(false)}>접기</button>
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
          {linked.length>0&&<><h4>다른 주제와의 연결</h4><ul>{linked.map(r=><li key={r.relation_id}>{byId.get(r.from_id)!.label} → {byId.get(r.to_id)!.label}<p className="bank-note">{r.reason}</p></li>)}</ul></>}
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
      <ol className="main-quiz-tree-outline">{tree.nodes.get(tree.rootId)!.children.map(function item(id:string):ReactNode{const n=tree.nodes.get(id)!;
        return <li key={id}><button className={`main-quiz-tree-link ${n.status??''}`} onClick={()=>choose(id)}>{n.label}</button>
          <span className="bank-note"> {n.kind==='target'?STATUS_LABEL[n.status!]:`문항 ${STATUSES.reduce((s,k)=>s+n.counts[k],0)}개`}{n.pages.length?' · '+pageText(n.pages):''}</span>
          {n.children.length>0&&<ol>{n.children.map(item)}</ol>}</li>;})}</ol>
    </details>
    <details className="main-quiz-details"><summary>자료 범위·출제포인트</summary><p>{map.scope.label}</p>{map.scope.limitations.map((text,i)=><p className="bank-note" key={i}>{text}</p>)}
      {map.points?.map(p=><p key={p.point_id}>{p.text} · {POINT_STATUS[map.coverage?.find(c=>c.point_id===p.point_id)?.status??'unknown']}</p>)}
    </details>
  </section>;
}
