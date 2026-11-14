import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { RootAction, RootView } from '../types/rootLearning';
import type { BankQuestion as BankQuestionData, BankRating, BankTier } from '../types/bank';
import { api } from '../api';
import { QuestionBody, AnswerBody, AnswerReviewItems, hasAnswerReview } from './BankQuestion';
import { PersonalQuestionDialog, type PersonalQuestionResult } from './PersonalQuestionDialog';
import { RootSummaryPanel } from './RootToday';
import { ANSWER_SECONDS, questionSeconds, readTimerOn, saveTimerOn, useQuizTimer } from './quizTimer';
import { mcqChoices, readQuizMode, saveQuizMode, type QuizMode } from './quizMode';

const PdfSlides = lazy(() => import('./RootPdfSlides').then(m => ({default:m.RootPdfSlides})));
const JokboSlides = lazy(() => import('./RootPdfSlides').then(m => ({default:m.RootJokboSlides})));

/** 강의록·족보 근거. Quiz Bank처럼 족보가 핵심이면 족보를 먼저, 아니면 강의록 뒤에 참고 족보를 둔다. */
function AnswerSlides({answer}:{answer:NonNullable<NonNullable<RootView['task']>['answer']>}){
  const notes=answer.pdfSlides??[], exams=answer.jokboPdfSlides??[];
  const examFirst=exams.some(s=>s.primary);
  const exam=exams.length?<JokboSlides slides={exams}/>:null;
  if(!notes.length&&!exams.length&&!answer.slides.length)return <p className="bank-note">이 문항에 연결된 참고 슬라이드가 없습니다.</p>;
  return <Suspense fallback={<p role="status">참고 슬라이드를 준비하고 있습니다…</p>}>
    {examFirst&&exam}
    {!!notes.length&&<PdfSlides slides={notes} focusKnown={!!answer.slideFocusKnown} statusKnown={!!answer.evidenceStatus}/>}
    {!examFirst&&exam}
  </Suspense>;
}
/** 예전 화면이 브라우저에 보관한 선지 선택(`…:picks`)을 지운다. 다른 보관값(초안·선지 보기 기록)은 건드리지 않는다. */
function clearSavedPicks() {
  try {
    for (const k of Object.keys(localStorage)) if (k.startsWith('studyez:root-draft:') && k.endsWith(':picks')) localStorage.removeItem(k);
  } catch { /* 저장소를 못 쓰면 지울 것도 읽지 않는다. */ }
}
const RATINGS: BankRating[] = ['Again', 'Hard', 'Good', 'Easy'];
const TIER_LABEL: Record<BankTier,string> = {Essential:'★ Must-Know', Core:'Core', Important:'Important', Optional:'Optional'};

export function RootSolve({view,title,scope,disabled,advancing,onAction,onToday,onError,onMap,editPath,onEdited,tierPath,onTier}:{view:RootView;title?:string;scope:string;disabled:boolean;
  editPath?:(questionId:string)=>string;onEdited?:(result:PersonalQuestionResult)=>void;
  /** 「내 중요도」 저장 경로(2026-11-09). 없으면 선택을 그리지 않는다. */
  tierPath?:(questionId:string)=>string;onTier?:(question:BankQuestionData)=>void;
  advancing:boolean;onAction:(a:RootAction)=>void;onToday:()=>void;onError:(message:string)=>void;onMap?:()=>void}) {
  const task=view.task;
  const key=`studyez:root-draft:${scope}:${JSON.stringify([view.revision,task?.id])}`;
  const [picked,setPicked]=useState<Set<string>>(new Set());
  // 「폈음」은 그 문항의 것일 때만 참이다 — 다음 문항이 그려지는 첫 순간에 앞 문항의 값으로 선지가 비치지 않게 한다.
  // seen: 한 번이라도 폈는지. 다시 접어도(2026-11-12, V·Z) 도움받은 풀이 기록은 그대로 남는다.
  const [choiceState,setChoiceState]=useState({key:'',shown:false,seen:false});
  const choices=choiceState.key===key&&choiceState.shown;
  const choicesSeen=choiceState.key===key&&choiceState.seen;
  const setChoices=(shown:boolean,seen=shown)=>setChoiceState({key,shown,seen});
  const [imageState,setImageState]=useState<{taskId:string;ready:boolean}|null>(null);
  const [editing,setEditing]=useState(false);
  const [editNote,setEditNote]=useState('');
  const [tierBusy,setTierBusy]=useState(false);
  const heading=useRef<HTMLHeadingElement>(null);
  const menu=useRef<HTMLDetailsElement>(null);
  const locked=disabled||advancing||!!view.blocked;
  const imagesReady=!task?.question.stimuli?.length||(imageState?.taskId===task.id&&imageState.ready);
  // 객관식 모드(2026-11-14): 선지가 있는 모든 문항을 처음부터 선지로 푼다. 정답 개수는 알리지 않고 여러 개를 고를 수 있다.
  const [mode,setMode]=useState<QuizMode>(readQuizMode);
  const mcq=mode==='mcq'&&task?mcqChoices(task.question,task.answer):null;
  const hiddenChoices=!mcq&&task?.question.mcq_mode==='recall_first'&&!choices&&!task.answer;
  // 단답·나열 「선지 보기」(2026-11-12): 문항의 options와 별개인 선지. 사용자가 펼 때만 보이고, 편 풀이는 도움받은 풀이로 남는다.
  const recall=!mcq&&task&&!task.question.options.length&&task.question.recall_choices?.length?task.question.recall_choices:null;
  const recallClosed=!!recall&&!choices&&!task?.answer;
  const recallOpen=!!recall&&choices&&!task?.answer;
  useEffect(()=>{
    // 고른 선지는 문항을 열 때마다 비운다(사용자 2026-11-14 「무조건 과거 기록은 삭제되도록」). 예전에 보관한 선택도 지운다.
    setPicked(new Set());clearSavedPicks();
    try {
      const saved=localStorage.getItem(key+':choices');
      setChoices(saved==='shown',saved==='shown'||saved==='seen');
    }catch{setChoices(false);onError('보관된 선지 보기 기록을 읽지 못했습니다. 원본을 보존했습니다.');}
    menu.current?.removeAttribute('open');setEditing(false);setEditNote('');
    heading.current?.focus();window.scrollTo(0,0);
  },[key]);
  function save(suffix:string,text:string) {
    try{localStorage.setItem(key+suffix,text);return true;}
    catch{onError('선지 선택을 보관하지 못했습니다. 브라우저 저장 공간을 확인하세요.');return false;}
  }
  function pick(id:string){
    if(locked||task?.answer)return;
    const single=!mcq&&(task?.question.format==='mcq'||(!!recall&&task?.question.format==='basic'));
    const next=new Set(single?[]:picked);
    if(picked.has(id)&&!single)next.delete(id);else next.add(id);
    setPicked(next);
    heading.current?.focus({preventScroll:true});
  }
  function showChoices(){if(save(':choices','shown'))setChoices(true);heading.current?.focus({preventScroll:true});}
  /** 편 단답·나열 선지를 다시 접는다(V 한 번 더·Z·Ctrl+Z). 안 보이는 선택이 답으로 가지 않게 고른 것도 비운다. */
  function hideChoices(){
    if(save(':choices','seen')){setChoices(false,true);setPicked(new Set());}
    heading.current?.focus({preventScroll:true});
  }
  function reveal(attempted=true){
    if(locked||!task||task.answer||attempted&&!imagesReady)return;
    // Retired text drafts remain untouched in storage; no new text is required.
    const response=picked.size?`선택: ${[...picked].join(', ')}`:'';
    onAction({kind:'reveal',attempted,response,helped:view.mapSeen,
      // 객관식 모드의 풀이는 주관식과 같은 풀이로 기록·평가한다(사용자 2026-11-14 「분리하지 말고」). 덧붙인 선지(객관식 모드·OX·선지 보기)는
      // 도움받은 풀이로 세지 않고, 문항 자체 선지는 주관식 모드와 같게 센다.
      choicesShown:mcq?!!task.question.options.length:recall?choicesSeen:!!task.question.options.length&&!hiddenChoices,
      ...(attempted&&task.question.stimuli?.length?{stimulusHashes:task.question.stimuli.map(s=>s.sha256)}:{})});
    heading.current?.focus({preventScroll:true});
  }
  /** 내 계정·이 판의 이 문항에만 적용. 바꾼 중요도는 그 문항 복습 간격에만 반영된다(서버 state.replay). */
  async function changeTier(tier:BankTier|null){
    if(!task||!tierPath||tierBusy)return;
    setTierBusy(true);setEditNote('');
    try{
      const got=await api<{question:BankQuestionData;rescheduled:boolean}>(tierPath(task.question.question_id),
        {method:'PUT',body:JSON.stringify({requestId:crypto.randomUUID(),tier})});
      onTier?.(got.question);
      setEditNote((got.question.personalTier?`내 중요도를 ${TIER_LABEL[got.question.tier]}로 저장했습니다.`:'원래 중요도로 되돌렸습니다.')
        +(got.rescheduled?' 이 문항의 복습 예정일을 다시 계산했습니다.':''));
    }catch(cause){onError((cause as Error).message);}
    finally{setTierBusy(false);}
  }
  /** 이 판에서 내 학습에서 뺀다(2026-11-12). Z로 되돌린다. */
  function exclude(){if(!disabled&&!advancing&&task&&!view.blocked?.includes('학습일'))onAction({kind:'exclude'});}
  function rate(selfRating:BankRating){if(!locked&&task?.answer)onAction({kind:'rate',selfRating});}
  // 문항 타이머(2026-11-11): 문제 0초 → 답 보기, 해설 40초 0초 → Again(사용자 선택).
  const [timerOn,setTimerOn]=useState(readTimerOn);
  const timer=useQuizTimer({
    phase:task&&!view.finished?`${task.id}:${task.answer?'answer':'question'}`:null,
    seconds:task?.answer?ANSWER_SECONDS:questionSeconds(mcq&&task?.question.format!=='ox'?'mcq':task?.question.format??'basic'),
    enabled:timerOn,running:!locked&&!editing&&(!!task?.answer||imagesReady),
    onExpire:()=>{if(task?.answer)rate('Again');else reveal();},
  });
  function toggleTimer(){const on=!timerOn;saveTimerOn(on);setTimerOn(on);heading.current?.focus({preventScroll:true});}
  function toggleMode(){const next:QuizMode=mode==='mcq'?'recall':'mcq';saveQuizMode(next);setMode(next);setPicked(new Set());heading.current?.focus({preventScroll:true});}
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      const target=event.target as HTMLElement;
      if(event.defaultPrevented||event.isComposing||!task)return;
      if(document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')||target.closest('input,textarea,select,[contenteditable="true"]'))return;
      // 스페이스는 이 화면에서 쪽을 내리지 않는다 — 답을 본 뒤·누르고 있을 때·저장 중에도(2026-11-12: 아래 바가 위아래로 움직였다).
      // 버튼·링크에 포커스가 있으면 브라우저가 그것을 누르게 둔다.
      if(event.code==='Space'&&!target.closest('button,a,summary'))event.preventDefault();
      if(event.repeat||event.altKey||locked)return;
      // 되돌리기: Z, Ctrl+Z, ⌘+Z(2026-11-12). 한글 입력 상태도 키 자리(KeyZ)로 알아보고, 버튼에 포커스가 있어도 된다.
      // 단답·나열 선지를 편 채면 먼저 그것을 접는다 — 가장 최근 동작이 「선지 보기」이므로.
      if((event.code==='KeyZ'||event.key.toLowerCase()==='z')&&!(event.ctrlKey&&event.metaKey)){
        if(recallOpen){event.preventDefault();hideChoices();}
        else if(view.canUndo){event.preventDefault();onAction({kind:'undo'});}
        return;
      }
      if(event.ctrlKey||event.metaKey)return;
      if(event.key==='Tab'&&!event.shiftKey&&timerOn){event.preventDefault();timer.togglePause();return;}
      const number=/^[1-4]$/.test(event.key);
      // 객관식 모드에서 답 보기 전에는 1–9로 그 번호 선지를 고른다(선지가 5개 이상일 수 있다).
      if(mcq&&!task.answer&&/^[1-9]$/.test(event.key)&&!target.closest('button')){
        const option=mcq.choices[Number(event.key)-1];
        if(option){event.preventDefault();pick(option.id);return;}
      }
      if(target.closest('a,summary')||target.closest('button')&&!number&&event.key!=='5')return;
      if((event.code==='Space'||event.key==='Enter')&&!task.answer){event.preventDefault();reveal();}
      if(event.code==='KeyV'&&recallClosed){event.preventDefault();showChoices();}
      else if(event.code==='KeyV'&&recallOpen){event.preventDefault();hideChoices();}
      if(task.answer&&number){event.preventDefault();rate(RATINGS[Number(event.key)-1]);}
      // 답 보기 전 1–4: 화면에 보이는 선지(객관식 선지, 또는 V로 편 단답·나열 선지)에서 그 번호를 고른다.
      if(!task.answer&&number){
        const shown=recall?(choices?recall:[]):hiddenChoices?[]:task.question.options;
        const option=shown[Number(event.key)-1];
        if(option){event.preventDefault();pick(option.id);}
      }
      if(event.key==='5'){event.preventDefault();exclude();}
    };
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  },[locked,task,picked,imagesReady,hiddenChoices,recallClosed,recallOpen,choices,choicesSeen,view.mapSeen,view.canUndo,timerOn,timer.togglePause,mcq]);
  const done=Math.min(view.position,view.count);
  const head=<header className="mq-solve-head">
    <p className="mq-kicker">
      {/* 기록은 평가마다 저장된다. 풀이를 멈추고 시작 화면(오늘 현황)으로 간다. */}
      <button type="button" className="quiz-back" disabled={disabled||advancing} onClick={onToday}><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3 5 8l5 5"/></svg>뒤로</button>
      <span className="mq-badge">Main-Quiz</span>{title&&<span className="mq-solve-title">{title}</span>}</p>
    {!view.finished&&<span className="main-quiz-tools">
      <span className="mq-timer">
        {timerOn&&task&&<span role="timer" aria-label={`${timer.paused?'일시정지 · ':''}남은 시간 ${timer.left}초`}
          className={`mq-timer-left${timer.paused?' is-paused':''}${timer.left<=5?' is-low':''}`}>{timer.paused&&<i aria-hidden="true">멈춤</i>}{timer.left}초</span>}
        <button type="button" role="switch" aria-checked={timerOn} className="mq-timer-switch"
          onClick={toggleTimer}>타이머<i aria-hidden="true"/></button>
      </span>
      <button type="button" role="switch" aria-checked={mode==='mcq'} className="mq-timer-switch mq-mode-switch"
        disabled={!!task?.answer} onClick={toggleMode}>객관식<i aria-hidden="true"/></button>
      {onMap&&<button className="pill-button" disabled={disabled||advancing} onClick={onMap}>개념 지도</button>}
      <details ref={menu} className="main-quiz-menu"><summary className="pill-button">더 보기</summary>
        <div className="mq-menu-pop" onClick={e=>{if((e.target as HTMLElement).closest('button'))menu.current?.removeAttribute('open');}}>
          {!task?.answer&&<button disabled={locked} onClick={()=>reveal(false)}>답만 보기</button>}
          <button disabled={disabled||advancing||!!view.blocked?.includes('학습일')} onClick={()=>onAction({kind:'skip'})}>이 문제 보류</button>
          <button disabled={disabled||advancing||!task||!!view.blocked?.includes('학습일')} onClick={exclude} aria-keyshortcuts="5">이 문제 제외 <kbd>5</kbd></button>
          {task&&editPath&&<button disabled={disabled||advancing} onClick={()=>setEditing(true)}>문제 수정·제보</button>}
          {/* 기록은 평가마다 저장된다. 이 버튼은 풀이를 멈추고 오늘 현황(시작 화면)으로 간다. */}
          <button disabled={disabled||advancing} onClick={onToday}>오늘 현황 보기</button>
        </div>
      </details></span>}
  </header>;
  if(view.finished)return <section className="mq-done">{head}
    <div className="mq-today mq-done-card"><div className="mq-today-text"><h2>오늘 목록을 마쳤어요</h2>
      <p>이번 회차 <b>{view.count}</b>문항 · 첫 학습 <b>{view.summary.learned}</b>/{view.summary.total} · 회상 가능 <b>{view.summary.recalled}</b></p></div>
      <div className="root-actions"><button className="pill-button" disabled={disabled||!view.canUndo} onClick={()=>onAction({kind:'undo'})}>되돌리기 <kbd>Z</kbd></button>
        <button className="mq-start-button" disabled={disabled} onClick={onToday}>오늘 현황으로</button></div></div>
    <details className="mq-more"><summary>학습 기록·남은 범위</summary><RootSummaryPanel summary={view.summary}/></details></section>;
  return <section className="quiz main-quiz-solve is-solving" aria-busy={advancing}>
    {head}
    <div className="quiz-progress bank-progress mq-solve-progress"><h2 className="main-quiz-question-heading" ref={heading} tabIndex={-1}>문항 {view.position+1} / {view.count}</h2>
      <span className="mq-track" aria-hidden="true"><i style={{width:`${view.count?done/view.count*100:0}%`}}/></span>
      {task&&tierPath&&<span className="bank-tags mq-tier">
        <label className={`bank-tier-control${task.question.tier==='Essential'?' is-essential':''}`} title="내 계정의 이 문제에만 적용됩니다. 중요도가 목표 기억률을 정하고, 높이면 더 자주·낮추면 덜 자주 복습합니다. Must-Know: 교수의 직접·간접적인 필수 지식 강조·출제 예고 / Core: 학습목표·기출 / Important: 강조·임상 중요 / Optional: 기타 세부사항">
          내 중요도{' '}
          <select aria-label="내 문제 중요도" value={task.question.tier} disabled={disabled||tierBusy}
            onChange={event=>void changeTier(event.target.value as BankTier)}>
            {(Object.keys(TIER_LABEL) as BankTier[]).map(tier=><option key={tier} value={tier}>{TIER_LABEL[tier]}</option>)}
          </select>
        </label>
        {task.question.targetMastery!=null&&<span className="bank-target" title="새 평가부터 이 목표 기억률로 복습 간격을 정합니다(Quiz Bank와 같은 방식). 실제 기억률을 잰 값은 아닙니다.">
          목표 {Math.round(task.question.targetMastery*100)}%</span>}
        {task.question.personalTier&&<button className="is-quiet bank-tier-reset" disabled={disabled||tierBusy}
          title={`원래 중요도: ${TIER_LABEL[task.question.originalTier??'Core']}`} onClick={()=>void changeTier(null)}>원래대로</button>}
      </span>}</div>
    {view.blocked&&<p role="alert">{view.blocked}</p>}
    {editNote&&<p className="bank-note mq-edit-note" role="status">{editNote}</p>}
    {task&&task.question.personalEdited&&<p className="mq-edited"><span className="tag">내 수정본</span></p>}
    {editing&&task&&editPath&&<PersonalQuestionDialog path={editPath(task.question.question_id)} questionId={task.question.question_id}
      answerVisible={!!task.answer} onClose={()=>setEditing(false)} onSaved={(result,reset)=>{
        setEditing(false);onEdited?.(result);
        setEditNote(reset?'원본으로 되돌렸습니다.':(result.highlighted?'강조 제보를 보냈습니다.':'관리자에게 전달했습니다.')+(result.question.personalEdited?' 내 수정본을 저장했습니다.':''));
      }}/>}
    {advancing&&<p className="bank-note" role="status">불러오는 중…</p>}
    {task&&<div className="quiz-card bank-card mq-card"><QuestionBody key={task.id} question={task.question} answer={task.answer} picked={picked}
      onStimuliReady={ready=>setImageState({taskId:task.id,ready})} onPick={pick} disabled={locked}
      showOptions={mcq?true:recall?choices||!!task.answer&&choicesSeen:!hiddenChoices} showChoiceScore={false}
      recallChoices={mcq?.choices??recall??undefined} choiceCorrectIds={mcq?.correct} choiceHint={!mcq}/>
      {recallClosed&&<button className="is-quiet" disabled={locked} onClick={showChoices} aria-keyshortcuts="V">선지 보기 <kbd>V</kbd></button>}
      {recallOpen&&<button className="is-quiet" disabled={locked} onClick={hideChoices} aria-keyshortcuts="V Z Control+Z Meta+Z">선지 접기 <kbd>V</kbd></button>}
      {hiddenChoices&&<button className="is-quiet" disabled={locked} onClick={showChoices}>선지 보기</button>}
      {task.answer&&<><hr className="quiz-line"/><AnswerBody question={task.question} answer={task.answer} reviewInline={false}/>
        <AnswerSlides key={task.id} answer={task.answer}/>
        <AnswerRecords task={task}/>
      </>}
    </div>}
    <div className="quiz-bar bank-solve-bar" aria-label="자기평가">
      <button className="quiz-undo" disabled={disabled||advancing||!view.canUndo} onClick={()=>onAction({kind:'undo'})} aria-keyshortcuts="Z Control+Z Meta+Z">되돌리기 <kbd>Z</kbd></button>
      {task?.answer?RATINGS.map((rating,i)=><button key={rating} className={`quiz-grade is-${rating.toLowerCase()}`} disabled={locked}
        onClick={()=>rate(rating)} aria-keyshortcuts={String(i+1)}><span className="quiz-grade-name">{rating}<kbd>{i+1}</kbd></span></button>):
        <button className="quiz-submit" disabled={locked||!task||!imagesReady} onClick={()=>reveal()} aria-keyshortcuts="Space Enter">답 보기 <kbd>Space</kbd></button>}
    </div>
  </section>;
}

/**
 * 참고 슬라이드 아래에 두는 이 문항의 기록(2026-11-08 사용자 지시). 회차 전체 메모는 서버가 이미 걸렀다.
 * 슬라이드가 원본 열기를 주므로 원본 링크는 슬라이드가 없을 때만 보인다.
 */
function AnswerRecords({task}:{task:NonNullable<RootView['task']>}) {
  const a=task.answer!;
  const notes=a.reviewNotes??[];
  const links=a.pdfSlides?.length||a.jokboPdfSlides?.length?[]:a.sourceLinks??[];
  const records=hasAnswerReview(a)||notes.length>0||links.length>0;
  return <>
    {records&&<details className="mq-records"><summary>이 문항 검토 기록</summary>
      <AnswerReviewItems answer={a}/>
      {notes.map((r,i)=><p key={i}><b>{r.source} · {r.verdict==='wrong'?'오류 지적':'판단 유보'}</b> {r.note}{r.suggested_answer&&` · 검토 제안: ${r.suggested_answer}`}</p>)}
      {links.map((s,i)=><p key={i}><a href={s.url} target="_blank" rel="noreferrer">{s.label}</a></p>)}
    </details>}
    {(task.helped||!task.attempted)&&<p className="bank-note mq-help-note">지도·선지 열람과 답만 보기는 따로 기록됩니다. 자기평가는 네 단계 중 자유롭게 고르세요.</p>}
  </>;
}
