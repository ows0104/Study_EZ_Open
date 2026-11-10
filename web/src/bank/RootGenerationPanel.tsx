import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import './roots.css';
import { saveRootWebFile } from './rootWeb';
import { pollAfterSettled } from './pollChain';

type Input={conceptMap:string;points:string;scope:string;examDate:string|null;inputMode?:'provided'|'source'};
type Generation={id:string;requestId?:string;state:string;stage:string;message:string;published:boolean;revision:string;
  authoring?:string;parallelAuthoring?:boolean;pipeline?:string|null;awaitingWeb?:boolean;dispatched?:boolean;
  sources?:{id:string;kind:string;filename:string}[];operatorResumes?:number;
  privatePilot:boolean;featureEnabled:boolean;input:Input;report?:{repairRounds:number;taskCount:number;targetCount:number;
    pipelineVersion?:string;addRounds?:number;fixCount?:number;notReady?:number;
    issues:string[];questionNotes:{source:string;question_id:string;verdict:string;note:string}[];
    coverage:{point_id:string;status:string;reason:string}[]}|null};
type Props={subject:string;runId:string;onPublished?:()=>void};
// map-tree/1 (2026-11-09 사용자 결정): the pilots' Map /3 → points /3 → audit/repair front stages in the runner.
// The click is this lecture's approval to send its sources to Codex CLI and, once validated, to open it to students.
// map-tree/2 (2026-11-10, docs/changes/2026-11-10-root-generation-3): the same front stages plus an independent bank,
// then root-generation/3 (coverage check → add only for empty goals → batch review → one medical review).
type Mode='map-tree'|'map-tree-v3'|'parallel'|'provided';
const MAP_TREE='map-tree/1';
const MAP_TREE_V3='map-tree/2';
function modeOf(g:Generation):Mode{return g.pipeline===MAP_TREE?'map-tree':g.pipeline===MAP_TREE_V3?'map-tree-v3':g.input.inputMode==='provided'?'provided':g.parallelAuthoring?'parallel':'map-tree';}
const isMapTree=(m:Mode)=>m==='map-tree'||m==='map-tree-v3';
export function RootGenerationPanel(props:Props) {
  return <GenerationPanel key={props.subject+'/'+props.runId} {...props}/>;
}
function GenerationPanel({subject,runId,onPublished}:Props) {
  const base=`/api/admin/root-learning/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/generation`;
  const [input,setInput]=useState<Input>({conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'});
  const [mode,setMode]=useState<Mode>('map-tree');
  const [privatePilot,setPrivate]=useState(false);
  const [reason,setReason]=useState('');
  const [job,setJob]=useState<Generation|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [loaded,setLoaded]=useState(false);
  const sending=useRef(false);
  const [loadVersion,setLoadVersion]=useState(0);
  useEffect(()=>{let live=true;api<{generation:Generation|null}>(base).then(({generation:g})=>{
    if(live){setLoaded(true);if(g){setJob(g);setInput(g.input);setPrivate(g.privatePilot);setMode(modeOf(g));}}
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
  function chooseMode(next:Mode){setMode(next);setInput(old=>({...old,inputMode:next==='provided'?'provided':'source'}));}
  async function send(resume=false){
    if(sending.current)return;
    sending.current=true;setBusy(true);setError('');
    try{
      // A resume repeats the original request exactly (the server refuses a changed input under the same ID).
      const original=resume&&job?job:null;
      const data=original?original.input:input;
      const source=original?(original.input.inputMode??'provided')==='source':mode!=='provided';
      const pipeline=original?original.pipeline:mode==='map-tree'?MAP_TREE:mode==='map-tree-v3'?MAP_TREE_V3:null;
      const result=await api<{generation:Generation}>(base,{method:'POST',body:JSON.stringify({
        ...data,conceptMap:source?'':data.conceptMap,points:source?'':data.points,inputMode:source?'source':'provided',
        requestId:original?.requestId??crypto.randomUUID(),privatePilot:original?original.privatePilot:privatePilot,resume,
        authoring:original?original.authoring??'cli':'cli',parallelAuthoring:original?original.parallelAuthoring??false:mode==='parallel',
        ...(pipeline?{pipeline}:{}),...(resume&&reason.trim()?{resumeReason:reason.trim()}:{})})});
      setJob(result.generation);setReason('');if(result.generation.published)onPublished?.();
    }catch(e){setError(e instanceof Error?e.message:'요청을 저장하지 못했습니다.');}finally{sending.current=false;setBusy(false);}
  }
  async function upload(field:'conceptMap'|'points',file?:File){
    if(!file)return;
    if(file.size>1500000){setError('텍스트 파일은 1.5MB 이하로 선택하세요.');return;}
    try{const value=await file.text();setInput(old=>({...old,[field]:value}));setError('');}
    catch{setError('파일을 읽지 못했습니다. 내용을 직접 붙여 넣으세요.');}
  }
  const sourceMode=mode!=='provided';
  const resumable=!!job&&!job.published&&!pending&&!job.awaitingWeb;
  const needsReason=resumable&&(job?.pipeline===MAP_TREE||job?.pipeline===MAP_TREE_V3);
  const label=busy?'요청 중…':pending?'생성·업로드 진행 중':resumable?'Main Quiz 이어서 만들기':'Main Quiz 만들기';
  const showApproval=!resumable&&!pending&&isMapTree(mode);
  return <section className="root-card root-generation" aria-label="Main Quiz 만들기"><h3>Main Quiz 만들기</h3>
    <p>{isMapTree(mode)?'올해 필기·족보에서 개념 지도와 출제포인트를 뽑아 대조·보완한 뒤 문항을 만들고, 검수를 거쳐 자동으로 올립니다.':'올해 필기·족보로 문제은행을 만들고, 개념도·출제포인트와 통합·검수한 뒤 자동으로 업로드합니다.'}</p>
    {showApproval&&<div role="note" aria-label="이 요청이 승인하는 것">
      <p><strong>이 버튼이 이 강의의 승인입니다.</strong> 이 강의에 등록된 올해 필기(S1)와 족보(S2, 있으면) PDF를 OpenAI Codex CLI로 보냅니다.</p>
      {mode==='map-tree-v3'
        ?<p>호출 상한: 개념 지도 1 · 출제포인트 1 · 문제은행 1 · 포인트 대조 최대 2 · 포인트 보완 최대 1 · 커버 확인(목표 60개마다 1, 빈 목표 추가 뒤 다시) · 지도 확인 최대 2 · 목표 밖 문항 포인트 보충 최대 2 · 빈 목표 추가 최대 2 · 문항 검토(40문항마다 1, 고친 문항만 다시) · 문항 고치기 문항마다 최대 2 · 임상 정리 1 · 의학 검토 1. 새 구조 시범이라 예상 시간은 아직 모릅니다.</p>
        :<p>호출 상한: 개념 지도 1 · 출제포인트 1 · 포인트 대조 최대 2 · 포인트 보완 최대 1 · 출제 1 · 문항 보완 최대 3 · 원본 대조 포기 시 단계마다 자동 재실행 1. 예상 1~1.5시간.</p>}
      <p>{privatePilot?'검증을 통과하면 우선 내 계정에만 공개됩니다.':'검증을 통과하면 학생에게 바로 공개됩니다.'} 이미 공개된 판이 있는 강의는 요청이 거절됩니다.</p>
    </div>}
    {needsReason&&<label>이어 하기 이유 (실패한 단계는 이유가 있을 때만 다시 돕니다)<input aria-label="이어 하기 이유" value={reason} maxLength={500} onChange={e=>setReason(e.target.value)}/></label>}
    <button className="is-primary" disabled={!loaded&&!error||busy||pending||needsReason&&!reason.trim()||!resumable&&!sourceMode&&(!input.conceptMap.trim()||!input.points.trim())} onClick={()=>{if(!loaded){setError('');setLoadVersion(v=>v+1);}else void send(resumable);}}>{loaded?label:error?'기존 작업 다시 확인':'기존 작업 확인 중…'}</button>
    <p>러너를 켜두세요. {isMapTree(mode)?'개념 지도·출제포인트·대조를 CLI에서 차례로 만듭니다.':mode==='parallel'?'문제은행·개념도·출제포인트를 각각 CLI에서 만듭니다.':'입력한 지도·포인트로 CLI에서 출제합니다.'} 통합·검수·업로드까지 자동으로 이어집니다. 기존 문제와 학습 기록은 보존합니다.</p>
    <details><summary>설정·기존 지도 사용</summary><fieldset disabled={busy||pending||resumable}>
    <label><input type="radio" name="root-generation-mode" checked={mode==='map-tree'} onChange={()=>chooseMode('map-tree')}/>개념 지도·출제포인트부터 (기본)</label>
    <label><input type="radio" name="root-generation-mode" checked={mode==='map-tree-v3'} onChange={()=>chooseMode('map-tree-v3')}/>새 구조 (시범): 문제은행·개념 지도·출제포인트를 따로 뽑고 빈 목표만 추가</label>
    <label><input type="radio" name="root-generation-mode" checked={mode==='parallel'} onChange={()=>chooseMode('parallel')}/>문제은행·개념도·포인트 병렬 (옛 방식)</label>
    <label><input type="checkbox" checked={!sourceMode} onChange={e=>chooseMode(e.target.checked?'provided':'map-tree')}/>기존 Concept map·출제포인트 사용</label>
    {!sourceMode&&<>
    <label>Concept map<textarea aria-label="Concept map 입력" value={input.conceptMap} maxLength={500000} onChange={e=>setInput({...input,conceptMap:e.target.value})}/>
      <input aria-label="Concept map 파일" type="file" accept=".md,.txt,.json" onChange={e=>void upload('conceptMap',e.target.files?.[0])}/></label>
    <label>출제포인트<textarea aria-label="출제포인트 입력" value={input.points} maxLength={500000} onChange={e=>setInput({...input,points:e.target.value})}/>
      <input aria-label="출제포인트 파일" type="file" accept=".md,.txt,.json" onChange={e=>void upload('points',e.target.files?.[0])}/></label>
    </>}
    <label>출제 범위·제외 사항<textarea aria-label="자동출제 범위" value={input.scope} maxLength={10000} onChange={e=>setInput({...input,scope:e.target.value})}/></label>
    <label>시험일 (비워두면 시간표에서 확인)<input type="date" value={input.examDate??''} onChange={e=>setInput({...input,examDate:e.target.value||null})}/></label>
    <label><input type="checkbox" checked={privatePilot} onChange={e=>setPrivate(e.target.checked)}/> 우선 내 계정에서만 확인</label>
    <p>수정은 최대 3회이며 미해결 지적도 보존합니다. 새 판의 학습은 기존 문제은행과 별도로 집계됩니다.</p>
    </fieldset></details>
    {error&&<p role="alert">{error}</p>}
    {job&&<div role="status"><p>{job.published?'게시 완료':job.awaitingWeb?'웹 응답 대기':job.state==='queued'?'러너 대기':job.state==='running'?'출제·검수 진행 중':'작업 중지·실패'} · {job.stage||job.message}</p>
      {job.sources?.length?<p>보낸 자료: {job.sources.map(s=>s.id+' '+s.filename).join(' · ')}</p>:null}
      {job.published?<><Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`}>Main Quiz 열기 →</Link>
        {!job.featureEnabled&&<p>콘텐츠는 저장되었습니다. 현재 Main Quiz 학습 공개 설정은 꺼져 있습니다.</p>}</>:null}</div>}
    {resumable&&<p>같은 입력과 남은 수정 횟수로 이어서 진행합니다. 기존 실패 기록은 보존합니다.</p>}
    {job?.awaitingWeb&&<details><summary>응답 전달 복구</summary><p>자동 회수가 되지 않을 때만 완성된 응답 파일을 전달하세요.</p><label>완성된 웹 응답 JSON 불러오기 (기존 MD 지원)<input type="file" accept=".json,.md" aria-label="웹 응답 파일" disabled={busy} onChange={async e=>{const file=e.target.files?.[0];if(!file)return;setBusy(true);try{await saveRootWebFile(job.id,file);setError('');}catch(err){setError((err as Error).message);}finally{setBusy(false);}}}/></label></details>}
    {job?.report&&<details><summary>생성·검수 결과</summary><p>목표 {job.report.targetCount}개 · 준비된 과제 {job.report.taskCount}개 · {job.report.pipelineVersion==='root-generation/3'
      ?`빈 목표 추가 ${job.report.addRounds}/2회 · 고친 문항 ${job.report.fixCount}개 · 준비 안 된 목표 ${job.report.notReady}개`:`수정 ${job.report.repairRounds}/3회`}</p>
      <ul>{job.report.issues.map((text,i)=><li key={i}>{text}</li>)}{job.report.questionNotes.map((r,i)=><li key={'q'+i}>{r.source} · {r.question_id} · {r.verdict}: {r.note}</li>)}</ul>
      <ul>{job.report.coverage.map(c=><li key={c.point_id}>{c.point_id} · {c.status} · {c.reason}</li>)}</ul></details>}
  </section>;
}
