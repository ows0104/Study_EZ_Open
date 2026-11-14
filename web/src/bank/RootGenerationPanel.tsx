import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import './roots.css';
import { saveRootWebFile } from './rootWeb';
import { pollAfterSettled } from './pollChain';

type Input={conceptMap:string;points:string;scope:string;examDate:string|null;inputMode?:'provided'|'source'};
type Generation={id:string;requestId?:string;state:string;stage:string;message:string;published:boolean;revision:string;
  authoring?:string;parallelAuthoring?:boolean;pipeline?:string|null;awaitingWeb?:boolean;dispatched?:boolean;
  sources?:{id:string;kind:string;filename:string}[];operatorResumes?:number;restartOf?:string|null;
  privatePilot:boolean;featureEnabled:boolean;input:Input;report?:{repairRounds:number;taskCount:number;targetCount:number;
    pipelineVersion?:string;addRounds?:number;fixCount?:number;notReady?:number;mergedDuplicates?:number;unplacedQuestions?:number;coverageFallback?:number;importanceNotes?:number;
    issues:string[];questionNotes:{source:string;question_id:string;verdict:string;note:string}[];
    coverage:{point_id:string;status:string;reason:string}[]}|null};
type Props={subject:string;runId:string;onPublished?:()=>void};
// The click is this lecture's approval to send its sources to Codex CLI and, once validated, to publish (2026-11-09).
// 2026-11-11 사용자 「예습퀴즈처럼 다 빼고 버튼 하나만 남겨줘. 선택지는 지금 가장 최신 파이프라인으로. 기본 학생 공개.
// 체크하면 학생 비공개.」 (docs/changes/2026-11-11-main-quiz-one-button): a new request is always the newest pipeline,
// 새 구조 2 = map-tree/3 (root-generation/4) from the lecture's own sources on CLI. The one checkbox is privatePilot.
// A resume still repeats its original request exactly, whatever pipeline it used.
const NEWEST='map-tree/3';
const NEW_REQUEST={conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source' as const,
  authoring:'cli' as const,parallelAuthoring:false,pipeline:NEWEST};
const MAP_TREES=['map-tree/1','map-tree/2','map-tree/3'];
export function RootGenerationPanel(props:Props) {
  return <GenerationPanel key={props.subject+'/'+props.runId} {...props}/>;
}
function GenerationPanel({subject,runId,onPublished}:Props) {
  const base=`/api/admin/root-learning/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/generation`;
  // Unchecked = open to students. An earlier job's scope is not carried over: each press decides it again.
  const [privatePilot,setPrivate]=useState(false);
  const [reason,setReason]=useState('');
  const [job,setJob]=useState<Generation|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [loaded,setLoaded]=useState(false);
  const sending=useRef(false);
  const [loadVersion,setLoadVersion]=useState(0);
  useEffect(()=>{let live=true;api<{generation:Generation|null}>(base).then(({generation:g})=>{
    if(live){setLoaded(true);if(g)setJob(g);}
  }).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[base,loadVersion]);
  const pending=!!job&&(['queued','running'].includes(job.state)||!!job.awaitingWeb&&!['canceled','failed'].includes(job.state));
  useEffect(()=>{
    if(!pending)return;
    let live=true;
    // 고정 간격은 이 GET이 3초보다 오래 걸릴 때 요청을 겹쳐 쌓는다 — 까닭은 pollChain.ts에 있다.
    const stop=pollAfterSettled(()=>api<{generation:Generation|null}>(base).then(({generation:g})=>{
      if(live){setJob(g);if(g?.published)onPublished?.();}
    }).catch(e=>{if(live)setError(e.message);}),3000);
    return()=>{live=false;stop();};
  },[base,pending,onPublished]);
  // mode: 'new' (the newest default), 'resume' (the original request, remaining budgets) or 'restart' (「새로 출제」:
  // the newest default as a new request beside the ended one, fresh budgets; docs/changes/2026-11-11-main-quiz-start-over).
  async function send(mode:'new'|'resume'|'restart'='new'){
    if(sending.current)return;
    sending.current=true;setBusy(true);setError('');
    try{
      // A resume repeats the original request exactly (the server refuses a changed input under the same ID).
      const original=mode==='resume'&&job?job:null;
      let body;
      if(original){
        const source=(original.input.inputMode??'provided')==='source';
        body={...original.input,conceptMap:source?'':original.input.conceptMap,points:source?'':original.input.points,
          inputMode:source?'source':'provided',requestId:original.requestId??crypto.randomUUID(),privatePilot:original.privatePilot,resume:true,
          authoring:original.authoring??'cli',parallelAuthoring:original.parallelAuthoring??false,
          ...(original.pipeline?{pipeline:original.pipeline}:{}),...(reason.trim()?{resumeReason:reason.trim()}:{})};
      }else if(mode==='restart'&&job)body={...NEW_REQUEST,requestId:crypto.randomUUID(),privatePilot:job.privatePilot,resume:false,
        restart:true,resumeReason:reason.trim()};
      else body={...NEW_REQUEST,requestId:crypto.randomUUID(),privatePilot,resume:false};
      const result=await api<{generation:Generation}>(base,{method:'POST',body:JSON.stringify(body)});
      setJob(result.generation);setReason('');if(result.generation.published)onPublished?.();
    }catch(e){setError(e instanceof Error?e.message:'요청을 저장하지 못했습니다.');}finally{sending.current=false;setBusy(false);}
  }
  const resumable=!!job&&!job.published&&!pending&&!job.awaitingWeb;
  const needsReason=resumable&&MAP_TREES.includes(job?.pipeline??'');
  // The server sets aside only an ended request (failed·canceled); a held one is resumed or stopped first.
  const restartable=needsReason&&['failed','canceled'].includes(job?.state??'');
  const fresh=!resumable&&!pending;
  const label=busy?'요청 중…':pending?'생성·업로드 진행 중':resumable?'Main Quiz 이어서 만들기':'Main Quiz 만들기';
  return <section className="root-card root-generation" aria-label="Main Quiz 만들기"><h3>Main Quiz 만들기</h3>
    {needsReason&&<label>이유 (이어 하기·새로 출제 모두 이유가 있을 때만 다시 돕니다)<input aria-label="이어 하기 이유" value={reason} maxLength={500} onChange={e=>setReason(e.target.value)}/></label>}
    <div className="root-generation-action">
      <button className="is-primary" disabled={!loaded&&!error||busy||pending||needsReason&&!reason.trim()} onClick={()=>{if(!loaded){setError('');setLoadVersion(v=>v+1);}else void send(resumable?'resume':'new');}}>{loaded?label:error?'기존 작업 다시 확인':'기존 작업 확인 중…'}</button>
      {restartable&&<button disabled={busy||!reason.trim()} onClick={()=>void send('restart')}>새로 출제 (처음부터)</button>}
      {fresh&&<label><input type="checkbox" checked={privatePilot} disabled={busy} onChange={e=>setPrivate(e.target.checked)}/>학생 비공개 (내 계정에서만 확인)</label>}
    </div>
    {fresh&&<div role="note" aria-label="이 요청이 승인하는 것">
      <p><strong>이 버튼이 이 강의의 승인입니다.</strong> 이 강의에 등록된 올해 필기(S1)와 족보(S2, 있으면) PDF를 OpenAI Codex CLI로 보내 새 구조 2로 출제합니다. {privatePilot?'검증을 통과하면 내 계정에만 공개되고 학생에게는 보이지 않습니다.':'검증을 통과하면 학생에게 바로 공개됩니다.'}</p>
      <p className="root-generation-fine">러너를 켜두세요. 호출 상한: 개념 지도 1 · 출제포인트 1 · 문제은행 1 · 포인트 대조 최대 2 · 포인트 보완 최대 1 · 커버 확인(목표 60개마다 1, 빈 목표 추가 뒤 다시) · 지도 확인 최대 2 · 목표 밖 문항 포인트 보충 최대 2 · 빈 목표 추가 최대 2 · 문항 검토(40문항마다 1, 고친 문항만 다시) · 문항 고치기 문항마다 최대 2 · 임상 정리 1 · 의학 검토 1. 기존 문제와 학습 기록은 보존하고, 이미 공개된 판이 있는 강의는 요청이 거절됩니다.</p>
    </div>}
    {resumable&&<p>같은 입력·같은 공개 범위({job!.privatePilot?'학생 비공개':'학생 공개'})와 남은 수정 횟수로 이어서 진행합니다. 기존 실패 기록은 보존합니다.</p>}
    {restartable&&<p className="root-generation-fine">새로 출제: 이 판은 그대로 두고, 같은 공개 범위로 최신 새 구조 2 작업을 새로 등록합니다. 필기(S1)·족보(S2) PDF를 OpenAI Codex CLI로 다시 보내고 수정·추가 횟수를 처음부터 받습니다. 이 버튼이 그 승인입니다.</p>}
    {error&&<p role="alert">{error}</p>}
    {job&&<div role="status"><p>{job.published?'게시 완료':job.awaitingWeb?'웹 응답 대기':job.state==='queued'?'러너 대기':job.state==='running'?'출제·검수 진행 중':'작업 중지·실패'} · {job.stage||job.message}{job.published?job.privatePilot?' · 학생 비공개':' · 학생 공개':''}</p>
      {job.sources?.length?<p>보낸 자료: {job.sources.map(s=>s.id+' '+s.filename).join(' · ')}</p>:null}
      {job.published?<><Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`}>Main Quiz 열기 →</Link>
        {!job.featureEnabled&&<p>콘텐츠는 저장되었습니다. 현재 Main Quiz 학습 공개 설정은 꺼져 있습니다.</p>}</>:null}</div>}
    {job?.awaitingWeb&&<details><summary>응답 전달 복구</summary><p>자동 회수가 되지 않을 때만 완성된 응답 파일을 전달하세요.</p><label>완성된 웹 응답 JSON 불러오기 (기존 MD 지원)<input type="file" accept=".json,.md" aria-label="웹 응답 파일" disabled={busy} onChange={async e=>{const file=e.target.files?.[0];if(!file)return;setBusy(true);try{await saveRootWebFile(job.id,file);setError('');}catch(err){setError((err as Error).message);}finally{setBusy(false);}}}/></label></details>}
    {job?.report&&<details><summary>생성·검수 결과</summary><p>목표 {job.report.targetCount}개 · 준비된 과제 {job.report.taskCount}개 · {job.report.pipelineVersion==='root-generation/4'
      ?`빈 부분 추가 ${job.report.addRounds}/2회 · 고친 문항 ${job.report.fixCount}개 · 다 묻지 못한 목표 ${job.report.notReady}개 · 중복으로 합친 문항 ${job.report.mergedDuplicates}개 · 목표에 못 붙은 문항 ${job.report.unplacedQuestions}개${job.report.coverageFallback!=null?` · 범위 점검 판정으로 붙인 문항 ${job.report.coverageFallback}개`:''}`
      :job.report.pipelineVersion==='root-generation/3'
      ?`빈 목표 추가 ${job.report.addRounds}/2회 · 고친 문항 ${job.report.fixCount}개 · 준비 안 된 목표 ${job.report.notReady}개`:`수정 ${job.report.repairRounds}/3회`}</p>
      <ul>{job.report.issues.map((text,i)=><li key={i}>{text}</li>)}{job.report.questionNotes.map((r,i)=><li key={'q'+i}>{r.source} · {r.question_id} · {r.verdict}: {r.note}</li>)}</ul>
      <ul>{job.report.coverage.map(c=><li key={c.point_id}>{c.point_id} · {c.status} · {c.reason}</li>)}</ul></details>}
  </section>;
}
