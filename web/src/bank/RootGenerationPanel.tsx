import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import './roots.css';
import { saveRootWebFile } from './rootWeb';
import { pollAfterSettled } from './pollChain';

type Input={conceptMap:string;points:string;scope:string;examDate:string|null;inputMode?:'provided'|'source'};
type Generation={id:string;requestId?:string;state:string;stage:string;message:string;published:boolean;revision:string;
  authoring?:string;parallelAuthoring?:boolean;awaitingWeb?:boolean;dispatched?:boolean;
  privatePilot:boolean;featureEnabled:boolean;input:Input;report?:{repairRounds:number;taskCount:number;targetCount:number;
    issues:string[];questionNotes:{source:string;question_id:string;verdict:string;note:string}[];
    coverage:{point_id:string;status:string;reason:string}[]}|null};
type Props={subject:string;runId:string;onPublished?:()=>void};
export function RootGenerationPanel(props:Props) {
  return <GenerationPanel key={props.subject+'/'+props.runId} {...props}/>;
}
function GenerationPanel({subject,runId,onPublished}:Props) {
  const base=`/api/admin/root-learning/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/generation`;
  const [input,setInput]=useState<Input>({conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'});
  const [privatePilot,setPrivate]=useState(true);
  const [job,setJob]=useState<Generation|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [loaded,setLoaded]=useState(false);
  const sending=useRef(false);
  const [loadVersion,setLoadVersion]=useState(0);
  useEffect(()=>{let live=true;api<{generation:Generation|null}>(base).then(({generation:g})=>{
    if(live){setLoaded(true);if(g){setJob(g);setInput(g.input);setPrivate(g.privatePilot);}}
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
  async function send(resume=false){
    if(sending.current)return;
    sending.current=true;setBusy(true);setError('');
    try{
      const data=resume&&job?job.input:input;
      const mode=data.inputMode??'provided';
      const result=await api<{generation:Generation}>(base,{method:'POST',body:JSON.stringify({
        ...data,conceptMap:mode==='source'?'':data.conceptMap,points:mode==='source'?'':data.points,inputMode:mode,
        requestId:resume&&job?.requestId?job.requestId:crypto.randomUUID(),privatePilot:resume&&job?job.privatePilot:privatePilot,resume,authoring:resume&&job?job.authoring??'cli':'cli',parallelAuthoring:resume&&job?job.parallelAuthoring??false:mode==='source'})});
      setJob(result.generation);if(result.generation.published)onPublished?.();
    }catch(e){setError(e instanceof Error?e.message:'요청을 저장하지 못했습니다.');}finally{sending.current=false;setBusy(false);}
  }
  async function upload(field:'conceptMap'|'points',file?:File){
    if(!file)return;
    if(file.size>1500000){setError('텍스트 파일은 1.5MB 이하로 선택하세요.');return;}
    try{const value=await file.text();setInput(old=>({...old,[field]:value}));setError('');}
    catch{setError('파일을 읽지 못했습니다. 내용을 직접 붙여 넣으세요.');}
  }
  const sourceMode=input.inputMode==='source';
  const resumable=!!job&&!job.published&&!pending&&!job.awaitingWeb;
  const label=busy?'요청 중…':pending?'생성·업로드 진행 중':resumable?'Main Quiz 이어서 만들기':'Main Quiz 만들기';
  return <section className="root-card root-generation" aria-label="Main Quiz 만들기"><h3>Main Quiz 만들기</h3>
    <p>올해 필기·족보로 문제은행을 만들고, 개념도·출제포인트와 통합·검수한 뒤 자동으로 업로드합니다.</p>
    <button className="is-primary" disabled={!loaded&&!error||busy||pending||!resumable&&!sourceMode&&(!input.conceptMap.trim()||!input.points.trim())} onClick={()=>{if(!loaded){setError('');setLoadVersion(v=>v+1);}else void send(resumable);}}>{loaded?label:error?'기존 작업 다시 확인':'기존 작업 확인 중…'}</button>
    <p>러너를 켜두세요. {sourceMode?'문제은행·개념도·출제포인트를 각각 CLI에서 만듭니다.':'입력한 지도·포인트로 CLI에서 출제합니다.'} 통합·검수·업로드까지 자동으로 이어집니다. 기본은 내 계정 시범 공개이며, 기존 문제와 학습 기록은 보존합니다.</p>
    <details><summary>설정·기존 지도 사용</summary><fieldset disabled={busy||pending||resumable}>
    <label><input type="checkbox" checked={!sourceMode} onChange={e=>setInput({...input,inputMode:e.target.checked?'provided':'source'})}/>기존 Concept map·출제포인트 사용</label>
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
      {job.published?<><Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`}>Main Quiz 열기 →</Link>
        {!job.featureEnabled&&<p>콘텐츠는 저장되었습니다. 현재 Main Quiz 학습 공개 설정은 꺼져 있습니다.</p>}</>:null}</div>}
    {resumable&&<p>같은 입력과 남은 수정 횟수로 이어서 진행합니다. 기존 실패 기록은 보존합니다.</p>}
    {job?.awaitingWeb&&<details><summary>응답 전달 복구</summary><p>자동 회수가 되지 않을 때만 완성된 응답 파일을 전달하세요.</p><label>완성된 웹 응답 JSON 불러오기 (기존 MD 지원)<input type="file" accept=".json,.md" aria-label="웹 응답 파일" disabled={busy} onChange={async e=>{const file=e.target.files?.[0];if(!file)return;setBusy(true);try{await saveRootWebFile(job.id,file);setError('');}catch(err){setError((err as Error).message);}finally{setBusy(false);}}}/></label></details>}
    {job?.report&&<details><summary>생성·검수 결과</summary><p>목표 {job.report.targetCount}개 · 준비된 과제 {job.report.taskCount}개 · 수정 {job.report.repairRounds}/3회</p>
      <ul>{job.report.issues.map((text,i)=><li key={i}>{text}</li>)}{job.report.questionNotes.map((r,i)=><li key={'q'+i}>{r.source} · {r.question_id} · {r.verdict}: {r.note}</li>)}</ul>
      <ul>{job.report.coverage.map(c=><li key={c.point_id}>{c.point_id} · {c.status} · {c.reason}</li>)}</ul></details>}
  </section>;
}
