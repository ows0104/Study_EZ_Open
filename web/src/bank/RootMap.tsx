import { useId, useMemo, useState } from 'react';
import type { RootMapData, RootSummary } from '../types/rootLearning';

const RELATIONS:Record<string,string>={classification:'분류',causal:'원인·결과',comparison:'비교',sequence:'순서',prerequisite:'선행',association:'연결'};
function conceptState(id:string,map:RootMapData,summary:RootSummary){
  const targets=map.targets.filter(t=>t.concept_ids.includes(id));
  const states=targets.map(t=>summary.targets.find(s=>s.id===t.target_id));
  if(!states.length)return {label:'연결된 과제 없음',className:'is-unready'};
  if(states.every(s=>s?.recalled))return {label:'회상 가능',className:'is-recalled'};
  if(states.some(s=>s?.learned))return {label:'학습 중',className:'is-learning'};
  if(states.every(s=>!s?.ready))return {label:'준비 전',className:'is-unready'};
  return {label:'미학습',className:'is-new'};
}
function lines(text:string){
  const chars=Array.from(text);return chars.length>30?[chars.slice(0,15).join(''),chars.slice(15,28).join('')+'…']:
    chars.length>15?[chars.slice(0,15).join(''),chars.slice(15).join('')]:[text];
}

export function RootMap({map,summary,position}:{map:RootMapData;summary:RootSummary;position:string}) {
  const [selected,setSelected]=useState<string|null>(map.concepts.length>24?(map.currentConceptIds?.[0]??null):null);
  const [search,setSearch]=useState('');
  const arrow=useId().replace(/:/g,'');
  const byId=new Map(map.concepts.map(c=>[c.concept_id,c]));
  const allRelations=map.relations.filter(r=>byId.has(r.from_id)&&byId.has(r.to_id));
  const neighbors=new Set([selected,...allRelations.filter(r=>r.from_id===selected||r.to_id===selected).flatMap(r=>[r.from_id,r.to_id])]);
  const visible=useMemo(()=>map.concepts.length>24&&selected?map.concepts.filter(c=>neighbors.has(c.concept_id)):map.concepts,[map,selected]);
  const layout=useMemo(()=>{
    const known=new Map(visible.map(c=>[c.concept_id,c]));
    function depth(id:string,path=new Set<string>()):number{
      if(path.has(id)||path.size>=8)return 0;
      const parents=known.get(id)?.parent_ids.filter(p=>known.has(p))??[];
      return parents.length?1+Math.max(...parents.map(p=>depth(p,new Set([...path,id])))):0;
    }
    const layers=new Map<number,typeof map.concepts>();
    for(const c of visible){const d=depth(c.concept_id);layers.set(d,[...(layers.get(d)??[]),c]);}
    const coordinates=new Map<string,{x:number;y:number}>();let row=0;
    const columns=Math.min(4,Math.max(1,...[...layers.values()].map(g=>g.length)));
    const width=Math.max(420,columns*210+40);
    for(const [,group]of [...layers].sort(([a],[b])=>a-b)){
      group.forEach((c,i)=>{
        const count=Math.min(columns,group.length-Math.floor(i/columns)*columns);
        coordinates.set(c.concept_id,{x:width/2+(i%columns-(count-1)/2)*210,y:60+(row+Math.floor(i/columns))*130});
      });row+=Math.ceil(group.length/columns);
    }
    return {coordinates,width,height:Math.max(220,row*130)};
  },[visible]);
  const relations=allRelations.filter(r=>layout.coordinates.has(r.from_id)&&layout.coordinates.has(r.to_id));
  const targets=selected?map.targets.filter(t=>t.concept_ids.includes(selected)):map.targets;
  return <section className="main-quiz-map"><header className="bank-cmap-heading"><h2>개념 지도</h2><span>{position}</span></header>
    <p className="bank-note">개념을 누르면 관련 연결과 학습 내용을 볼 수 있어요. 문제 위치는 유지됩니다.</p>
    {map.concepts.length>24&&<div className="main-quiz-map-search"><label>개념 찾기 <input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="개념 이름"/></label>
      <span className="bank-note">{selected?`관련 ${visible.length}개 / 전체 ${map.concepts.length}개`:`전체 ${map.concepts.length}개`}</span>
      {selected&&<button onClick={()=>setSelected(null)}>전체 지도 보기</button>}
      {search.trim()&&<ul>{map.concepts.filter(c=>c.label.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())).slice(0,12).map(c=><li key={c.concept_id}>
        <button onClick={()=>{setSelected(c.concept_id);setSearch('');}}>{c.label}</button></li>)}</ul>}
    </div>}
    <p className="main-quiz-map-legend"><span className="is-new">미학습</span><span className="is-learning">학습 중</span><span className="is-recalled">회상 가능</span><span className="is-unready">준비 전</span></p>
    <div className="main-quiz-graph-scroll" tabIndex={0} aria-label="개념 지도 스크롤 영역">
      <svg className="main-quiz-graph" viewBox={`0 0 ${layout.width} ${layout.height}`} style={{minWidth:Math.min(layout.width,680)}} role="group" aria-label="개념 관계 그래프">
        <defs><marker id={arrow} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>
        {relations.map(r=>{
          const a=layout.coordinates.get(r.from_id)!,b=layout.coordinates.get(r.to_id)!;
          const angle=Math.atan2(b.y-a.y,b.x-a.x);
          const sx=a.x+Math.cos(angle)*50,sy=a.y+Math.sin(angle)*32;
          const ex=b.x-Math.cos(angle)*88,ey=b.y-Math.sin(angle)*38;
          const active=r.from_id===selected||r.to_id===selected;
          return <path key={r.relation_id} d={`M ${sx} ${sy} Q ${(sx+ex)/2+18} ${(sy+ey)/2-14} ${ex} ${ey}`}
            className={`main-quiz-edge${active?' is-focus':selected?' is-muted':''}`} markerEnd={`url(#${arrow})`}>
            <title>{byId.get(r.from_id)!.label} → {byId.get(r.to_id)!.label} · {RELATIONS[r.kind]??r.kind} · {r.reason}</title></path>;
        })}
        {visible.map(c=>{
          const point=layout.coordinates.get(c.concept_id)!,status=conceptState(c.concept_id,map,summary);
          return <g key={c.concept_id} transform={`translate(${point.x},${point.y})`} role="button" tabIndex={0}
            aria-label={`${c.label} · ${status.label}`} aria-pressed={selected===c.concept_id}
            className={`main-quiz-node ${status.className}${selected===c.concept_id?' is-selected':''}${selected&&!neighbors.has(c.concept_id)?' is-muted':''}`}
            onClick={()=>setSelected(c.concept_id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setSelected(c.concept_id);}}}>
            <title>{c.label} · {status.label}</title><rect x="-88" y="-36" width="176" height="78" rx="12"/>
            <text textAnchor="middle" className="main-quiz-node-label">{lines(c.label).map((line,i)=><tspan key={i} x="0" y={-10+i*18}>{line}</tspan>)}</text>
            <text textAnchor="middle" y="29" className="main-quiz-node-status">{status.label}</text>
          </g>;
        })}
      </svg>
    </div>
    {selected&&<section className="main-quiz-map-selection"><h3>{byId.get(selected)?.label}</h3><button onClick={()=>setSelected(null)}>전체 개념 보기</button>
      <ul>{allRelations.filter(r=>r.from_id===selected||r.to_id===selected).map(r=><li key={r.relation_id}>
        {byId.get(r.from_id)!.label} → {byId.get(r.to_id)!.label} <span className="bank-note">{RELATIONS[r.kind]??r.kind}</span><p>{r.reason}</p></li>)}</ul></section>}
    <details className="main-quiz-details" open={selected?true:undefined} key={selected??'all'}><summary>{selected?'관련 학습 내용':'개념별 학습 내용'} · {targets.length}개</summary>
      {targets.map(t=><article className="root-card" key={t.target_id}><h3>{t.title}</h3><p className="bank-note">{summary.targets.find(x=>x.id===t.target_id)?.status??'준비 전'}</p>
        <details><summary>회상 방향과 답 범위</summary>{t.directions.map(d=><p key={d.direction_id}>{d.cue} → {d.answer_scope}
          {map.readyDirectionIds&&!map.readyDirectionIds.includes(d.direction_id)&&' · 학습 연결 준비 전'}</p>)}</details>
        <details><summary>중요도 근거</summary><dl>{(['structural','exam','clinical'] as const).map((axis,i)=><div key={axis}><dt>{['이해의 뼈대','시험 근거','임상 근거'][i]}</dt><dd>{t.importance[axis].reason}</dd></div>)}</dl></details>
      </article>)}
    </details>
    <details className="main-quiz-details"><summary>자료 범위·출제포인트</summary><p>{map.scope.label}</p>{map.scope.limitations.map((text,i)=><p className="bank-note" key={i}>{text}</p>)}
      {map.points?.map(p=><p key={p.point_id}>{p.text} · {({covered:'충족',partial:'일부 충족',gap:'미출제',unknown:'검토 필요',excluded:'범위 제외'} as Record<string,string>)[map.coverage?.find(c=>c.point_id===p.point_id)?.status??'unknown']}</p>)}
    </details>
  </section>;
}
