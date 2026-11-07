import type { RootOverview, RootSummary, RootPolicy } from '../types/rootLearning';
export function RootPolicyNotice({policy}:{policy?:RootPolicy}) {
  if(!policy)return null;
  return <p className="bank-note">한국시간 {String(policy.day_hour).padStart(2,'0')}:00에 새 학습일이 시작됩니다.
    {'mode' in policy&&policy.mode==='adaptive'?' 복습 간격은 회상 결과·실제 경과 시간·시험일까지 남은 기간에 따라 조정됩니다.':' 이 회차는 시작할 때 고정한 이전 복습 정책을 따릅니다.'}</p>;
}
export function RootSummaryPanel({summary:s}:{summary:RootSummary}) {
  return <section className="root-summary" aria-label="Main Quiz 학습 현황"><h3>학습 목표</h3>
    <p>고유 목표 {s.total}개 · 첫 학습 {s.learned} · 회상 가능 {s.recalled} · 미학습 {s.unseen}</p>
    <progress aria-label="목표 첫 학습" max={Math.max(1,s.total)} value={s.learned}/>
    <p>준비 전 {s.unready} · 중요한 미학습 {s.importantUnseen}</p>
    <p>오늘 새로 접한 목표 {s.newToday} · 오늘 평가에 따른 회상 변화 {s.recallLearningChange>0?'+':''}{s.recallLearningChange}</p>
    {s.recallTimeChange!==0&&<p>복습 기한 경과에 따른 변화 {s.recallTimeChange} · 새로운 실패 평가와 구별합니다.</p>}
    <p className="bank-note">첫 학습은 시도 후 답 확인이 저장된 사실입니다. 회상은 필수 방향별 자기평가이며 강의 전체 숙련도는 아닙니다.</p>
  </section>;
}
export function RootToday({info,onStart,disabled,onMap}:{info:RootOverview;onStart:()=>void;disabled:boolean;onMap?:()=>void}) {
  const p=info.plan;
  return <section className="quiz bank-start"><h2>{info.title}</h2>
    {info.summary&&<p className="main-quiz-today-counts">학습 목표 {info.summary.total}개 · 처음 본 목표 {info.summary.learned}개 · 회상 가능 {info.summary.recalled}개</p>}
    {p?<><h3>오늘 추천</h3><p>새 목표 최소 {p.newGoalQuota}개 · 준비된 과제 {p.tasks.length}개</p>
      <p>{p.deadline?`첫 학습 목표일 ${p.deadline}${p.days!==null&&p.days<=0?' · 목표일 경과':''}`:'시험일 미정 · 준비된 새 범위와 필요한 복습을 추천합니다.'}</p>
      <button className="quiz-submit" disabled={disabled||!p.tasks.length&&!info.sessionId} onClick={onStart}>{info.sessionId?'오늘 학습 재개':'오늘 학습 시작'}</button>
      {onMap&&<button className="main-quiz-map-start" disabled={disabled} onClick={onMap}>개념 지도</button>}
      {!p.tasks.length&&<p>현재 추천할 과제가 없습니다. 준비 전 목표와 남은 범위를 확인하세요.</p>}</>:<p>{info.message}</p>}
    <details className="main-quiz-details"><summary>학습 현황·자료 범위</summary>
      {info.summary&&<RootSummaryPanel summary={info.summary}/>}
      <RootPolicyNotice policy={info.policy}/><p className="bank-note">자료 판 {info.revision} · 판이 다른 학습은 검토된 동일성 연결이 있을 때만 이어집니다.</p>
      {p&&<p className="bank-note">{p.scopeNote}</p>}
    </details>
  </section>;
}
