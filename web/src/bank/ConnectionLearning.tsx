import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError } from '../api';
import { useAuth } from '../auth';
import type { Bundle } from '../connection-pilot/data';
import './connections.css';
import { connectionRecovery, type Mark, type Write } from './connectionRecovery';

type Step = { question: string; answers?: string[]; explanation?: string; response?: string; marks?: Mark[] };
type View = { revision: string; title: string; scope: string; version: number; count: number;
  state: { current: number; reviewSeen: boolean; entries: Record<string, Partial<Record<'root' | 'follow', { response: string; marks: Mark[] }>>> };
  task: { id: string; root: Step; follow?: Step }; map: Bundle[] | null };
type Version = { revision: string; title: string; scope: string; count: number; published: boolean };
type Overview = { canManage: boolean; versions: Version[] };

export function ConnectionEntry({ subject, runId }: {subject: string; runId: string}) {
  return <p className="bank-note"><Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/connections`}>연결부터 학습하기 · 개념 지도와 학습 경로 →</Link></p>;
}

export function ConnectionLearningPage() {
  const {subject = '', runId = ''} = useParams();
  const {session} = useAuth();
  const account = session?.user.id ?? session?.user.email ?? '';
  return <Learning key={`${account}/${subject}/${runId}`} account={account} subject={subject} runId={runId}/>;
}

function Learning({subject, runId, account}: {subject: string; runId: string; account: string}) {
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/connections`;
  const recovery = (revision: string) => connectionRecovery(localStorage, account, subject, runId, revision);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Write | null>(null);
  const [conflict, setConflict] = useState(false);
  const [conflicts, setConflicts] = useState<Write[]>([]);
  const [tab, setTab] = useState<'learn' | 'map' | 'record'>('learn');
  const [drafts, setDrafts] = useState<Record<string,string>>({});
  const [upload, setUpload] = useState('');
  const [candidate, setCandidate] = useState<{title:string; revision:string; scope:string; bundles:Bundle[]} | null>(null);
  const [message, setMessage] = useState('');
  const refresh = () => api<Overview>(base).then(setOverview).catch(e => setError(e.message));
  useEffect(() => { void refresh(); }, [base]);
  function restore(next: View) {
    const store = recovery(next.revision);
    const saved = store.read();
    const root = store.draft(next.task.id, 'root');
    const follow = store.draft(next.task.id, 'follow');
    setDrafts(d => ({...d, [`${next.revision}/${next.task.id}/root`]: root, [`${next.revision}/${next.task.id}/follow`]: follow}));
    setPending(saved.find(s => !s.conflict)?.payload ?? null);
    setConflicts(saved.filter(s => s.conflict).map(s => s.payload));
    setView(next);
    return saved.some(s => !s.conflict);
  }
  async function open(revision: string) {
    setBusy(true); setError('');
    try {
      const hasPending = restore(await api<View>(`${base}/${revision}`));
      setConflict(false);
      if (hasPending) setError('이전에 저장 확인을 받지 못한 요청이 있습니다. 같은 요청을 다시 저장하세요.');
    }
    catch(e) { setError((e as Error).message); } finally {setBusy(false);}
  }
  async function send(payload: Write) {
    if (!view) return;
    setBusy(true); setPending(payload); setError('');
    try {
      const store = recovery(view.revision);
      store.save(payload);
      await api<View>(`${base}/${view.revision}/actions`, {method:'POST',body:JSON.stringify(payload)});
      const latest = await api<View>(`${base}/${view.revision}`);
      store.confirm(payload);
      const hasPending = restore(latest);
      setConflict(false);
      if (hasPending) setError('다른 미확인 요청이 남아 있습니다. 같은 요청을 다시 저장하세요.');
    }
    catch(e) {
      const stale = e instanceof ApiError && e.status === 409;
      setConflict(stale);
      if (stale) {
        try { const store = recovery(view.revision); store.save(payload, true); setConflicts(store.read().filter(s => s.conflict).map(s => s.payload)); }
        catch { /* The pending request remains in memory if local storage fails. */ }
      }
      setError((e as Error).message);
    }
    finally {setBusy(false);}
  }
  function draft(key: string, step: 'root' | 'follow', text: string) {
    setDrafts(d => ({...d, [key]: text}));
    if (!view) return;
    try { recovery(view.revision).saveDraft(view.task.id, step, text); }
    catch { setError('이 브라우저에 입력을 보관하지 못했습니다. 화면을 닫기 전에 응답을 복사하세요.'); }
  }
  function action(kind: Write['kind'], options: Partial<Write> = {}) {
    if (!view || busy || pending) return;
    void send({requestId:crypto.randomUUID(), version:view.version, kind, index:view.state.current, ...options});
  }
  async function register() {
    if (!candidate) return;
    setBusy(true); setError('');
    try { await api(`/api/admin/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/connections`, {method:'POST',body:JSON.stringify(candidate)}); setMessage('새 판을 비공개로 등록했습니다. 내용을 확인한 뒤 학생 공개를 선택하세요.'); await refresh(); }
    catch(e){setError((e as Error).message);} finally {setBusy(false);}
  }
  async function publication(v: Version) {
    setBusy(true); setError('');
    try {await api(`/api/admin/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/connections/${v.revision}/publication`,{method:'PUT',body:JSON.stringify({published:!v.published})}); await refresh();}
    catch(e){setError((e as Error).message);} finally{setBusy(false);}
  }
  const done = view ? Object.values(view.state.entries).filter(e=>e.root && e.follow).length : 0;
  return <main className="quiz connection-product"><Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`}>← Main-Quiz</Link><h2>연결부터 학습하기</h2>
    <p>먼저 연결을 떠올리고, 답을 확인한 뒤 세부 질문으로 이어갑니다.</p>
    {error && <div role="alert" className="notice is-error">{error}{pending && !conflict && <button disabled={busy} onClick={()=>void send(pending)}>같은 요청 다시 저장</button>}{view && conflict && <button disabled={busy} onClick={()=>void open(view.revision)}>서버 기록 다시 불러오기</button>}<p>서버 확인 전에는 저장이 완료되지 않습니다. 보관된 응답과 충돌 요청은 유지됩니다.</p></div>}
    {!!conflicts.length && <details><summary>충돌로 반영되지 않은 응답 {conflicts.length}개</summary><p>서버 기록을 다시 불러온 뒤 필요한 내용을 확인하세요. 아래 응답은 자동으로 덮어쓰지 않습니다.</p>{conflicts.map(p=><article key={p.requestId}><p>연결 {p.index+1} · {p.step==='follow'?'후속 질문':'첫 질문'} · {p.kind}</p><pre>{p.response || (p.marks ? p.marks.join(', ') : '이동·열람 요청')}</pre></article>)}</details>}
    {message && <p role="status">{message}</p>}
    {!overview ? <p>자료 확인 중…</p> : <>
      {!overview.versions.length && <p>아직 준비된 연결 학습 자료가 없습니다. 기존 Main-Quiz는 계속 이용할 수 있습니다.</p>}
      <div className="connection-versions">{overview.versions.map(v=><div key={v.revision}><button disabled={busy || !!pending} onClick={()=>void open(v.revision)}>{v.title} · {v.count}묶음{!v.published ? ' · 비공개 초안' : ''}</button>{overview.canManage && <button disabled={busy || !!pending} onClick={()=>void publication(v)}>{v.published ? '학생 공개 중지' : '학생에게 공개'}</button>}</div>)}</div>
      {overview.canManage && <details><summary>연결 학습 자료 등록</summary><p>질문·답·연결·근거를 포함한 JSON을 새 판으로 등록합니다. 기존 판과 학습기록은 보존합니다.</p><input type="file" accept="application/json,.json" aria-label="연결 자료 JSON" onChange={async e=>{const f=e.target.files?.[0]; if(!f)return; if(f.size>5_000_000){setError('5MB 이하 파일을 선택하세요.');return;}setCandidate(null);try{const text=await f.text();setUpload(text); const p=JSON.parse(text); if(!p.title || !p.revision || !p.scope || !Array.isArray(p.bundles))throw new Error('title, revision, scope, bundles가 필요합니다.'); setCandidate(p);}catch(err){setError((err as Error).message);}}}/>
        {candidate && <div><h3>{candidate.title}</h3><p>{candidate.scope} · {candidate.bundles.length}묶음 · 판 {candidate.revision}</p><details><summary>등록할 원문 검토</summary><pre>{upload}</pre></details><button disabled={busy || !!pending} onClick={()=>void register()}>이 판을 비공개로 등록</button></div>}</details>}
    </>}
    {view && <section><h3>{view.title}</h3><p>{view.scope}</p><p role="status">{busy ? '서버에 저장 중…' : pending ? '저장 미확인' : '서버 기록 확인됨'} · 두 답 열람 {done}/{view.count}묶음</p>
      <nav aria-label="연결 학습"><button onClick={()=>setTab('learn')}>질문</button><button disabled={busy || !!pending} onClick={()=>{action('map');setTab('map');}}>연결 지도·근거 (답 포함)</button><button onClick={()=>setTab('record')}>학습 기록</button></nav>
      {tab==='learn' && <><p>연결 {view.state.current+1}/{view.count}{view.state.reviewSeen ? ' · 지도 답 노출 있음' : ''}</p>
        {(['root','follow'] as const).map(step=>{const q=view.task[step];if(!q)return null;const key=`${view.revision}/${view.task.id}/${step}`;return <section className="connection-question" key={key}><small>{step==='root'?'먼저 연결 떠올리기':'세부로 이어가기'}</small><h3>{q.question}</h3><textarea aria-label={`${step==='root'?'첫':'후속'} 질문 응답`} readOnly={!!q.answers} value={q.response ?? drafts[key] ?? ''} onChange={e=>draft(key,step,e.target.value)} placeholder="떠오르는 내용을 적거나, 모르면 설명으로 넘어가세요." maxLength={10000}/>
          {!q.answers ? <button disabled={busy || !!pending} onClick={()=>action('reveal',{step,response:drafts[key]??''})}>답·설명 확인</button> : <><p>{q.explanation}</p>{q.answers.map((answer,i)=><label className="connection-answer" key={i}><span>{answer}</span><select aria-label={`${step} 답 ${i+1} 자기확인`} disabled={busy || !!pending} value={q.marks?.[i]??''} onChange={e=>action('rate',{step,marks:q.answers!.map((_,j)=>i===j?e.target.value as Mark:q.marks?.[j]??'')})}><option value="">미확인</option><option value="recalled">떠올렸음</option><option value="partial">일부만</option><option value="learned">새로 배움</option></select></label>)}</>}
        </section>})}
        <div className="connection-nav"><button disabled={busy || !!pending || view.state.current===0} onClick={()=>action('select',{index:view.state.current-1})}>이전</button><button disabled={busy || !!pending || view.state.current+1===view.count} onClick={()=>action('select',{index:view.state.current+1})}>다음 연결</button></div></>}
      {tab==='map' && (view.map ? view.map.map((b,i)=><article className="connection-question" key={b.id}><h3>{b.title}</h3><p>{b.connection}</p><p>형태: {b.type} · 구조: {b.structure} · 학습 역할: {b.role}</p><dl><dt>이해의 뼈대</dt><dd>{b.structural}</dd><dt>시험 근거</dt><dd>{b.exam}</dd><dt>임상 근거</dt><dd>{b.clinical}</dd><dt>남은 질문</dt><dd>{b.gap}</dd><dt>출처</dt><dd>{b.sources} · {b.original}</dd></dl><button disabled={busy || !!pending} onClick={()=>{action('select',{index:i});setTab('learn');}}>이 연결 학습</button></article>) : <p>지도 노출 기록이 저장되면 지도를 표시합니다.</p>)}
      {tab==='record' && <><p>열람·응답 시도·항목별 자기확인을 구별합니다. 자기확인은 독립 회상 인증이나 강의 전체 숙련도가 아닙니다.</p>{Object.entries(view.state.entries).map(([id,e])=><article key={id}><h4>{id}</h4>{(['root','follow'] as const).map(step=><p key={step}>{step==='root'?'첫 질문':'후속 질문'}: {!e[step]?'미열람':`${e[step]!.response.trim()?'응답 후 확인':'답만 확인'} · 떠올렸음 ${e[step]!.marks.filter(m=>m==='recalled').length} · 일부만/새로 배움 ${e[step]!.marks.filter(m=>m==='partial'||m==='learned').length}`}</p>)}</article>)}</>}
    </section>}
  </main>;
}
