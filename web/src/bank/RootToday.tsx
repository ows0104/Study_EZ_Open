import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { RootOverview, RootSummary, RootPolicy } from '../types/rootLearning';
import { Icon } from '../shell/icons';

export function RootPolicyNotice({policy}:{policy?:RootPolicy}) {
  if(!policy)return null;
  return <p className="bank-note">한국시간 {String(policy.day_hour).padStart(2,'0')}:00에 새 학습일이 시작됩니다.
    {'mode' in policy&&policy.mode==='adaptive'?' 복습 간격은 회상 결과·실제 경과 시간·시험일까지 남은 기간에 따라 조정됩니다.':' 이 회차는 시작할 때 고정한 이전 복습 정책을 따릅니다.'}</p>;
}

/** 풀이 중 「학습 기록·남은 범위」와 시작 화면 자세히 보기가 함께 쓴다. 시작 화면은 위 숫자 칸이 첫 줄을 대신한다(`brief`). */
export function RootSummaryPanel({summary:s,brief=false}:{summary:RootSummary;brief?:boolean}) {
  const rows:[string,number][]=[['미학습',s.unseen],['중요한 미학습',s.importantUnseen],['준비 전',s.unready],['오늘 새로 접함',s.newToday]];
  return <section className="mq-summary" aria-label="Main Quiz 학습 현황">
    {!brief&&<p className="mq-summary-line">고유 목표 {s.total}개 · 첫 학습 {s.learned} · 회상 가능 {s.recalled}</p>}
    <dl>{rows.map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {s.recallLearningChange!==0&&<p className="bank-note">오늘 평가에 따른 회상 변화 {s.recallLearningChange>0?'+':''}{s.recallLearningChange}</p>}
    {s.recallTimeChange!==0&&<p className="bank-note">복습 기한 경과에 따른 변화 {s.recallTimeChange}</p>}
    <p className="bank-note">첫 학습은 시도 후 답을 확인한 목표, 회상 가능은 필요한 방향을 모두 스스로 떠올린 목표입니다.</p>
  </section>;
}

function Stat({label,value,total,tone}:{label:string;value:number;total?:number;tone?:string}) {
  return <div className={tone}><span>{label}</span><b>{value.toLocaleString('ko-KR')}{total!==undefined&&<small>/{total.toLocaleString('ko-KR')}</small>}</b></div>;
}

/**
 * Main-Quiz 첫 화면(2026-11-08). 홈의 「강의 목록」과 같은 머리·숫자 칸·카드 모양.
 * 해야 할 일(오늘 학습)을 한 장의 카드에 두고, 설명·정책·판 정보는 접어 둔다.
 */
export function RootToday({info,onStart,disabled,onMap,lectureLink,admin}:{info:RootOverview;onStart:()=>void;disabled:boolean;onMap?:()=>void;
  lectureLink?:string;admin?:ReactNode}) {
  const p=info.plan,s=info.summary;
  const learned=s&&s.total?s.learned/s.total*100:0,recalled=s&&s.total?s.recalled/s.total*100:0;
  return <section className="mq-start">
    <header className="page-head mq-head">
      <div>
        <p className="mq-kicker"><span className="mq-badge">Main-Quiz</span>{lectureLink&&<Link to={lectureLink}>강의 자료 보기</Link>}</p>
        <h1>{info.title}</h1>
      </div>
      {onMap&&<button type="button" className="pill-button mq-map-button" disabled={disabled} onClick={onMap}>개념 지도</button>}
    </header>

    {s&&<>
      <div className="mq-stats">
        <Stat label="학습 목표" value={s.total}/>
        <Stat label="첫 학습" value={s.learned} total={s.total} tone="is-learned"/>
        <Stat label="회상 가능" value={s.recalled} total={s.total} tone="is-recalled"/>
      </div>
      <div className="mq-progress" role="img" aria-label={`첫 학습 ${s.learned}/${s.total} · 회상 가능 ${s.recalled}/${s.total}`}>
        <i className="is-recalled" style={{width:`${recalled}%`}}/><i className="is-learned" style={{width:`${Math.max(0,learned-recalled)}%`}}/>
      </div>
    </>}

    <section className="mq-today" aria-label="오늘 추천">
      {p?<>
        <div className="mq-today-text">
          <h2>오늘 추천</h2>
          <p>{p.tasks.length?<>과제 <b>{p.tasks.length}</b>개 · 새 목표 최소 <b>{p.newGoalQuota}</b>개</>:'지금 추천할 과제가 없습니다.'}</p>
          <small>{p.deadline?`첫 학습 목표일 ${p.deadline}${p.days!==null&&p.days<=0?' · 목표일 지남':''}`:'시험일 미정 · 준비된 새 범위와 필요한 복습을 추천합니다.'}</small>
        </div>
        <button className="mq-start-button" disabled={disabled||!p.tasks.length&&!info.sessionId} onClick={onStart}>
          <Icon.play/>{info.sessionId?'오늘 학습 재개':'오늘 학습 시작'}</button>
      </>:<p className="mq-today-text">{info.message}</p>}
    </section>

    <details className="mq-more"><summary>학습 현황·자료 범위</summary>
      {s&&<RootSummaryPanel summary={s} brief/>}
      <RootPolicyNotice policy={info.policy}/>
      {p&&<p className="bank-note">{p.scopeNote}</p>}
    </details>
    {admin}
  </section>;
}
