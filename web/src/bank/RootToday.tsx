import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ROOT_TIERS } from '../types/rootLearning';
import type { RootFocus, RootOverview, RootSummary, RootPolicy, RootTierName } from '../types/rootLearning';
import { Icon } from '../shell/icons';
import { readQuizMode, readQuizOrder, saveQuizMode, saveQuizOrder, type QuizMode, type QuizOrder } from './quizMode';

export function RootPolicyNotice({policy}:{policy?:RootPolicy}) {
  if(!policy)return null;
  return <p className="bank-note">한국시간 {String(policy.day_hour).padStart(2,'0')}:00에 새 학습일이 시작됩니다.
    {'mode' in policy&&policy.mode==='adaptive'?' 복습 간격은 회상 결과·실제 경과 시간·시험일까지 남은 기간에 따라 조정됩니다.':' 이 회차는 시작할 때 고정한 이전 복습 정책을 따릅니다.'}</p>;
}

/** 풀이 중 「학습 기록·남은 범위」와 시작 화면 자세히 보기가 함께 쓴다. 시작 화면은 위 숫자 칸이 첫 줄을 대신한다(`brief`). */
export function RootSummaryPanel({summary:s,brief=false}:{summary:RootSummary;brief?:boolean}) {
  const rows:[string,number][]=[['미학습',s.unseen],['중요한 미학습',s.importantUnseen],['준비 전',s.unready],['오늘 새로 접함',s.newToday]];
  return <section className="mq-summary" aria-label="Main Quiz 학습 현황">
    {/* 시작 화면 위 숫자 칸은 카드 기준(2026-11-24)이라, 접은 자세히 보기에서는 목표 기준임을 밝힌다. */}
    <p className="mq-summary-line">{brief?'학습 목표 기준 · ':''}고유 목표 {s.total}개 · 첫 학습 {s.learned} · 회상 가능 {s.recalled}</p>
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
/**
 * 오늘 학습 중요도 범위(2026-11-25-lecture-tier-range, 처음은 2026-11-12 칩). 선분 4개(중요도마다 하나, 이름은 선분 위)와
 * 경계 점 5개. 손잡이 둘이 점 위에 있고 그 사이 선분들이 고른 중요도다. 손잡이는 겹치지 않아 늘 한 선분 이상이다.
 * 끄는 동안은 화면만, 놓을 때(pointerup·키·blur) 달라졌으면 한 번 저장한다.
 * 선분 이름을 누르면 가까운 손잡이가 와서 그 선분을 넣는다.
 * 옛 비연속 선택은 가장 낮은 것~가장 높은 것으로 보이고, 처음 움직일 때 연속 구간으로 저장된다.
 */
function FocusRange({focus,disabled,onChange}:{focus:RootFocus;disabled:boolean;onChange:(tiers:RootTierName[],prereqs?:boolean)=>void}) {
  const end=ROOT_TIERS.length;
  const picked=focus.tiers.map(t=>ROOT_TIERS.indexOf(t)).filter(i=>i>=0);
  const from=picked.length?Math.min(...picked):0,to=picked.length?Math.max(...picked)+1:end;
  const [draft,setDraft]=useState<[number,number]>([from,to]);
  const draftRef=useRef(draft);
  const set=(next:[number,number])=>{draftRef.current=next;setDraft(next);};
  // 서버 값(저장 응답·다른 강의로 이동)이 바뀌면 손잡이도 따라간다.
  useEffect(()=>{set([from,to]);},[from,to]);
  const commit=(next=draftRef.current)=>{
    const tiers=ROOT_TIERS.slice(next[0],next[1]);
    if(tiers.join()!==focus.tiers.join())onChange(tiers);
  };
  const [lo,hi]=draft;
  const pick=(i:number)=>{
    const next:[number,number]=i<lo?[i,hi]:i>=hi?[lo,i+1]:i-lo<=hi-1-i?[i,hi]:[lo,i+1];
    set(next);commit(next);
  };
  // 선행 문항(2026-11-18-prereq-toggle): 고른 중요도 밖의 선행 문항을 끌어올지. 모두 고르면 밖이 없다.
  const prereqs=focus.prereqs!==false,narrowed=focus.tiers.length<ROOT_TIERS.length;
  const thumb=(which:0|1)=><input type="range" min={0} max={end} step={1} value={draft[which]} disabled={disabled}
    aria-label={which?'중요도 끝':'중요도 시작'}
    aria-valuetext={which?`${ROOT_TIERS[draft[1]-1]}까지`:`${ROOT_TIERS[draft[0]]}부터`}
    onChange={e=>{const v=Number(e.currentTarget.value);set(which?[lo,Math.max(lo+1,v)]:[Math.min(hi-1,v),hi]);}}
    onPointerUp={()=>commit()} onKeyUp={()=>commit()} onBlur={()=>commit()}/>;
  return <div className="mq-focus" role="group" aria-label="중요도">
    <div className="mq-range" style={{'--lo':lo/end,'--hi':hi/end} as CSSProperties}>
      <div className="mq-range-stops">
        {ROOT_TIERS.map((tier,i)=><button key={tier} type="button" disabled={disabled}
          className={[i>=lo&&i<hi?'is-in':'',focus.counts[tier]?'':'is-empty'].filter(Boolean).join(' ')||undefined}
          onClick={()=>pick(i)}>{tier}<b>{focus.counts[tier]}</b></button>)}
      </div>
      <div className="mq-range-track" aria-hidden="true"><i/>
        {Array.from({length:end+1},(_,i)=><span key={i} className={i>=lo&&i<=hi?'is-in':undefined} style={{left:`${i/end*100}%`}}/>)}
      </div>
      {thumb(0)}{thumb(1)}
    </div>
    <button type="button" className="mq-focus-prereqs" aria-pressed={prereqs} disabled={disabled||!narrowed}
      onClick={()=>onChange(focus.tiers,!prereqs)}>{prereqs&&<Icon.check/>}선행 문항</button>
  </div>;
}

export function RootToday({info,onStart,disabled,mapDisabled=disabled,starting=false,onMap,onFocus,focusing=false,lectureLink,questionsLink,admin,resumeCount,onBack}:{info:RootOverview;onStart:(order?:QuizOrder)=>void;disabled:boolean;
  /** 개념 지도는 회차가 없으면 쓰기 큐를 쓰지 않아, 보관된 충돌이 있어도 열린다(2026-11-12). */
  mapDisabled?:boolean;starting?:boolean;onMap?:()=>void;onFocus?:(tiers:RootTierName[],prereqs?:boolean)=>void;
  /** 진행 중 회차의 남은 문항 수. 읽는 동안은 undefined. */
  resumeCount?:number;onBack?:()=>void;
  /** 중요도 저장·재계획 응답 대기 중: 카드 수를 흐리게 둔다. */
  focusing?:boolean;lectureLink?:string;
  /** 강의 문항 전체 보기(2026-11-23-lecture-question-list). */
  questionsLink?:string;admin?:ReactNode}) {
  const p=info.plan,s=info.summary;
  const count=info.sessionId?resumeCount:p?.tasks.length;
  // 숫자 칸·오늘 추천은 카드(문항) 수로(2026-11-24 사용자 「기준을 학습 목표 개수로 표기하지 말고 카드 수로」).
  // 강의 목록 열과 같은 서버 값(questionProgress): 본 카드 = 전체 − 미열람, 회상 가능 = 인출 + 저장.
  const q=info.questionProgress;
  const seen=q?q.total-q.unseen:0,recall=q?q.retrieving+q.retained:0;
  const learned=q&&q.total?seen/q.total*100:0,recalled=q&&q.total?recall/q.total*100:0;
  // 주관식/객관식 모드(2026-11-14). 풀이 화면이 같은 저장값을 읽는다.
  const [mode,setMode]=useState<QuizMode>(readQuizMode);
  const choose=(next:QuizMode)=>{saveQuizMode(next);setMode(next);};
  // 사진 반입 판의 순서(2026-11-15). 이어 풀 때는 그 회차의 지금 순서를 먼저 보인다. 바꾸고 시작하면 남은 문항만 다시 놓는다.
  const [order,setOrder]=useState<QuizOrder>(()=>info.order??readQuizOrder());
  const chooseOrder=(next:QuizOrder)=>{saveQuizOrder(next);setOrder(next);};
  return <section className="mq-start">
    <header className="page-head mq-head">
      <div>
        <p className="mq-kicker">{onBack&&<button type="button" className="quiz-back" onClick={onBack}><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3 5 8l5 5"/></svg>뒤로</button>}<span className="mq-badge">Main-Quiz</span>{lectureLink&&<Link to={lectureLink}>강의 자료 보기</Link>}</p>
        <h1>{info.title}</h1>
      </div>
      <div className="mq-head-actions">
        {onMap&&<button type="button" className="pill-button mq-map-button" disabled={mapDisabled} onClick={onMap}>개념 지도</button>}
        {questionsLink&&<Link className="pill-button mq-list-button" to={questionsLink}>전체 문항</Link>}
      </div>
    </header>

    {q&&<>
      <div className="mq-stats">
        <Stat label="전체 카드" value={q.total}/>
        <Stat label="본 카드" value={seen} total={q.total} tone="is-learned"/>
        <Stat label="회상 가능" value={recall} total={q.total} tone="is-recalled"/>
      </div>
      <div className="mq-progress" role="img" aria-label={`본 카드 ${seen}/${q.total} · 회상 가능 ${recall}/${q.total}`}>
        <i className="is-recalled" style={{width:`${recalled}%`}}/><i className="is-learned" style={{width:`${Math.max(0,learned-recalled)}%`}}/>
      </div>
    </>}

    <section className="mq-today" aria-label="오늘 추천">
      {p?<>
        <div className="mq-today-text">
          <h2>오늘 추천</h2>
          <p>{!p.tasks.length?'지금 추천할 과제가 없습니다.'
            :q?.newToday!==undefined?<>새 카드 <b>{q.newToday.toLocaleString('ko-KR')}</b>장 · 복습 <b>{q.reviewDue.toLocaleString('ko-KR')}</b>장</>
            :<>오늘 카드 <b>{p.tasks.length.toLocaleString('ko-KR')}</b>장</>}</p>
          <small>{p.deadline?`첫 학습 목표일 ${p.deadline}${p.days!==null&&p.days<=0?' · 목표일 지남':''}`:'시험일 미정 · 준비된 새 범위와 필요한 복습을 추천합니다.'}</small>
          {info.focus&&onFocus&&<FocusRange focus={info.focus} disabled={disabled||starting||focusing} onChange={onFocus}/>}
          <div className="mq-mode" role="radiogroup" aria-label="풀이 모드">
            {([['recall','주관식'],['mcq','객관식']] as [QuizMode,string][]).map(([value,label])=>
              <button key={value} type="button" role="radio" aria-checked={mode===value} className={mode===value?'is-on':''}
                disabled={starting} onClick={()=>choose(value)}>{label}</button>)}
          </div>
          {info.orderChoice&&<div className="mq-mode" role="radiogroup" aria-label="문항 순서">
            {([['ordered','순서대로'],['random','랜덤']] as [QuizOrder,string][]).map(([value,label])=>
              <button key={value} type="button" role="radio" aria-checked={order===value} className={order===value?'is-on':''}
                disabled={starting} onClick={()=>chooseOrder(value)}>{label}</button>)}
          </div>}
        </div>
        <button className="mq-start-button" disabled={disabled||!p.tasks.length&&!info.sessionId} onClick={()=>onStart(info.orderChoice?order:undefined)} aria-busy={starting}>
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
