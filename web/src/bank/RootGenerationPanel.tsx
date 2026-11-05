import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import './roots.css';
import { sendRootWeb,saveRootWebFile } from './rootWeb';
import { extensionCompatible,extensionInputMinimum } from '../bridge/previewBridge';

type Input={conceptMap:string;points:string;scope:string;examDate:string|null;inputMode?:'provided'|'source'};
type Generation={id:string;requestId?:string;state:string;stage:string;message:string;published:boolean;revision:string;
  authoring?:string;awaitingWeb?:boolean;dispatched?:boolean;
  privatePilot:boolean;featureEnabled:boolean;input:Input;report?:{repairRounds:number;taskCount:number;targetCount:number;
    issues:string[];questionNotes:{source:string;question_id:string;verdict:string;note:string}[];
    coverage:{point_id:string;status:string;reason:string}[]}|null};
export function RootGenerationPanel({subject,runId,onPublished}:{subject:string;runId:string;onPublished?:()=>void}) {
  const base=`/api/admin/root-learning/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/generation`;
  const [input,setInput]=useState<Input>({conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'});
  const [privatePilot,setPrivate]=useState(true);
  const [job,setJob]=useState<Generation|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{let live=true;api<{generation:Generation|null}>(base).then(({generation:g})=>{
    if(live&&g){setJob(g);setInput(g.input);setPrivate(g.privatePilot);}
  }).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[base]);
  const pending=!!job&&(['queued','running'].includes(job.state)||!!job.awaitingWeb&&!['canceled','failed'].includes(job.state));
  useEffect(()=>{
    if(!pending)return;
    let live=true;
    const timer=setInterval(()=>api<{generation:Generation|null}>(base).then(({generation:g})=>{
      if(live){setJob(g);if(g?.published)onPublished?.();}
    }).catch(e=>{if(live)setError(e.message);}),3000);
    return()=>{live=false;clearInterval(timer);};
  },[base,pending,onPublished]);
  async function send(resume=false){
    setBusy(true);setError('');
    try{
      if(!resume&&!extensionCompatible(extensionInputMinimum('bank',true)))throw new Error('최신 Study EZ 브리지를 연결한 뒤 자동전송을 이용하세요.');
      const data=resume&&job?job.input:input;
      const mode=data.inputMode??'provided';
      const result=await api<{generation:Generation}>(base,{method:'POST',body:JSON.stringify({
        ...data,conceptMap:mode==='source'?'':data.conceptMap,points:mode==='source'?'':data.points,inputMode:mode,
        requestId:resume&&job?.requestId?job.requestId:crypto.randomUUID(),privatePilot:resume&&job?job.privatePilot:privatePilot,resume,authoring:resume&&job?job.authoring??'cli':'web'})});
      setJob(result.generation);if(result.generation.published)onPublished?.();
      if(!resume&&result.generation.awaitingWeb)await sendRootWeb(result.generation.id);
    }catch(e){setError(e instanceof Error?e.message:'요청을 저장하지 못했습니다.');}finally{setBusy(false);}
  }
  async function upload(field:'conceptMap'|'points',file?:File){
    if(!file)return;
    if(file.size>1500000){setError('텍스트 파일은 1.5MB 이하로 선택하세요.');return;}
    try{const value=await file.text();setInput(old=>({...old,[field]:value}));setError('');}
    catch{setError('파일을 읽지 못했습니다. 내용을 직접 붙여 넣으세요.');}
  }
  const sourceMode=input.inputMode==='source';
  return <section className="root-card root-generation" aria-label="Concept map 자동출제"><h3>뿌리 학습 자동 생성</h3>
    <p>올해 필기·족보를 자동으로 첨부해 전송합니다. 문항 회수 후 원본만으로 지도·출제포인트를 따로 만들고, 대조·독립 정답 검수와 필요한 수정을 거쳐 게시합니다.</p>
    <button disabled={busy||pending||!sourceMode&&(!input.conceptMap.trim()||!input.points.trim())} onClick={()=>void send()}>뿌리 학습 자동전송</button>
    <p>러너가 켜져 있으면 회수·검수·게시까지 이어집니다. 기본은 내 계정 시범 공개이며, 기존 문제와 학습 기록은 보존합니다.</p>
    <details><summary>설정·기존 지도 사용</summary>
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
    </details>
    {error&&<p role="alert">{error}</p>}
    {job&&<div role="status"><p>{job.published?'게시 완료':job.awaitingWeb?'웹 응답 대기':job.state==='queued'?'러너 대기':job.state==='running'?'출제·검수 진행 중':'작업 중지·실패'} · {job.stage||job.message}</p>
      {job.published?<><Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/roots`}>생성된 뿌리 학습 열기 →</Link>
        {!job.featureEnabled&&<p>콘텐츠는 저장되었습니다. 현재 전체 뿌리 학습 공개 설정은 꺼져 있습니다.</p>}</>:
        !pending&&!job.awaitingWeb&&<button disabled={busy} onClick={()=>void send(true)}>같은 입력·남은 횟수로 재개</button>}</div>}
    {job?.awaitingWeb&&<label>완성된 웹 응답 MD 불러오기<input type="file" accept=".md" aria-label="웹 응답 MD" disabled={busy} onChange={async e=>{const file=e.target.files?.[0];if(!file)return;setBusy(true);try{await saveRootWebFile(job.id,file);setError('');}catch(err){setError((err as Error).message);}finally{setBusy(false);}}}/></label>}
    {job?.report&&<details><summary>생성·검수 결과</summary><p>목표 {job.report.targetCount}개 · 준비된 과제 {job.report.taskCount}개 · 수정 {job.report.repairRounds}/3회</p>
      <ul>{job.report.issues.map((text,i)=><li key={i}>{text}</li>)}{job.report.questionNotes.map((r,i)=><li key={'q'+i}>{r.source} · {r.question_id} · {r.verdict}: {r.note}</li>)}</ul>
      <ul>{job.report.coverage.map(c=><li key={c.point_id}>{c.point_id} · {c.status} · {c.reason}</li>)}</ul></details>}
  </section>;
}
