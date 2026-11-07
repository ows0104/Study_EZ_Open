import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError } from '../api';
import { useAuth } from '../auth';
import { useMe } from '../useMe';
import type { RootAction, RootMapData, RootOverview, RootView } from '../types/rootLearning';
import { useRootStudyWrites } from './useRootStudyWrites';
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

type Catalog={lectures:(RootOverview&{subject:string;runId:string})[]};
export function RootOverviewPanel({lectureKeys}:{lectureKeys?:string[]}) {
  const [rows,setRows]=useState<Catalog['lectures']>([]);
  useEffect(()=>{let live=true;api<Catalog>('/api/root-learning').then(v=>{if(live)setRows(v.lectures??[]);}).catch(()=>{});return()=>{live=false;};},[]);
  const visible=rows.filter(r=>!lectureKeys||lectureKeys.includes(`${r.subject}/${r.runId}`));
  if(!visible.length)return null;
  return <section className="root-card"><h2>Main Quiz · 강의별 목표</h2><p>강의별 학습 목표와 준비 상태를 확인합니다.</p>
    <ul>{visible.map(r=><li key={`${r.subject}/${r.runId}`}><Link to={href(r.subject,r.runId)}>{r.title}</Link>{r.summary&&` · 첫 학습 ${r.summary.learned}/${r.summary.total} · 회상 가능 ${r.summary.recalled} · 중요한 미학습 ${r.summary.importantUnseen}`}</li>)}</ul></section>;
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
  const loadSession=async(id:string)=>setView(await api<RootView>(`/api/root-learning/sessions/${id}`));
  async function refresh(resume=false) {
    const next=await api<RootOverview>(base);setInfo(next);setError('');
    if(resume&&next.sessionId)await loadSession(next.sessionId);
  }
  const writes=useRootStudyWrites(scope,async(result)=>{await loadSession(result.sessionId);await refresh();});
  useEffect(()=>{void refresh(true).catch(e=>setError(e instanceof ApiError&&e.status===404?'아직 공개된 Main Quiz 학습 자료가 없습니다. 기존 문제를 이용하거나 자료 준비를 기다려 주세요.':e.message));},[base]);
  async function act(action:RootAction) {
    if(!view||writes.blocked)return;
    setError('');if(action.kind==='rate')setAdvancing(true);
    try{await writes.run(`/api/root-learning/sessions/${view.sessionId}/events`,{version:view.version,...action});}
    finally{setAdvancing(false);}
  }
  async function showMap() {
    if(writes.blocked)return;
    if(!view){setMapRequested(true);await writes.run(base+'/sessions',{});return;}
    await act({kind:'map'});
    try{setMap(await api<RootMapData>(`/api/root-learning/sessions/${view.sessionId}/map`));setTab('map');}
    catch(e){setError((e as Error).message);}
  }
  useEffect(()=>{if(mapRequested&&view&&!writes.blocked){setMapRequested(false);void showMap();}},[mapRequested,view,writes.blocked]);
  useEffect(()=>{document.title='Main-Quiz · Study_EZ';},[]);
  async function reload() {
    if(view)await loadSession(view.sessionId);
    await refresh();
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
  return <main className="root-learning main-quiz-learning"><div className="main-quiz-heading"><Link to={lectureHref({subject,runId})}>← 강의로</Link>
    {!view&&<Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}?legacy=1`}>기존 문제·기록</Link>}</div>
    {!view&&<h1>Main-Quiz</h1>}
    {(error||writes.error||writes.pending&&!writes.busy||writes.conflicts.some(r=>!r.acknowledged))&&<div role="alert" className="notice is-error">{error||writes.error||'이전에 저장 확인을 받지 못한 요청 또는 충돌 응답이 있습니다.'}
      {writes.pending&&<button disabled={writes.busy} onClick={()=>void writes.retry()}>같은 요청 다시 저장</button>}
      {writes.conflicts.some(r=>!r.acknowledged)&&<button disabled={writes.busy} onClick={()=>void writes.acknowledge(reload)}>보관 응답 확인 후 서버 기록 불러오기</button>}
    </div>}
    {writes.conflicts.length>0&&<details><summary>보존된 충돌 응답 {writes.conflicts.length}개</summary>{writes.conflicts.map(r=><pre key={r.requestId}>{typeof r.body.response==='string'?r.body.response:JSON.stringify(r.body)}</pre>)}</details>}
    {notice&&<p role="status">{notice}</p>}
    {writes.busy&&<p className="bank-note main-quiz-save-status" role="status">저장 중…</p>}
    {view?<>
      {view.finished&&writes.blocked?<p role="status">마지막 저장과 미확인 요청을 확인 중입니다. 완료 현황은 확인 뒤 표시합니다.</p>:tab==='map'&&map?<><button className="main-quiz-back" onClick={()=>setTab('learn')}>← 문제로 돌아가기</button><RootMap map={map} summary={view.summary} position={`문항 ${Math.min(view.position+1,view.count)}/${view.count}`}/></>:
        <RootSolve view={view} scope={scope} disabled={writes.blocked} advancing={advancing} onAction={a=>void act(a)} onError={setError} onMap={()=>void showMap()}
          onToday={()=>{setView(null);setMap(null);setTab('learn');void refresh().catch(e=>setError(e.message));}}/>}
      {view.blocked?.includes('학습일')&&<button disabled={writes.blocked} onClick={()=>{setView(null);void refresh().catch(e=>setError(e.message));}}>오늘 학습 다시 계획</button>}
    </>:info?<RootToday info={info} disabled={writes.blocked} onStart={()=>void writes.run(base+'/sessions',{})} onMap={()=>void showMap()}/>:!error&&<p>학습 범위 확인 중…</p>}
    {!view&&me?.isAdmin&&<details><summary>Main Quiz 만들기</summary><RootGenerationPanel subject={subject} runId={runId} onPublished={()=>{void refresh().catch(e=>setError(e.message));void adminVersions();}}/></details>}
    {!view&&me?.isAdmin&&<details><summary>Main Quiz 자료·공개 관리</summary><p>검토 묶음·원본 문항·채택 목표·방향별 과제를 포함한 새 판을 등록합니다. 기존 기록과 은행은 보존됩니다.</p>
      <input type="file" accept="application/json,.json" aria-label="Main Quiz 자료" onChange={async e=>{setCandidate(null);const file=e.target.files?.[0];if(!file)return;if(file.size>5_000_000){setError('5MB 이하의 자료를 선택하세요.');return;}try{const text=await file.text();setRaw(text);const value=JSON.parse(text);if(value.schema_version!=='roots/1')throw new Error('Main Quiz 자료 형식을 확인하세요.');setCandidate(value);}catch(err){setError((err as Error).message);}}}/>
      {candidate&&<><details><summary>등록할 내용 검토</summary><pre>{raw}</pre></details><button disabled={managing||writes.blocked} onClick={()=>void register()}>새 판 비공개 등록</button></>}
      <p><label><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/>목표·답·출처·미준비 범위를 검토했습니다</label></p>
      <p><label><input type="checkbox" checked={privatePilot} onChange={e=>setPrivatePilot(e.target.checked)}/>내 계정에서만 시범 사용</label></p>
      {versions.map(v=><p key={v.revision}>{v.title} · {v.revision} <button disabled={managing||writes.blocked||!reviewed} onClick={()=>void publish(v.revision,true)}>{privatePilot?'내 계정에 활성화':'승인된 학생에게 활성화'}</button> <button disabled={managing||writes.blocked} onClick={()=>void publish(v.revision,false)}>사용 중지</button></p>)}
    </details>}
  </main>;
}
