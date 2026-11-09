import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { RootAction, RootView } from '../types/rootLearning';
import type { BankQuestion as BankQuestionData, BankRating, BankTier } from '../types/bank';
import { api } from '../api';
import { QuestionBody, AnswerBody, AnswerReviewItems, hasAnswerReview } from './BankQuestion';
import { PersonalQuestionDialog, type PersonalQuestionResult } from './PersonalQuestionDialog';
import { RootSummaryPanel } from './RootToday';

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
  const [choices,setChoices]=useState(false);
  const [imageState,setImageState]=useState<{taskId:string;ready:boolean}|null>(null);
  const [editing,setEditing]=useState(false);
  const [editNote,setEditNote]=useState('');
  const [tierBusy,setTierBusy]=useState(false);
  const heading=useRef<HTMLHeadingElement>(null);
  const menu=useRef<HTMLDetailsElement>(null);
  const locked=disabled||advancing||!!view.blocked;
  const imagesReady=!task?.question.stimuli?.length||(imageState?.taskId===task.id&&imageState.ready);
  const hiddenChoices=task?.question.mcq_mode==='recall_first'&&!choices&&!task.answer;
  useEffect(()=>{
    try {
      const ids:unknown=JSON.parse(localStorage.getItem(key+':picks')??'[]');
      const allowed=new Set(task?.question.options.map(o=>o.id)??[]);
      if(!Array.isArray(ids)||!ids.every(id=>typeof id==='string'&&allowed.has(id)))throw Error('invalid saved choices');
      setPicked(new Set(ids));setChoices(localStorage.getItem(key+':choices')==='shown');
    }catch{setPicked(new Set());setChoices(false);onError('보관된 선지 선택을 읽지 못했습니다. 원본을 보존했습니다.');}
    menu.current?.removeAttribute('open');setEditing(false);setEditNote('');
    heading.current?.focus();window.scrollTo(0,0);
  },[key]);
  function save(suffix:string,text:string) {
    try{localStorage.setItem(key+suffix,text);return true;}
    catch{onError('선지 선택을 보관하지 못했습니다. 브라우저 저장 공간을 확인하세요.');return false;}
  }
  function pick(id:string){
    if(locked||task?.answer)return;
    const next=new Set(task?.question.format==='mcq'?[]:picked);
    if(picked.has(id)&&task?.question.format!=='mcq')next.delete(id);else next.add(id);
    if(save(':picks',JSON.stringify([...next])))setPicked(next);
    heading.current?.focus({preventScroll:true});
  }
  function showChoices(){if(save(':choices','shown'))setChoices(true);heading.current?.focus({preventScroll:true});}
  function reveal(attempted=true){
    if(locked||!task||task.answer||attempted&&!imagesReady)return;
    // Retired text drafts remain untouched in storage; no new text is required.
    const response=picked.size?`선택: ${[...picked].join(', ')}`:'';
    onAction({kind:'reveal',attempted,response,helped:view.mapSeen,
      choicesShown:!!task.question.options.length&&!hiddenChoices,
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
  function rate(selfRating:BankRating){if(!locked&&task?.answer)onAction({kind:'rate',selfRating});}
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      const target=event.target as HTMLElement;
      if(event.defaultPrevented||event.repeat||event.isComposing||event.ctrlKey||event.metaKey||event.altKey||locked||!task)return;
      if(document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')||target.closest('input,textarea,select,[contenteditable="true"]'))return;
      const number=/^[1-4]$/.test(event.key);
      if(target.closest('a,summary')||target.closest('button')&&!number)return;
      if((event.code==='Space'||event.key==='Enter')&&!task.answer){event.preventDefault();reveal();}
      if(task.answer&&number){event.preventDefault();rate(RATINGS[Number(event.key)-1]);}
      if(event.key.toLowerCase()==='z'&&view.canUndo){event.preventDefault();onAction({kind:'undo'});}
    };
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  },[locked,task,picked,imagesReady,hiddenChoices,view.mapSeen,view.canUndo]);
  const done=Math.min(view.position,view.count);
  const head=<header className="mq-solve-head">
    <p className="mq-kicker"><span className="mq-badge">Main-Quiz</span>{title&&<span className="mq-solve-title">{title}</span>}</p>
    {!view.finished&&<span className="main-quiz-tools">{onMap&&<button className="pill-button" disabled={disabled||advancing} onClick={onMap}>개념 지도</button>}
      <details ref={menu} className="main-quiz-menu"><summary className="pill-button">더 보기</summary>
        <div className="mq-menu-pop" onClick={e=>{if((e.target as HTMLElement).closest('button'))menu.current?.removeAttribute('open');}}>
          {!task?.answer&&<button disabled={locked} onClick={()=>reveal(false)}>답만 보기</button>}
          <button disabled={disabled||advancing||!!view.blocked?.includes('학습일')} onClick={()=>onAction({kind:'skip'})}>이 문제 보류</button>
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
      showOptions={!hiddenChoices} showChoiceScore={false}/>
      {hiddenChoices&&<button className="is-quiet" disabled={locked} onClick={showChoices}>선지 보기</button>}
      {task.answer&&<><hr className="quiz-line"/><AnswerBody question={task.question} answer={task.answer} reviewInline={false}/>
        <AnswerSlides key={task.id} answer={task.answer}/>
        <AnswerRecords task={task}/>
      </>}
    </div>}
    <div className="quiz-bar bank-solve-bar" aria-label="자기평가">
      <button className="quiz-undo" disabled={disabled||advancing||!view.canUndo} onClick={()=>onAction({kind:'undo'})} aria-keyshortcuts="Z">되돌리기 <kbd>Z</kbd></button>
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
