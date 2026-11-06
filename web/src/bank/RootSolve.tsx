import { useEffect, useRef, useState } from 'react';
import type { RootAction, RootView } from '../types/rootLearning';
import { QuestionBody, AnswerBody } from './BankQuestion';
import { RootSummaryPanel } from './RootToday';

export function RootSolve({view,scope,disabled,advancing,onAction,onToday,onError}:{view:RootView;scope:string;disabled:boolean;
  advancing:boolean;onAction:(a:RootAction)=>void;onToday:()=>void;onError:(message:string)=>void}) {
  const task=view.task;
  const key=`studyez:root-draft:${scope}:${JSON.stringify([view.revision,task?.id])}`;
  const [response,setResponse]=useState('');
  const [picked,setPicked]=useState<Set<string>>(new Set());
  const [choices,setChoices]=useState(false);
  const [imageState,setImageState]=useState<{taskId:string;ready:boolean}|null>(null);
  const imagesReady=!task?.question.stimuli?.length||(imageState?.taskId===task.id&&imageState.ready);
  const heading=useRef<HTMLHeadingElement>(null);
  const hiddenChoices=task?.question.mcq_mode==='recall_first'&&!choices&&!task.answer;
  useEffect(()=>{
    try {
      setResponse(localStorage.getItem(key)??'');
      const ids:unknown=JSON.parse(localStorage.getItem(key+':picks')??'[]');
      const allowed=new Set(task?.question.options.map(o=>o.id)??[]);
      if(!Array.isArray(ids)||!ids.every(id=>typeof id==='string'&&allowed.has(id)))throw Error('invalid saved choices');
      setPicked(new Set(ids));setChoices(localStorage.getItem(key+':choices')==='shown');
    }catch{setPicked(new Set());setChoices(false);onError('작성 중 응답을 읽지 못했습니다. 입력 내용을 확인하고 다시 불러오세요.');}
    heading.current?.focus();window.scrollTo(0,0);
  },[key]);
  function save(suffix:string,text:string) {
    try{localStorage.setItem(key+suffix,text);return true;}
    catch{onError('작성 중 응답을 보관하지 못했습니다. 화면을 닫기 전에 복사하세요.');return false;}
  }
  function draft(text:string){setResponse(text);save('',text);}
  function pick(id:string){
    if(disabled||task?.answer)return;
    const next=new Set(task?.question.format==='mcq'?[]:picked);
    if(picked.has(id)&&task?.question.format!=='mcq')next.delete(id);else next.add(id);
    if(save(':picks',JSON.stringify([...next])))setPicked(next);
  }
  function showChoices(){if(save(':choices','shown'))setChoices(true);}
  function reveal(attempted:boolean){
    if(disabled||advancing||view.blocked||!task||task.answer||attempted&&!imagesReady)return;
    const savedResponse=response+(picked.size?`\n선택: ${[...picked].join(', ')}`:'');
    if(savedResponse.length>10000){onError('선택 기록을 포함한 응답이 너무 깁니다. 내 답을 조금 줄인 뒤 확인하세요. 현재 입력은 보존했습니다.');return;}
    onAction({kind:'reveal',attempted,response:savedResponse,
      helped:view.mapSeen,choicesShown:!!task.question.options.length&&!hiddenChoices,
      ...(attempted&&task.question.stimuli?.length?{stimulusHashes:task.question.stimuli.map(s=>s.sha256)}:{})});
  }
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      const target=event.target as HTMLElement;
      if(event.defaultPrevented||event.repeat||event.isComposing||event.ctrlKey||event.metaKey||event.altKey||disabled||advancing||!task||view.blocked)return;
      if(document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')||target.closest('input,textarea,select,[contenteditable="true"]'))return;
      if(target.closest('button,a,summary')&&!target.closest('.bank-options'))return;
      if((event.code==='Space'||event.key==='Enter')&&!task.answer){event.preventDefault();reveal(true);}
      if(task.answer&&['1','2','3'].includes(event.key)){
        if(event.key==='3'&&(task.helped||!task.attempted))return;
        event.preventDefault();onAction({kind:'rate',grade:({'1':'missed','2':'partial','3':'independent'} as const)[event.key as '1'|'2'|'3']});
      }
      if(event.key.toLowerCase()==='z'&&view.canUndo){event.preventDefault();onAction({kind:'undo'});}
    };
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  },[disabled,advancing,task,response,picked,imagesReady,hiddenChoices,view.mapSeen,view.blocked,view.canUndo]);
  if(advancing)return <section className="quiz" role="status">평가를 저장하고 다음 문제를 준비하고 있습니다…</section>;
  if(view.finished)return <section className="quiz bank-start"><h2>오늘 목록을 마쳤어요</h2><p>이번 회차 목록 {view.count}문항</p>
    <details><summary>학습 기록·남은 범위</summary><RootSummaryPanel summary={view.summary}/></details>
    <div className="root-actions"><button disabled={disabled||!view.canUndo} onClick={()=>onAction({kind:'undo'})}>직전 자기평가 취소</button><button className="quiz-submit" disabled={disabled} onClick={onToday}>오늘 현황으로</button></div></section>;
  return <section className="quiz main-quiz-solve">
    <div className="quiz-progress bank-progress"><h2 className="main-quiz-question-heading" ref={heading} tabIndex={-1}>문항 {view.position+1} / {view.count}</h2>
      <button className="is-quiet" disabled={disabled} onClick={onToday}>쉬기·오늘 현황</button></div>
    <progress aria-label="이번 회차 진행" max={Math.max(1,view.count)} value={view.position}/>
    {view.blocked&&<p role="alert">{view.blocked}</p>}
    {task&&<article><QuestionBody key={task.id} question={task.question} answer={task.answer} picked={picked}
      onStimuliReady={ready=>setImageState({taskId:task.id,ready})} onPick={pick} disabled={disabled}
      showOptions={!hiddenChoices} showChoiceScore={false}/>
      {hiddenChoices&&<button className="is-quiet" disabled={disabled} onClick={showChoices}>선지 보기</button>}
      <details className="main-quiz-draft" key={key}><summary>내 답 적기 · 선택</summary>
        <textarea aria-label="Main Quiz 응답" readOnly={!!task.answer} value={task.response??response} onChange={e=>draft(e.target.value)} maxLength={10000}/></details>
      {!task.answer?<><button className="quiz-submit main-quiz-reveal" disabled={disabled||!!view.blocked||!imagesReady} onClick={()=>reveal(true)}>답 확인 <kbd>Space</kbd></button>
        <button className="is-quiet" disabled={disabled||!!view.blocked} onClick={()=>reveal(false)}>답만 보기</button></>:<section className="main-quiz-answer">
        <AnswerBody question={task.question} answer={task.answer}/>
        {!!task.answer.reviewNotes?.length&&<details><summary>문항별 검수 의견</summary>{task.answer.reviewNotes.map((r,i)=><p key={i}>{r.source} · {r.verdict==='wrong'?'오류 지적':'판단 유보'}: {r.note}{r.suggested_answer&&` · 검토 제안: ${r.suggested_answer}`}</p>)}</details>}
        {!!task.answer.reviewIssues?.length&&<details><summary>범위·미해결 검토 기록</summary><ul>{task.answer.reviewIssues.map((issue,i)=><li key={i}>{issue}</li>)}</ul></details>}
        {!!task.answer.sourceLinks?.length&&<details><summary>출제 당시 원본 자료</summary>{task.answer.sourceLinks.map((s,i)=><p key={i}><a href={s.url} target="_blank" rel="noreferrer">{s.label}</a></p>)}</details>}
        <p className="bank-note">{task.attempted?'시도 후 답 확인':'답만 확인 · 첫 학습에 포함하지 않음'}{task.helped?' · 도움 노출 있음':''}</p>
        <div className="main-quiz-ratings" aria-label="회상 자기평가"><button disabled={disabled||!!view.blocked} onClick={()=>onAction({kind:'rate',grade:'missed'})}>1 못 떠올림</button>
          <button disabled={disabled||!!view.blocked} onClick={()=>onAction({kind:'rate',grade:'partial'})}>2 일부만·도움 받아 떠올림</button>
          <button disabled={disabled||!!view.blocked||task.helped||!task.attempted} onClick={()=>onAction({kind:'rate',grade:'independent'})}>3 스스로 떠올림</button></div>
      </section>}
    </article>}
    <div className="root-actions main-quiz-secondary"><button className="is-quiet" disabled={disabled||!view.canUndo} onClick={()=>onAction({kind:'undo'})}>직전 자기평가 취소</button>
      <button className="is-quiet" disabled={disabled||!!view.blocked&&view.blocked.includes('학습일')} onClick={()=>onAction({kind:'skip'})}>이 문제 보류하고 다음</button></div>
  </section>;
}
