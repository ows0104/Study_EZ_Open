import type { RootMapData, RootSummary } from '../types/rootLearning';
export function RootMap({map,summary,position}:{map:RootMapData;summary:RootSummary;position:string}) {
  return <section><h2>뿌리 지도와 근거</h2><p>{position} · 지도 탐색은 풀이 위치를 바꾸지 않습니다.</p>
    <p>{map.scope.label}</p>{map.scope.limitations.map((text,i)=><p className="bank-note" key={i}>{text}</p>)}
    <details><summary>탐색 구조</summary><ul>{map.concepts.map(c=><li key={c.concept_id}>{c.label}{c.parent_ids.length?` · 상위 ${c.parent_ids.map(id=>map.concepts.find(x=>x.concept_id===id)?.label??id).join(', ')}`:''}</li>)}</ul></details>
    {map.targets.map(t=><article className="root-card" key={t.target_id}><h3>{t.title}</h3><p>{summary.targets.find(x=>x.id===t.target_id)?.status??'준비 전'}</p>
      <p>구조적 역할: {t.role==='root'?'뼈대':t.role==='branch'?'가지':'세부'}</p>
      <dl>{(['structural','exam','clinical'] as const).map((axis,i)=><div key={axis}><dt>{['이해의 뼈대','시험 근거','임상 근거'][i]}</dt><dd>{t.importance[axis].reason} · {t.importance[axis].status==='supported'?'근거 있음':'미확인/근거 부족'}</dd></div>)}</dl>
      <details><summary>회상 방향과 답 범위</summary>{t.directions.map(d=><p key={d.direction_id}>{d.cue} → {d.answer_scope} · {d.requirement==='required'?'필수':d.requirement==='optional'?'확장':'필수 여부 검토 중'}
        {map.readyDirectionIds&&(map.readyDirectionIds.includes(d.direction_id)?' · 학습 연결 준비됨':' · 학습 연결 미준비')}</p>)}</details>
    </article>)}
    <p className="bank-note">같은 목표가 여러 탐색 위치에 연결되어도 목표 수에는 한 번만 포함됩니다.</p>
    {!!map.points?.length&&<section><h3>출제포인트와 실제 시험 범위</h3><p>원본 대조 결과입니다. 정답 검수와 선행 과제를 반영한 학습 준비 여부는 각 목표에 표시합니다.</p>
      <ul>{map.points.map(p=>{const c=map.coverage?.find(row=>row.point_id===p.point_id);return <li key={p.point_id}><strong>{p.text}</strong>
        {' · '}{({covered:'방향 충족',partial:'일부 시험',gap:'미시험',unknown:'검토 필요',excluded:'범위 제외'} as Record<string,string>)[c?.status??'unknown']}
        <p>{c?.reason??p.reason}</p>{c&&<p>확인 {c.confirmed_direction_ids.length} · 일부 {c.partial_direction_ids.length} · 누락 {c.missing_direction_ids.length} · 미확인 {c.unknown_direction_ids.length}</p>}</li>;})}</ul></section>}
  </section>;
}
