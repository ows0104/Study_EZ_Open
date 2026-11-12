import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api';
import { useAuth } from '../auth';
import { useMe } from '../useMe';
import type { RootAction, RootMapData, RootOverview, RootTierName, RootView } from '../types/rootLearning';
import { useRootStudyWrites } from './useRootStudyWrites';
import { useRootFrames } from './useRootFrames';
import { RootToday } from './RootToday';
import { RootMap } from './RootMap';
import { RootSolve } from './RootSolve';
import { RootGenerationPanel } from './RootGenerationPanel';
import { useBankLink } from './bankBridge';
import './roots.css';
import './main-quiz.css';
import { lectureHref } from '../links';

const href=(subject:string,runId:string)=>`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`;
const endpoint=(subject:string,runId:string)=>`/api/root-learning/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`;

export function RootEntry({subject,runId}:{subject:string;runId:string}) {
  const [info,setInfo]=useState<RootOverview|null>(null);
  const admin=useMe()?.isAdmin;
  useEffect(()=>{let live=true;api<RootOverview>(endpoint(subject,runId)).then(v=>{if(live)setInfo(v);}).catch(()=>{});return()=>{live=false;};},[subject,runId]);
  if(!info&&!admin)return null;
  return <p className="root-entry"><Link to={href(subject,runId)}>Main Quiz · 학습 현황과 오늘 추천 →</Link>
    {info?.summary&&<span> 첫 학습 {info.summary.learned}/{info.summary.total} · 회상 가능 {info.summary.recalled} · 준비 전 {info.summary.unready}</span>}</p>;
}

export function RootLearningPage() {
  useBankLink();
  const {subject='',runId=''}=useParams();
  const {session}=useAuth();
  const account=session?.user.id??session?.user.email??'';
  return <Learning key={JSON.stringify([account,subject,runId])} account={account} subject={subject} runId={runId}/>;
}

function Learning({subject,runId,account}:{subject:string;runId:string;account:string}) {
  const base=endpoint(subject,runId);
  const scope=JSON.stringify([account,subject,runId]);
  const me=useMe();
  const [info,setInfo]=useState<RootOverview|null>(null);
  const [view,setView]=useState<RootView|null>(null);
  const [map,setMap]=useState<RootMapData|null>(null);
  const [error,setError]=useState('');
  const [tab,setTab]=useState<'learn'|'map'>('learn');
  const [advancing,setAdvancing]=useState(false);
  const [mapRequested,setMapRequested]=useState(false);
  const viewRef=useRef(view);viewRef.current=view;
  // Views before each reveal/rating/skip of this session, so every Z draws at once (2026-11-11: unlimited, full undo).
  const undoSnapshots=useRef<RootView[]>([]);
  // stale: only replace the screen if no newer action was drawn ahead of the server meanwhile.
  const loadSession=async(id:string,stale=false)=>{
    const next=await api<RootView>(`/api/root-learning/sessions/${id}`);
    if(stale&&viewRef.current&&viewRef.current.version!==next.version)return;
    undoSnapshots.current=[];viewRef.current=next;setView(next);
  };
  // Resuming an open session draws the question first; the start screen would only flash in between.
  async function refresh(resume=false) {
    const next=await api<RootOverview>(base);
    if(resume&&next.sessionId)await loadSession(next.sessionId);
    setInfo(next);setError('');
    return next;
  }
  const writes=useRootStudyWrites(scope);
  const frames=useRootFrames(view?.sessionId);
  const {ensure,forget}=frames;
  useEffect(()=>{if(view&&!view.finished)ensure(view.position,view.count);},[view?.sessionId,view?.position,view?.count,view?.finished,ensure]);
  // 강의 목록의 「▶」(?start=1): 진행 중 회차는 위에서 이어 풀고, 없으면 오늘 계획으로 바로 회차를 연다. 한 번만.
  const [search,setSearch]=useSearchParams();
  const autoStart=useRef(search.get('start')==='1');
  useEffect(()=>{void refresh(true).then(next=>{
    if(!autoStart.current)return;
    autoStart.current=false;
    setSearch(old=>{const kept=new URLSearchParams(old);kept.delete('start');return kept;},{replace:true});
    if(!viewRef.current&&next.plan?.tasks.length)void begin();
  }).catch(e=>setError(e instanceof ApiError&&e.status===404?'아직 공개된 Main Quiz 학습 자료가 없습니다. 기존 문제를 이용하거나 자료 준비를 기다려 주세요.':e.message));},[base]);
  /** What the server will show once this event is stored, drawn from prepared frames. null: wait for it. */
  function predict(current:RootView,action:RootAction):RootView|null {
    const version=current.version+1;
    if(action.kind==='reveal') {
      const frame=frames.get(current.position);
      if(!current.task||current.task.answer||!frame?.task||frame.taskId!==current.task.id)return null;
      return {...current,version,canUndo:true,task:{...current.task,answer:frame.task.answer,attempted:!!action.attempted,
        response:action.response??'',helped:current.task.helped||!!action.helped||current.mapSeen}};
    }
    if(action.kind==='rate'||action.kind==='skip') {
      const position=current.position+1;
      const moved={...current,version,position,canUndo:true,blocked:null};
      if(position>=current.count)return {...moved,finished:true,task:null};
      const frame=frames.get(position);
      // 막힌 과제(제외 등)는 서버가 건너뛸 수 있다 — 서버 기록을 받아 그린다.
      if(!frame||frame.blocked)return null;
      return {...moved,blocked:frame.blocked,task:frame.task?{id:frame.task.id,question:frame.task.question,answer:null,response:null,
        attempted:null,helped:current.mapSeen||frame.task.helped}:null};
    }
    if(action.kind==='undo') {
      const before=undoSnapshots.current.at(-1);
      if(!current.canUndo||!before||before.sessionId!==current.sessionId)return null;
      return {...before,version,mapSeen:current.mapSeen,summary:current.summary};
    }
    return null;
  }
  function act(action:RootAction) {
    const current=viewRef.current;
    if(!current||writes.blocked||advancing)return;
    setError('');
    const confirmed=writes.run(`/api/root-learning/sessions/${current.sessionId}/events`,{version:current.version,...action});
    if(!confirmed)return;
    const next=predict(current,action);
    if(next) {
      if(action.kind==='undo')undoSnapshots.current=undoSnapshots.current.slice(0,-1);
      else if(action.kind!=='map')undoSnapshots.current=[...undoSnapshots.current,current];
      viewRef.current=next;setView(next);
      // The finished screen shows the server's own summary once every event is stored.
      if(next.finished)void confirmed.then(r=>Promise.all([loadSession(r.sessionId,true),refresh()])).catch(()=>{});
      return;
    }
    // 제외: 미리 받은 뒤 과제의 막힘 여부가 바뀐다. 다시 받고, Z가 이 화면으로 돌아오게 둔다.
    if(action.kind==='exclude'){forget();undoSnapshots.current=[...undoSnapshots.current,current];}
    // No prepared frame yet: confirm, then read the session (the former path).
    setAdvancing(true);
    void confirmed.then(r=>loadSession(r.sessionId)).catch(e=>{if(!(e instanceof ApiError))setError((e as Error).message);})
      .finally(()=>setAdvancing(false));
  }
  async function begin() {
    const started=writes.run(base+'/sessions',{});
    if(!started)return;
    setAdvancing(true);
    try{const r=await started;await Promise.all([loadSession(r.sessionId),refresh()]);}
    catch(e){if(!(e instanceof ApiError))setError((e as Error).message);}
    finally{setAdvancing(false);}
  }
  // 오늘 학습 중요도 필터(2026-11-12): chips change at once; the server's overview (re-planned) replaces it.
  const focusSeq=useRef(0);
  // Start waits for the newest choice: the server plans from what it has stored.
  const [focusing,setFocusing]=useState(false);
  async function changeFocus(tiers:RootTierName[]) {
    const current=info;
    if(!current?.focus)return;
    const seq=++focusSeq.current;
    setInfo({...current,focus:{...current.focus,tiers}});setFocusing(true);
    try{
      const next=await api<RootOverview>(base+'/focus',{method:'PUT',body:JSON.stringify({requestId:crypto.randomUUID(),tiers})});
      if(seq===focusSeq.current)setInfo(next);
    }catch(e){if(seq===focusSeq.current){setInfo(current);setError((e as Error).message);}}
    finally{if(seq===focusSeq.current)setFocusing(false);}
  }
  // The map tab is chosen at once: from the start screen the session it needs is opened underneath,
  // and the question screen is never drawn on the way (2026-11-09).
  async function showMap() {
    if(writes.blocked||advancing)return;
    setTab('map');
    const current=viewRef.current;
    if(!current){setMapRequested(true);await begin();if(!viewRef.current){setMapRequested(false);setTab('learn');}return;}
    const confirmed=writes.run(`/api/root-learning/sessions/${current.sessionId}/events`,{version:current.version,kind:'map'});
    if(!confirmed){setTab('learn');return;}
    setAdvancing(true);
    let shown=false;
    try{
      const r=await confirmed;
      const [data]=await Promise.all([api<RootMapData>(`/api/root-learning/sessions/${r.sessionId}/map`),loadSession(r.sessionId)]);
      setMap(data);shown=true;
    }catch(e){if(!(e instanceof ApiError&&e.status===409))setError((e as Error).message);}
    finally{setAdvancing(false);if(!shown)setTab('learn');}
  }
  useEffect(()=>{if(mapRequested&&view&&!writes.blocked&&!advancing){setMapRequested(false);void showMap();}},[mapRequested,view,writes.blocked,advancing]);
  useEffect(()=>{document.title='Main-Quiz · Study_EZ';},[]);
  async function reload() {
    if(view)await loadSession(view.sessionId);
    await refresh();
  }
  async function retry() {
    if(await writes.retry())await refresh(true).catch(e=>setError((e as Error).message));
  }
  const [versions,setVersions]=useState<{revision:string;title:string;reviewed:boolean}[]>([]);
  const [candidate,setCandidate]=useState<Record<string,unknown>|null>(null);
  const [raw,setRaw]=useState('');
  const [reviewed,setReviewed]=useState(false);
  const [privatePilot,setPrivatePilot]=useState(true);
  const [managing,setManaging]=useState(false);
  const [notice,setNotice]=useState('');
  async function adminVersions(){const data=await api<{versions:typeof versions}>(base.replace('/api/','/api/admin/'));setVersions(data.versions);}
  useEffect(()=>{if(me?.isAdmin)void adminVersions().catch(e=>setError(e.message));},[me?.isAdmin,base]);
  async function register(){if(!candidate)return;setManaging(true);try{await api(base.replace('/api/','/api/admin/'),{method:'POST',body:JSON.stringify(candidate)});setNotice('새 콘텐츠 판을 비공개로 보관했습니다. 내용 검토와 적용 범위를 확인한 뒤 활성화하세요.');await adminVersions();}catch(e){setError((e as Error).message);}finally{setManaging(false);}}
  async function publish(revision:string,enabled:boolean){setManaging(true);try{await api(base.replace('/api/','/api/admin/')+'/publication',{method:'PUT',body:JSON.stringify({revision,reviewed,enabled,allowedUsers:privatePilot?[me!.id]:[]})});setNotice(enabled?'선택한 범위에 활성화했습니다. 서버 전체 기능 설정이 꺼져 있으면 학습 진입은 열리지 않습니다.':'신규 진입과 쓰기를 중지했습니다. 기록은 보존됩니다.');await adminVersions();await refresh();}catch(e){setError((e as Error).message);}finally{setManaging(false);}}
  // 관리 도구는 학생 화면에 없고, 관리자에게도 한 접힘 안에 둔다.
  const adminTools=me?.isAdmin?<details className="mq-more mq-admin"><summary>관리자</summary>
    <p><Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}?legacy=1`}>기존 문제·기록 보기</Link>{info&&<span className="bank-note"> · 자료 판 {info.revision}</span>}</p>
    <details><summary>Main Quiz 만들기</summary><RootGenerationPanel subject={subject} runId={runId} onPublished={()=>{void refresh().catch(e=>setError(e.message));void adminVersions();}}/></details>
    <details><summary>Main Quiz 자료·공개 관리</summary><p>검토 묶음·원본 문항·채택 목표·방향별 과제를 포함한 새 판을 등록합니다. 기존 기록과 은행은 보존됩니다.</p>
      <input type="file" accept="application/json,.json" aria-label="Main Quiz 자료" onChange={async e=>{setCandidate(null);const file=e.target.files?.[0];if(!file)return;if(file.size>5_000_000){setError('5MB 이하의 자료를 선택하세요.');return;}try{const text=await file.text();setRaw(text);const value=JSON.parse(text);if(value.schema_version!=='roots/1')throw new Error('Main Quiz 자료 형식을 확인하세요.');setCandidate(value);}catch(err){setError((err as Error).message);}}}/>
      {candidate&&<><details><summary>등록할 내용 검토</summary><pre>{raw}</pre></details><button disabled={managing||writes.blocked} onClick={()=>void register()}>새 판 비공개 등록</button></>}
      <p><label><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/>목표·답·출처·미준비 범위를 검토했습니다</label></p>
      <p><label><input type="checkbox" checked={privatePilot} onChange={e=>setPrivatePilot(e.target.checked)}/>내 계정에서만 시범 사용</label></p>
      {versions.map(v=><p key={v.revision}>{v.title} · {v.revision} <button disabled={managing||writes.blocked||!reviewed} onClick={()=>void publish(v.revision,true)}>{privatePilot?'내 계정에 활성화':'승인된 학생에게 활성화'}</button> <button disabled={managing||writes.blocked} onClick={()=>void publish(v.revision,false)}>사용 중지</button></p>)}
    </details>
  </details>:null;
  return <main className={`root-learning main-quiz-learning${view?'':' is-start'}`}>
    {(error||writes.error||writes.pending&&!writes.busy||writes.conflicts.some(r=>!r.acknowledged))&&<div role="alert" className="notice is-error">{error||writes.error||'이전에 저장 확인을 받지 못한 요청 또는 충돌 응답이 있습니다.'}
      {writes.pending&&<button disabled={writes.busy} onClick={()=>void retry()}>같은 요청 다시 저장</button>}
      {writes.conflicts.some(r=>!r.acknowledged)&&<button disabled={writes.busy} onClick={()=>void writes.acknowledge(reload)}>보관 응답 확인 후 서버 기록 불러오기</button>}
    </div>}
    {writes.conflicts.length>0&&<details><summary>보존된 충돌 응답 {writes.conflicts.length}개</summary>{writes.conflicts.map(r=><pre key={r.requestId}>{typeof r.body.response==='string'?r.body.response:JSON.stringify(r.body)}</pre>)}</details>}
    {notice&&<p role="status">{notice}</p>}
    {writes.slow&&<p className="bank-note main-quiz-save-status" role="status">저장 확인 중…</p>}
    {view?<>
      {view.finished&&(writes.blocked||writes.queued>0)?<p role="status">마지막 저장과 미확인 요청을 확인 중입니다. 완료 현황은 확인 뒤 표시합니다.</p>:tab==='map'?map?<RootMap map={map} summary={view.summary} title={info?.title} onBack={()=>setTab('learn')}/>:<p className="notice" role="status">개념 지도를 불러오는 중…</p>:
        <RootSolve view={view} title={info?.title} scope={scope} disabled={writes.blocked}
          editPath={qid=>`${base}/questions/${encodeURIComponent(qid)}/personal`}
          onEdited={result=>{forget();const current=viewRef.current;if(!current?.task)return;
            const next={...current,task:{...current.task,question:result.question,answer:current.task.answer?result.answer:null}};
            viewRef.current=next;setView(next);if(!current.finished)ensure(current.position,current.count);}}
          tierPath={qid=>`${base}/questions/${encodeURIComponent(qid)}/tier`}
          onTier={question=>{forget();const current=viewRef.current;if(!current?.task||current.task.question.question_id!==question.question_id)return;
            const next={...current,task:{...current.task,question}};
            viewRef.current=next;setView(next);if(!current.finished)ensure(current.position,current.count);}} advancing={advancing} onAction={act} onError={setError} onMap={()=>void showMap()}
          onToday={()=>{setView(null);setMap(null);setTab('learn');void refresh().catch(e=>setError(e.message));}}/>}
      {view.blocked?.includes('학습일')&&<button disabled={writes.blocked} onClick={()=>{setView(null);void refresh().catch(e=>setError(e.message));}}>오늘 학습 다시 계획</button>}
    </>:info?<RootToday info={info} disabled={writes.blocked||advancing} starting={advancing} onStart={()=>{if(!focusing)void begin();}} onMap={()=>void showMap()}
      onFocus={tiers=>void changeFocus(tiers)} focusing={focusing} lectureLink={lectureHref({subject,runId})} admin={adminTools}/>:!error&&<><p className="notice" role="status">Main-Quiz를 불러오는 중…</p>{adminTools}</>}
  </main>;
}
