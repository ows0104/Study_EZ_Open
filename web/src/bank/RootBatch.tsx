import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api';
import { useAuth } from '../auth';
import { SlidePreloader } from '../slidePreload';
import type { RootAction, RootFrame, RootOverview, RootView } from '../types/rootLearning';
import { Icon } from '../shell/icons';
import { useRootStudyWrites } from './useRootStudyWrites';
import { warm } from './useRootFrames';
import { RootSolve } from './RootSolve';
import { readQuizMode, saveQuizMode, type QuizMode } from './quizMode';
import { readMix, type MixLecture } from './mixLinks';
import { bankHref } from '../links';
import './roots.css';
import './main-quiz.css';
import './root-batch.css';

/**
 * Main-Quiz 모아풀기(2026-11-18 사용자 「강의 목록형에서 선택해서 섞어서 풀 수 있게」).
 *
 * 서버 회차는 강의 단위 그대로다. 고른 강의마다 기존 회차를 열고, 이 화면이 문항을 번갈아 낸다.
 * 한 강의 안의 순서(선행·슬라이드 흐름)는 서버가 정한 그대로이고, 기록·복습일은 강의별로 쌓인다.
 * 다음 문항은 남은 비율이 가장 큰 강의가 낸다 — 강의들이 비슷한 때에 끝난다.
 * 되돌리기(Z)는 강의를 가리지 않고 방금 한 행동부터 거꾸로 돌린다.
 */

const endpoint=(l:MixLecture)=>`/api/root-learning/lectures/${encodeURIComponent(l.subject)}/${encodeURIComponent(l.runId)}`;
const keyOf=(l:MixLecture)=>`${l.subject}/${l.runId}`;
const sessionPath=(id:string)=>`/api/root-learning/sessions/${encodeURIComponent(id)}`;

type Lane = MixLecture & {key:string; base:string;
  /** 시작 화면: 그 강의의 오늘 현황. */
  info?:RootOverview; left?:number; error?:string;
  /** 풀이 중: 그 강의의 회차. */
  view?:RootView};
/** 화면 전체의 되돌리기 한 칸. before가 있으면 서버 확인 전에 그 화면을 바로 그린다. */
type Step = {key:string; before:RootView|null};

const AHEAD=3, BATCH=4;

/** 강의마다 다음 문항을 미리 받는다(GET …/prepare는 아무것도 기록하지 않는다). useRootFrames의 여러 회차판. */
function useLaneFrames() {
  const store=useRef(new Map<string,Map<number,RootFrame>>());
  const inflight=useRef(new Map<string,Set<number>>());
  const images=useMemo(()=>new SlidePreloader(),[]);
  const ensure=useCallback((sid:string,position:number,count:number)=>{
    const frames=store.current.get(sid)??new Map<number,RootFrame>();store.current.set(sid,frames);
    const busy=inflight.current.get(sid)??new Set<number>();inflight.current.set(sid,busy);
    let start=-1;
    for(let p=position;p<Math.min(position+AHEAD,count);p++)if(!frames.has(p)){start=p;break;}
    if(start<0||[...busy].some(p=>p<=start&&start<p+BATCH))return;
    busy.add(start);
    api<{sessionId:string;frames:RootFrame[]}>(`${sessionPath(sid)}/prepare?start=${start}&count=${BATCH}`)
      .then(result=>{
        if(store.current.get(sid)!==frames)return;
        for(const frame of result.frames)frames.set(frame.position,frame);
        warm(result.frames,images);
      })
      .catch(()=>{}) // 못 받으면 저장 확인 뒤 회차를 읽는다(강의 화면과 같다).
      .finally(()=>busy.delete(start));
  },[images]);
  const get=useCallback((sid:string,position:number)=>store.current.get(sid)?.get(position),[]);
  const forget=useCallback((sid:string)=>{store.current.delete(sid);inflight.current.delete(sid);},[]);
  return {ensure,get,forget};
}

/** 남은 비율이 가장 큰 강의. 같으면 고른 순서. 다 끝났으면 null. */
export function nextLane(lanes:Pick<Lane,'key'|'view'>[]):string|null {
  let best:string|null=null,score=-1;
  for(const lane of lanes) {
    const v=lane.view;
    if(!v||v.finished||!v.count)continue;
    const left=(v.count-Math.min(v.position,v.count))/v.count;
    if(left>score){score=left;best=lane.key;}
  }
  return best;
}

export function RootBatchPage() {
  const [search]=useSearchParams();
  const lectures=useMemo(()=>readMix(search),[search]);
  const {session}=useAuth();
  const account=session?.user.id??session?.user.email??'';
  return <Batch key={JSON.stringify([account,lectures.map(keyOf)])} account={account} lectures={lectures}/>;
}

function Batch({account,lectures}:{account:string;lectures:MixLecture[]}) {
  const scope=JSON.stringify([account,'mix']);
  const navigate=useNavigate();
  const writes=useRootStudyWrites(scope);
  const frames=useLaneFrames();
  // 강의별 상태는 행동마다 바로 읽어야 해서 ref에 두고, 바꿀 때 다시 그린다.
  const lanesRef=useRef<Lane[]>(lectures.map(l=>({...l,key:keyOf(l),base:endpoint(l)})));
  const currentRef=useRef<string|null>(null);
  const stack=useRef<Step[]>([]);
  const [,redraw]=useState(0);
  const [phase,setPhase]=useState<'start'|'solve'>('start');
  const [loading,setLoading]=useState(true);
  const [advancing,setAdvancing]=useState(false);
  const [error,setError]=useState('');
  const [mode,setMode]=useState<QuizMode>(readQuizMode);
  const lanes=lanesRef.current;
  const setLanes=(change:(lanes:Lane[])=>Lane[])=>{lanesRef.current=change(lanesRef.current);redraw(v=>v+1);};
  const patch=(key:string,change:Partial<Lane>)=>setLanes(all=>all.map(l=>l.key===key?{...l,...change}:l));
  const setCurrent=(key:string|null)=>{currentRef.current=key;redraw(v=>v+1);};
  const lane=(key:string|null)=>lanesRef.current.find(l=>l.key===key);
  const choose=()=>setCurrent(nextLane(lanesRef.current));

  useEffect(()=>{document.title='모아풀기 · Study_EZ';},[]);

  /** 시작 화면의 강의별 오늘 현황. 열린 회차가 있으면 남은 문항을 센다. */
  const survey=useCallback(async()=>{
    setLoading(true);
    const read=await Promise.all(lanesRef.current.map(async l=>{
      try{
        const info=await api<RootOverview>(l.base);
        if(!info.policyReady)return {...l,info,left:0,error:info.message||'지금 열 수 없습니다.',view:undefined};
        if(info.sessionId){
          const v=await api<RootView>(sessionPath(info.sessionId));
          return {...l,info,left:v.finished?0:Math.max(0,v.count-v.position),error:undefined,view:undefined};
        }
        // 오늘 목록을 다 푼 강의(todayDone)는 「더 풀기」 자리다. 모아풀기는 오늘 목록만 섞는다.
        return {...l,info,left:info.todayDone?0:info.plan?.tasks.length??0,error:undefined,view:undefined};
      }catch(e){
        const message=e instanceof ApiError&&e.status===404?'공개된 Main-Quiz가 없습니다.':(e as Error).message;
        return {...l,info:undefined,left:0,error:message,view:undefined};
      }
    }));
    lanesRef.current=read;setLoading(false);redraw(v=>v+1);
  },[]);
  useEffect(()=>{void survey();},[survey]);

  /** stale: 그동안 이 강의에 더 새 행동을 그렸으면 화면을 바꾸지 않는다. */
  async function loadLane(key:string,sid:string,stale=false) {
    const next=await api<RootView>(sessionPath(sid));
    const now=lane(key);
    if(stale&&now?.view&&now.view.version!==next.version)return;
    // 서버에서 다시 읽은 강의는 미리 그려 둔 되돌리기 화면을 버린다. 되돌리기 자체는 서버가 한다.
    stack.current=stack.current.map(s=>s.key===key?{...s,before:null}:s);
    patch(key,{view:next});
  }

  const eligible=lanes.filter(l=>!l.error&&(l.left??0)>0);
  async function begin() {
    if(advancing||writes.blocked||!eligible.length)return;
    setAdvancing(true);setError('');
    try{
      // 열린 회차는 그대로 잇고, 없으면 강의 화면과 같은 시작 요청을 보낸다. 요청은 한 줄로 순서대로 간다.
      const started=eligible.map(l=>l.info?.sessionId?Promise.resolve({sessionId:l.info.sessionId}):writes.run(l.base+'/sessions',{}));
      if(started.some(p=>!p))return;
      const ids=await Promise.all(started as Promise<{sessionId:string}>[]);
      const views=await Promise.all(ids.map(r=>api<RootView>(sessionPath(r.sessionId))));
      stack.current=[];
      setLanes(all=>all.map(l=>{const i=eligible.findIndex(e=>e.key===l.key);return i<0?{...l,view:undefined}:{...l,view:views[i]};}));
      choose();setPhase('solve');
    }catch(e){setError((e as Error).message);}
    finally{setAdvancing(false);}
  }

  // 강의마다 지금 자리부터 다음 문항을 미리 받는다.
  const signature=lanes.map(l=>l.view&&!l.view.finished?`${l.view.sessionId}:${l.view.position}:${l.view.count}`:'').join('|');
  const {ensure}=frames;
  useEffect(()=>{for(const l of lanesRef.current)if(l.view&&!l.view.finished)ensure(l.view.sessionId,l.view.position,l.view.count);},[signature,ensure]);

  /** 이 행동이 저장되면 서버가 보일 화면. 미리 받은 문항으로 그린다. null: 서버를 기다린다. (RootLearning.predict와 같은 규칙) */
  function predict(current:RootView,action:RootAction):RootView|null {
    const version=current.version+1;
    if(action.kind==='reveal') {
      const frame=frames.get(current.sessionId,current.position);
      if(!current.task||current.task.answer||!frame?.task||frame.taskId!==current.task.id)return null;
      return {...current,version,canUndo:true,task:{...current.task,answer:frame.task.answer,attempted:!!action.attempted,
        response:action.response??'',helped:current.task.helped||!!action.helped||current.mapSeen}};
    }
    if(action.kind==='rate'||action.kind==='skip') {
      const position=current.position+1;
      const moved={...current,version,position,canUndo:true,blocked:null};
      if(position>=current.count)return {...moved,finished:true,task:null};
      const frame=frames.get(current.sessionId,position);
      if(!frame||frame.blocked)return null;
      return {...moved,blocked:frame.blocked,task:frame.task?{id:frame.task.id,question:frame.task.question,answer:null,response:null,
        attempted:null,helped:current.mapSeen||frame.task.helped,prerequisite:frame.task.prerequisite}:null};
    }
    return null;
  }

  function act(action:RootAction) {
    if(writes.blocked||advancing)return;
    if(action.kind==='undo')return undo();
    if(action.kind==='map')return;
    const key=currentRef.current;
    const current=lane(key)?.view;
    if(!key||!current)return;
    setError('');
    const confirmed=writes.run(`${sessionPath(current.sessionId)}/events`,{version:current.version,...action});
    if(!confirmed)return;
    // 답 보기는 그 문항에 머문다. 평가·보류·제외만 다음 강의를 고른다.
    const moves=action.kind!=='reveal';
    const next=predict(current,action);
    stack.current=[...stack.current,{key,before:next?current:null}];
    if(next) {
      patch(key,{view:next});
      if(moves)choose();
      // 강의 하나가 끝나면 서버의 요약(첫 학습·회상 가능)을 받아 마침 화면에 쓴다.
      if(next.finished)void confirmed.then(r=>loadLane(key,r.sessionId,true)).catch(()=>{});
      return;
    }
    // 제외: 미리 받은 뒤 과제의 막힘 여부가 바뀐다. 다시 받는다.
    if(action.kind==='exclude')frames.forget(current.sessionId);
    setAdvancing(true);
    void confirmed.then(r=>loadLane(key,r.sessionId)).then(()=>{if(moves)choose();})
      .catch(e=>{if(!(e instanceof ApiError))setError((e as Error).message);})
      .finally(()=>setAdvancing(false));
  }

  function undo() {
    const top=stack.current.at(-1);
    const current=top&&lane(top.key)?.view;
    if(!top||!current)return;
    if(!current.canUndo){stack.current=stack.current.slice(0,-1);redraw(v=>v+1);return;}
    const confirmed=writes.run(`${sessionPath(current.sessionId)}/events`,{version:current.version,kind:'undo'});
    if(!confirmed)return;
    stack.current=stack.current.slice(0,-1);
    setCurrent(top.key);
    if(top.before&&top.before.sessionId===current.sessionId) {
      patch(top.key,{view:{...top.before,version:current.version+1,mapSeen:current.mapSeen,summary:current.summary}});
      return;
    }
    setAdvancing(true);
    void confirmed.then(r=>loadLane(top.key,r.sessionId))
      .catch(e=>{if(!(e instanceof ApiError))setError((e as Error).message);})
      .finally(()=>setAdvancing(false));
  }

  /** 지금 문항의 강의 화면만 바꾼다(문제 수정·메모·중요도). 미리 받은 문항은 옛 문면이라 버린다. */
  function patchTask(change:(task:NonNullable<RootView['task']>)=>NonNullable<RootView['task']>) {
    const key=currentRef.current,current=lane(key)?.view;
    if(!key||!current?.task)return;
    frames.forget(current.sessionId);
    patch(key,{view:{...current,task:change(current.task)}});
  }

  async function backToStart() {
    setPhase('start');setCurrent(null);
    await survey();
  }
  async function retry() {
    if(!await writes.retry())return;
    const key=currentRef.current,current=lane(key)?.view;
    if(key&&current)await loadLane(key,current.sessionId).catch(e=>setError((e as Error).message));
  }
  async function reload() {
    for(const l of lanesRef.current)if(l.view)await loadLane(l.key,l.view.sessionId);
    choose();
  }

  const solving=phase==='solve'?lanes.filter(l=>l.view):[];
  const allDone=solving.length>0&&solving.every(l=>l.view!.finished);
  const cur=lane(currentRef.current);
  const total=solving.reduce((sum,l)=>sum+l.view!.count,0);
  const done=solving.reduce((sum,l)=>sum+Math.min(l.view!.position,l.view!.count),0);
  const shown:RootView|null=cur?.view&&!allDone?{...cur.view,position:done,count:total,canUndo:stack.current.length>0,finished:false}:null;
  const back=()=>(window.history.state?.idx>0?navigate(-1):navigate('/study'));

  return <main className="root-learning main-quiz-learning mq-mix">
    {(error||writes.error||writes.pending&&!writes.busy||writes.conflicts.some(r=>!r.acknowledged))&&<div role="alert" className="notice is-error">{error||writes.error||'이전에 저장 확인을 받지 못한 요청 또는 충돌 응답이 있습니다.'}
      {writes.pending&&<button disabled={writes.busy} onClick={()=>void retry()}>같은 요청 다시 저장</button>}
      {writes.conflicts.some(r=>!r.acknowledged)&&<button disabled={writes.busy} onClick={()=>void writes.acknowledge(reload)}>보관 응답 확인 후 서버 기록 불러오기</button>}
    </div>}
    {writes.slow&&<p className="bank-note main-quiz-save-status" role="status">저장 확인 중…</p>}

    {phase==='start'?<section className="mq-start">
      <header className="page-head mq-head"><div>
        <p className="mq-kicker"><button type="button" className="quiz-back" onClick={back}><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3 5 8l5 5"/></svg>뒤로</button><span className="mq-badge">Main-Quiz</span></p>
        <h1>모아풀기 · {lectures.length}개 강의</h1>
      </div></header>
      {!lectures.length?<p className="notice">고른 강의가 없습니다. <Link to="/study">강의 목록</Link>에서 강의를 체크하세요.</p>:<>
        <ul className="mq-mix-list" aria-label="고른 강의">
          {lanes.map(l=><li key={l.key} className={l.error||!(l.left??0)?'is-off':undefined}>
            <span className="mq-mix-title">{l.info?.title??l.runId}</span>
            <span className="mq-mix-count">{loading?'…':l.error?`열 수 없음 · ${l.error}`:(l.left??0)>0?`${l.info?.sessionId?'남은':'오늘'} ${l.left}문항`:l.info?.todayDone?'오늘 목록 마침':'오늘 과제 없음'}</span>
            {l.info&&<Link className="mq-mix-one" to={bankHref(l)}>이 강의만</Link>}
          </li>)}
        </ul>
        <section className="mq-today" aria-label="모아풀기 시작">
          <div className="mq-today-text">
            <h2>섞어 풀기</h2>
            <p>{loading?'오늘 과제를 세는 중…':eligible.length?<><b>{eligible.length}</b>개 강의 · <b>{eligible.reduce((s,l)=>s+(l.left??0),0)}</b>문항</>:'오늘 섞어 풀 과제가 없습니다.'}</p>
            <small>강의마다 오늘 목록을 그 순서대로 두고 번갈아 냅니다. 기록·복습일은 강의별로 쌓입니다.</small>
            <div className="mq-mode" role="radiogroup" aria-label="풀이 모드">
              {([['recall','주관식'],['mcq','객관식']] as [QuizMode,string][]).map(([value,label])=>
                <button key={value} type="button" role="radio" aria-checked={mode===value} className={mode===value?'is-on':''}
                  disabled={advancing} onClick={()=>{saveQuizMode(value);setMode(value);}}>{label}</button>)}
            </div>
          </div>
          <button className="mq-start-button" disabled={loading||advancing||writes.blocked||!eligible.length} onClick={()=>void begin()} aria-busy={advancing}>
            <Icon.play/>{eligible.some(l=>l.info?.sessionId)?'모아풀기 재개':'모아풀기 시작'}</button>
          {advancing&&<span className="sr-only" role="status">첫 문항을 여는 중…</span>}
        </section>
        <p><Link to="/study">강의 다시 선택</Link></p>
      </>}
    </section>
    :allDone?(writes.blocked||writes.queued>0)?<p role="status">마지막 저장과 미확인 요청을 확인 중입니다. 완료 현황은 확인 뒤 표시합니다.</p>
    :<section className="mq-done">
      <div className="mq-today mq-done-card"><div className="mq-today-text"><h2>오늘 모아풀기를 마쳤어요</h2>
        <p><b>{solving.length}</b>개 강의 · <b>{total}</b>문항</p></div>
        <div className="root-actions"><button className="pill-button" disabled={writes.blocked||!stack.current.length} onClick={()=>undo()}>되돌리기 <kbd>Z</kbd></button>
          <button className="mq-start-button" onClick={()=>navigate('/study')}>강의 목록으로</button></div></div>
      <ul className="mq-mix-list" aria-label="강의별 결과">
        {solving.map(l=><li key={l.key}><span className="mq-mix-title">{l.info?.title??l.runId}</span>
          <span className="mq-mix-count">{l.view!.count}문항 · 첫 학습 {l.view!.summary.learned}/{l.view!.summary.total} · 회상 가능 {l.view!.summary.recalled}</span></li>)}
      </ul>
      <UndoKey disabled={writes.blocked||!stack.current.length} onUndo={undo}/>
    </section>
    :shown&&cur?<>
      <RootSolve view={shown} title={cur.info?.title} scope={JSON.stringify([account,cur.subject,cur.runId])} disabled={writes.blocked}
        editPath={qid=>`${cur.base}/questions/${encodeURIComponent(qid)}/personal`}
        onEdited={result=>patchTask(task=>({...task,question:result.question,answer:task.answer?{...result.answer,memo:task.answer.memo}:null}))}
        mineBase={cur.base}
        onMineChanged={()=>{const v=cur.view;if(!v)return;frames.forget(v.sessionId);void loadLane(cur.key,v.sessionId).catch(e=>setError((e as Error).message));}}
        onMemo={(qid,memo)=>patchTask(task=>task.answer&&task.question.question_id===qid?{...task,answer:{...task.answer,memo}}:task)}
        tierPath={qid=>`${cur.base}/questions/${encodeURIComponent(qid)}/tier`}
        onTier={question=>patchTask(task=>task.question.question_id===question.question_id?{...task,question}:task)}
        advancing={advancing} onAction={act} onError={setError} onToday={()=>void backToStart()}/>
      {cur.view?.blocked?.includes('학습일')&&<button disabled={writes.blocked} onClick={()=>void backToStart()}>오늘 모아풀기 다시 시작</button>}
    </>:<p className="notice" role="status">문항을 불러오는 중…</p>}
  </main>;
}

/** 마침 화면의 Z. 풀이 화면에서는 RootSolve가 Z를 받는다. */
function UndoKey({disabled,onUndo}:{disabled:boolean;onUndo:()=>void}) {
  useEffect(()=>{
    const down=(event:KeyboardEvent)=>{
      if(disabled||event.repeat||event.altKey)return;
      if((event.target as HTMLElement|null)?.closest('input,textarea,select,[contenteditable="true"]'))return;
      if(event.key.toLowerCase()==='z'){event.preventDefault();onUndo();}
    };
    window.addEventListener('keydown',down);return()=>window.removeEventListener('keydown',down);
  },[disabled,onUndo]);
  return null;
}
