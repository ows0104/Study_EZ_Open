import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ROOT_TIERS } from '../types/rootLearning';
import type { RootFocus, RootOverview, RootSummary, RootPolicy, RootTierName } from '../types/rootLearning';
import { Icon } from '../shell/icons';
import { readQuizMode, saveQuizMode, type QuizMode } from './quizMode';

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
/** 오늘 학습 중요도 필터(2026-11-12). 이름과 준비된 과제 수만. 마지막 남은 칩은 끌 수 없다. */
function FocusChips({focus,disabled,onChange}:{focus:RootFocus;disabled:boolean;onChange:(tiers:RootTierName[])=>void}) {
  const on=new Set(focus.tiers);
  return <div className="mq-focus" role="group" aria-label="중요도">
    {ROOT_TIERS.map(tier=>{
      const pressed=on.has(tier),last=pressed&&on.size===1;
      return <button key={tier} type="button" aria-pressed={pressed} disabled={disabled||last}
        className={focus.counts[tier]?undefined:'is-empty'}
        onClick={()=>onChange(ROOT_TIERS.filter(t=>t===tier?!pressed:on.has(t)))}>
        {pressed&&<Icon.check/>}{tier}<b>{focus.counts[tier]}</b></button>;
    })}
  </div>;
}

export function RootToday({info,onStart,disabled,mapDisabled=disabled,starting=false,onMap,onFocus,focusing=false,lectureLink,admin,resumeCount,onBack}:{info:RootOverview;onStart:()=>void;disabled:boolean;
  /** 개념 지도는 회차가 없으면 쓰기 큐를 쓰지 않아, 보관된 충돌이 있어도 열린다(2026-11-12). */
  mapDisabled?:boolean;starting?:boolean;onMap?:()=>void;onFocus?:(tiers:RootTierName[])=>void;
  /** 진행 중 회차의 남은 문항 수. 읽는 동안은 undefined. */
  resumeCount?:number;onBack?:()=>void;
  /** 중요도 저장·재계획 응답 대기 중: 카드 수를 흐리게 둔다. */
  focusing?:boolean;lectureLink?:string;admin?:ReactNode}) {
  const p=info.plan,s=info.summary;
  const count=info.sessionId?resumeCount:p?.tasks.length;
  const learned=s&&s.total?s.learned/s.total*100:0,recalled=s&&s.total?s.recalled/s.total*100:0;
  // 주관식/객관식 모드(2026-11-14). 풀이 화면이 같은 저장값을 읽는다.
  const [mode,setMode]=useState<QuizMode>(readQuizMode);
  const choose=(next:QuizMode)=>{saveQuizMode(next);setMode(next);};
  return <section className="mq-start">
    <header className="page-head mq-head">
      <div>
        <p className="mq-kicker">{onBack&&<button type="button" className="quiz-back" onClick={onBack}><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3 5 8l5 5"/></svg>뒤로</button>}<span className="mq-badge">Main-Quiz</span>{lectureLink&&<Link to={lectureLink}>강의 자료 보기</Link>}</p>
        <h1>{info.title}</h1>
      </div>
      {onMap&&<button type="button" className="pill-button mq-map-button" disabled={mapDisabled} onClick={onMap}>개념 지도</button>}
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
          <p>{p.tasks.length?<>새 목표 최소 <b>{p.newGoalQuota}</b>개</>:'지금 추천할 과제가 없습니다.'}</p>
          <small>{p.deadline?`첫 학습 목표일 ${p.deadline}${p.days!==null&&p.days<=0?' · 목표일 지남':''}`:'시험일 미정 · 준비된 새 범위와 필요한 복습을 추천합니다.'}</small>
          {info.focus&&onFocus&&<FocusChips focus={info.focus} disabled={disabled||starting} onChange={onFocus}/>}
          <div className="mq-mode" role="radiogroup" aria-label="풀이 모드">
            {([['recall','주관식'],['mcq','객관식']] as [QuizMode,string][]).map(([value,label])=>
              <button key={value} type="button" role="radio" aria-checked={mode===value} className={mode===value?'is-on':''}
                disabled={starting} onClick={()=>choose(value)}>{label}</button>)}
          </div>
        </div>
        <button className="mq-start-button" disabled={disabled||!p.tasks.length&&!info.sessionId} onClick={onStart} aria-busy={starting}>
          <Icon.play/>{info.sessionId?'오늘 학습 재개':info.todayDone?'더 풀기':'오늘 학습 시작'}
          {count!==undefined&&<span className="mq-card-count" aria-label={`카드 ${count}개`} aria-live="polite"
            data-busy={focusing&&!info.sessionId||undefined}>{count.toLocaleString('ko-KR')}</span>}</button>
        {starting&&<span className="sr-only" role="status">첫 문항을 여는 중…</span>}
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
