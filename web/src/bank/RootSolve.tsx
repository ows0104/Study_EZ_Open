import { useEffect, useRef, useState } from 'react';
import type { RootAction, RootView } from '../types/rootLearning';
import { QuestionBody, AnswerBody } from './BankQuestion';
import { RootSummaryPanel, RootPolicyNotice } from './RootToday';

export function RootSolve({view,scope,disabled,advancing,onAction,onToday,onError}:{view:RootView;scope:string;disabled:boolean;
  advancing:boolean;onAction:(a:RootAction)=>void;onToday:()=>void;onError:(message:string)=>void}) {
  const task=view.task;
  const key=`studyez:root-draft:${scope}:${JSON.stringify([view.revision,task?.id])}`;
  const [response,setResponse]=useState('');
  const [picked,setPicked]=useState<Set<string>>(new Set());
  const [imageState,setImageState]=useState<{taskId:string;ready:boolean}|null>(null);
  const imagesReady=!task?.question.stimuli?.length||(imageState?.taskId===task.id&&imageState.ready);
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{
    try{setResponse(localStorage.getItem(key)??'');}catch{onError('작성 중 응답을 읽지 못했습니다. 화면을 닫기 전에 입력을 복사하세요.');}
    setPicked(new Set());heading.current?.focus();
  },[key]);
  function draft(text:string){setResponse(text);try{localStorage.setItem(key,text);}catch{onError('작성 중 응답을 보관하지 못했습니다. 화면을 닫기 전에 복사하세요.');}}
  function reveal(attempted:boolean){if(attempted&&!imagesReady)return;onAction({kind:'reveal',attempted,response:response+(picked.size?`\n선택: ${[...picked].join(', ')}`:''),helped:task?.helped,
    ...(attempted&&task?.question.stimuli?.length?{stimulusHashes:task.question.stimuli.map(s=>s.sha256)}:{})});}
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      const target=event.target as HTMLElement;
      if(disabled||advancing||!task||target.closest('input,textarea,select,button,[contenteditable="true"]'))return;
      if(event.code==='Space'&&!task.answer){event.preventDefault();reveal(true);}
      if(task.answer&&['1','2','3'].includes(event.key)){
        if(event.key==='3'&&(task.helped||!task.attempted))return;
        event.preventDefault();onAction({kind:'rate',grade:({'1':'missed','2':'partial','3':'independent'} as const)[event.key as '1'|'2'|'3']});
      }
    };
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  },[disabled,advancing,task,response,picked,imagesReady]);
  if(advancing)return <p role="status">다음 질문 준비 중… 평가 저장을 확인하고 있습니다.</p>;
  if(view.finished)return <section><h2>오늘 목록 종료</h2><RootPolicyNotice policy={view.policy}/><RootSummaryPanel summary={view.summary}/><p>이 회차 {view.count}개 과제를 마쳤습니다. 준비 전·미학습 목표는 별도로 남아 있습니다.</p>
    <button disabled={disabled||!view.canUndo} onClick={()=>onAction({kind:'undo'})}>직전 자기평가 취소</button><button disabled={disabled} onClick={onToday}>오늘 현황으로</button></section>;
  return <section><p>뿌리 학습 · 질문 {view.position+1}/{view.count}</p><RootPolicyNotice policy={view.policy}/>
    <h2 ref={heading} tabIndex={-1}>현재 연결 {view.position+1}</h2>
    {view.blocked&&<p role="alert">{view.blocked}</p>}
    {task&&<article className="root-card"><QuestionBody key={task.id} question={task.question} answer={task.answer} picked={picked}
      onStimuliReady={ready=>setImageState({taskId:task.id,ready})}
      onPick={id=>setPicked(old=>{const next=new Set(old);next.has(id)?next.delete(id):next.add(id);return next;})} disabled={disabled} showChoiceScore={false}/>
      <label>떠올린 내용<textarea aria-label="뿌리 질문 응답" readOnly={!!task.answer} value={task.response??response} onChange={e=>draft(e.target.value)} maxLength={10000}/></label>
      {!task.answer?<div className="root-actions"><button disabled={disabled||!imagesReady} onClick={()=>reveal(true)}>떠올려본 뒤 답 확인</button><button disabled={disabled} onClick={()=>reveal(false)}>답만 보기</button></div>:<>
        <AnswerBody question={task.question} answer={task.answer}/>
        {task.answer.reviewNotes?.map((r,i)=><p className="bank-note" key={i}>{r.source} · {r.verdict==='wrong'?'오류 지적':'판단 유보'}: {r.note}{r.suggested_answer&&` · 검토 제안: ${r.suggested_answer}`}</p>)}
        {!!task.answer.reviewIssues?.length&&<details><summary>범위·미해결 검토 기록</summary><ul>{task.answer.reviewIssues.map((issue,i)=><li key={i}>{issue}</li>)}</ul></details>}
        {!!task.answer.sourceLinks?.length&&<p>출제 당시 원본: {task.answer.sourceLinks.map((s,i)=><a key={i} href={s.url} target="_blank" rel="noreferrer">{s.label} </a>)}</p>}
        <p>{task.attempted?'시도 후 답 확인':'답만 확인 · 첫 학습에 포함하지 않음'}{task.helped?' · 도움 노출 있음':''}</p>
        <div className="root-actions" aria-label="방향 자기평가"><button disabled={disabled} onClick={()=>onAction({kind:'rate',grade:'missed'})}>1 못 떠올림</button>
          <button disabled={disabled} onClick={()=>onAction({kind:'rate',grade:'partial'})}>2 일부만·도움 받아 떠올림</button>
          <button disabled={disabled||task.helped||!task.attempted} onClick={()=>onAction({kind:'rate',grade:'independent'})}>3 스스로 떠올림</button></div>
      </>}
    </article>}
    <div className="root-actions"><button disabled={disabled||!view.canUndo} onClick={()=>onAction({kind:'undo'})}>직전 자기평가 취소</button>
      <button disabled={disabled||!!view.blocked&&view.blocked.includes('학습일')} onClick={()=>onAction({kind:'skip'})}>이 과제 보류하고 다음</button><button disabled={disabled} onClick={onToday}>중단·오늘 현황</button></div>
  </section>;
}
