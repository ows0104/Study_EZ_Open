import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { RootAction, RootView } from '../types/rootLearning';
import type { BankRating } from '../types/bank';
import { QuestionBody, AnswerBody } from './BankQuestion';
import { RootSummaryPanel } from './RootToday';

const PdfSlides = lazy(() => import('./RootPdfSlides').then(m => ({default:m.RootPdfSlides})));
const RATINGS: BankRating[] = ['Again', 'Hard', 'Good', 'Easy'];

export function RootSolve({view,scope,disabled,advancing,onAction,onToday,onError,onMap}:{view:RootView;scope:string;disabled:boolean;
  advancing:boolean;onAction:(a:RootAction)=>void;onToday:()=>void;onError:(message:string)=>void;onMap?:()=>void}) {
  const task=view.task;
  const key=`studyez:root-draft:${scope}:${JSON.stringify([view.revision,task?.id])}`;
  const [picked,setPicked]=useState<Set<string>>(new Set());
  const [choices,setChoices]=useState(false);
  const [imageState,setImageState]=useState<{taskId:string;ready:boolean}|null>(null);
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
    menu.current?.removeAttribute('open');
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
  if(view.finished)return <section className="quiz bank-start"><h2>오늘 목록을 마쳤어요</h2><p>이번 회차 목록 {view.count}문항</p>
    <details><summary>학습 기록·남은 범위</summary><RootSummaryPanel summary={view.summary}/></details>
    <div className="root-actions"><button disabled={disabled||!view.canUndo} onClick={()=>onAction({kind:'undo'})}>되돌리기 <kbd>Z</kbd></button><button className="quiz-submit" disabled={disabled} onClick={onToday}>오늘 현황으로</button></div></section>;
  return <section className="quiz main-quiz-solve is-solving" aria-busy={advancing}>
    <div className="quiz-progress bank-progress"><h2 className="main-quiz-question-heading" ref={heading} tabIndex={-1}>문항 {view.position+1} / {view.count}</h2>
      <span className="main-quiz-tools">{onMap&&<button disabled={disabled||advancing} onClick={onMap}>개념 지도</button>}
        <button disabled={disabled||advancing} onClick={onToday}>쉬기</button>
        <details ref={menu} className="main-quiz-menu"><summary>더 보기</summary>
          {!task?.answer&&<button disabled={locked} onClick={()=>reveal(false)}>답만 보기</button>}
          <button disabled={disabled||advancing||!!view.blocked?.includes('학습일')} onClick={()=>onAction({kind:'skip'})}>이 문제 보류</button>
        </details></span></div>
    {view.blocked&&<p role="alert">{view.blocked}</p>}
    {advancing&&<p className="bank-note" role="status">평가 저장 중…</p>}
    {task&&<div className="quiz-card bank-card"><QuestionBody key={task.id} question={task.question} answer={task.answer} picked={picked}
      onStimuliReady={ready=>setImageState({taskId:task.id,ready})} onPick={pick} disabled={locked}
      showOptions={!hiddenChoices} showChoiceScore={false}/>
      {hiddenChoices&&<button className="is-quiet" disabled={locked} onClick={showChoices}>선지 보기</button>}
      {task.answer&&<><hr className="quiz-line"/><AnswerBody question={task.question} answer={task.answer}/>
        {!!task.answer.pdfSlides?.length&&<Suspense fallback={<p role="status">참고 슬라이드를 준비하고 있습니다…</p>}>
          <PdfSlides key={task.id} slides={task.answer.pdfSlides}/></Suspense>}
        {!task.answer.pdfSlides?.length&&!task.answer.slides.length&&<p className="bank-note">이 문항에 연결된 참고 슬라이드가 없습니다.</p>}
        {(!!task.answer.reviewNotes?.length||!!task.answer.reviewIssues?.length||!!task.answer.sourceLinks?.length||task.helped||!task.attempted)&&
          <details className="main-quiz-details"><summary>자료·검토 기록</summary>
            {task.answer.reviewNotes?.map((r,i)=><p key={i}>{r.source} · {r.verdict==='wrong'?'오류 지적':'판단 유보'}: {r.note}{r.suggested_answer&&` · 검토 제안: ${r.suggested_answer}`}</p>)}
            {task.answer.reviewIssues?.map((issue,i)=><p key={i}>{issue}</p>)}
            {task.answer.sourceLinks?.map((s,i)=><p key={i}><a href={s.url} target="_blank" rel="noreferrer">{s.label}</a></p>)}
            {(task.helped||!task.attempted)&&<p className="bank-note">지도·선지 열람과 답만 보기는 별도로 기록됩니다. 자기평가는 네 단계 중 자유롭게 선택하세요.</p>}
          </details>}
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
