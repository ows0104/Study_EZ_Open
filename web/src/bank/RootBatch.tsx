import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api';
import { useAuth } from '../auth';
import { SlidePreloader } from '../slidePreload';
import { ROOT_TIERS } from '../types/rootLearning';
import type { RootAction, RootFrame, RootMixInfo, RootMixOptions, RootMixOrder, RootMixPhases, RootSummary, RootTierName, RootView } from '../types/rootLearning';
import { Icon } from '../shell/icons';
import { useRootStudyWrites } from './useRootStudyWrites';
import { warm } from './useRootFrames';
import { RootSolve } from './RootSolve';
import { readQuizMode, saveQuizMode, type QuizMode } from './quizMode';
import { readMix, type MixLecture } from './mixLinks';
import './roots.css';
import './main-quiz.css';
import './root-batch.css';

/**
 * Main-Quiz 모아풀기(2026-11-18 사용자 「강의 목록형에서 선택해서 섞어서 풀 수 있게」).
 *
 * 서버 회차는 강의 단위 그대로다. 고른 강의마다 모아풀기 회차를 열고, 이 화면이 문항을 번갈아 낸다.
 * 시작 화면 선택지(docs/changes/2026-11-18-mix-options): 중요도(전체 + 강의별), 순서대로/섞어서, 복습 주기 이전 문제도 보기, 미열람 문항 보기.
 * 강의 안 순서는 서버가 회차를 열 때 정한다(순서대로 = 판 순서, 섞어서 = 선행 문항을 지킨 무작위). 기록·복습일은 강의별로 쌓인다.
 * 되돌리기(Z)는 강의를 가리지 않고 방금 한 행동부터 거꾸로 돌린다.
 */

const endpoint=(l:MixLecture)=>`/api/root-learning/lectures/${encodeURIComponent(l.subject)}/${encodeURIComponent(l.runId)}`;
const keyOf=(l:MixLecture)=>`${l.subject}/${l.runId}`;
const sessionPath=(id:string)=>`/api/root-learning/sessions/${encodeURIComponent(id)}`;

type Lane = MixLecture & {key:string; base:string; title?:string;
  /** 풀이 중 회차의 묶음(복습 대상 → 미열람 → 복습 주기 이전). 옛 회차는 없다. */
  phases?:RootMixPhases;
  /** 시작 화면: 중요도별 미열람·복습 대상·나중 수와 오늘 안 끝난 모아풀기 회차. */
  mix?:RootMixInfo; error?:string;
  /** 같은 조건으로 오늘 이미 다 푼 강의. 섞을 문항은 없지만 마침 화면에 그 강의의 결과로 남는다. */
  closed?:{count:number;summary:RootSummary};
  /** 풀이 중: 그 강의의 회차. */
  view?:RootView};
/** 화면 전체의 되돌리기 한 칸. before가 있으면 서버 확인 전에 그 화면을 바로 그린다. */
type Step = {key:string; before:RootView|null};

const AHEAD=3, BATCH=4;
const ALL:RootTierName[]=[...ROOT_TIERS];

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

/** 고른 조건의 문항 수: 고른 중요도마다 복습 대상 + (복습 주기 이전 문제도 보기면 나중) + (미열람 문항 보기면 미열람). */
export function mixCount(mix:RootMixInfo|undefined,tiers:readonly RootTierName[],unseen:boolean,ignoreSchedule:boolean):number {
  if(!mix)return 0;
  return tiers.reduce((sum,t)=>{const c=mix.counts[t];return c?sum+c.due+(ignoreSchedule?c.later:0)+(unseen?c.unseen:0):sum;},0);
}

const sameOptions=(a:RootMixOptions,b:RootMixOptions)=>a.unseen===b.unseen&&a.ignoreSchedule===b.ignoreSchedule
  &&a.order===b.order&&a.tiers.join()===b.tiers.join()&&!!a.prereqs===!!b.prereqs;

/** 섞어서: 회차·자리마다 정해지는 값(FNV-1a). 새로고침해도 같은 순서로 번갈아 낸다. */
function spread(text:string) {
  let h=0x811c9dc5;
  for(let i=0;i<text.length;i++){h^=text.charCodeAt(i);h=Math.imul(h,0x01000193);}
  // 끝 글자(자리 번호)만 다른 값들이 비슷하게 나오지 않게 섞는다(murmur3 fmix32). 없으면 한 강의가 늘 먼저였다.
  h^=h>>>16;h=Math.imul(h,0x85ebca6b);h^=h>>>13;h=Math.imul(h,0xc2b2ae35);h^=h>>>16;
  return h>>>0;
}

/**
 * 다음 문항을 낼 강의. 다 끝났으면 null.
 * 순서대로: 고른 순서(강의 번호 순)로 한 강의를 끝낸 뒤 다음.
 * 섞어서: 남은 문항 수에 비례한 확률로 강의를 고른다 — 모든 번갈아 놓기가 같은 확률이다. 값은 회차들·지금까지 푼 수로 정해
 * 새로고침해도 같은 순서다.
 */
/** 회차의 지금 자리가 어느 묶음인가: 0 복습 대상 · 1 미열람 · 2 복습 주기 이전. 묶음이 없는 옛 회차는 0. */
function phaseAt(lane:Pick<Lane,'view'|'phases'>):number {
  const v=lane.view!,p=lane.phases;
  if(!p)return 0;
  return v.position<p.due?0:v.position<p.due+p.unseen?1:2;
}

/** 지금 묶음에서 그 회차에 남은 칸 수. */
function leftInPhase(lane:Pick<Lane,'view'|'phases'>,phase:number):number {
  const v=lane.view!,p=lane.phases;
  const end=!p?v.count:phase===0?p.due:phase===1?p.due+p.unseen:v.count;
  return Math.max(0,Math.min(end,v.count)-v.position);
}

/**
 * 다음 문항을 낼 강의. 다 끝났으면 null.
 * 묶음(2026-11-19-mix-urgency-order): 모든 강의의 복습 대상이 끝나야 미열람, 그 뒤가 복습 주기 이전이다.
 * 복습 대상·미열람: 순서대로 = 고른 순서(강의 번호 순)로 한 강의씩, 섞어서 = 그 묶음에 남은 수에 비례한 추첨
 * (회차들·지금까지 푼 수로 정해 새로고침해도 같다). 복습 주기 이전: 강의마다 다음 칸 중 가장 급한 것(같으면 강의 순서).
 */
export function nextLane(lanes:Pick<Lane,'key'|'view'|'phases'>[],order:RootMixOrder='ordered'):string|null {
  const open=lanes.filter(l=>l.view&&!l.view.finished&&l.view.count>0&&l.view.position<l.view.count);
  if(!open.length)return null;
  const phase=Math.min(...open.map(phaseAt));
  const here=open.filter(l=>phaseAt(l)===phase);
  if(phase===2){
    let best=here[0],score=Infinity;
    for(const l of here){const p=l.phases!;const u=p.urgency[l.view!.position-p.due-p.unseen]??Infinity;if(u<score){score=u;best=l;}}
    return best.key;
  }
  if(order==='ordered')return here[0].key;
  const views=lanes.flatMap(l=>l.view?[l.view]:[]);
  const done=views.reduce((sum,v)=>sum+Math.min(v.position,v.count),0);
  const seed=views.map(v=>v.sessionId).sort().join(',');
  const left=here.map(l=>leftInPhase(l,phase));
  let pick=spread(`${seed}:${done}`)%Math.max(1,left.reduce((a,b)=>a+b,0));
  for(const [i,l] of here.entries()){if(pick<left[i])return l.key;pick-=left[i];}
  return here[here.length-1].key;
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
  // 시작 화면 선택지. 강의 하나 화면의 중요도 저장값과 따로다.
  const [laneTiers,setLaneTiers]=useState<Record<string,RootTierName[]>>({});
  const [unseen,setUnseen]=useState(false);
  const [ignoreSchedule,setIgnoreSchedule]=useState(false);
  // 선행 문항 포함(2026-11-18-prereq-toggle): 서버가 고른 문항의 선행 문항을 중요도 밖에서도 더한다.
  const [prereqs,setPrereqs]=useState(false);
  const [order,setOrder]=useState<RootMixOrder>('ordered');
  const [perLecture,setPerLecture]=useState(false);
  const orderRef=useRef<RootMixOrder>('ordered');
  const lanes=lanesRef.current;
  const setLanes=(change:(lanes:Lane[])=>Lane[])=>{lanesRef.current=change(lanesRef.current);redraw(v=>v+1);};
  const patch=(key:string,change:Partial<Lane>)=>setLanes(all=>all.map(l=>l.key===key?{...l,...change}:l));
  const setCurrent=(key:string|null)=>{currentRef.current=key;redraw(v=>v+1);};
  const lane=(key:string|null)=>lanesRef.current.find(l=>l.key===key);
  const choose=()=>setCurrent(nextLane(lanesRef.current,orderRef.current));

  useEffect(()=>{document.title='모아풀기 · Study_EZ';},[]);

  /** 시작 화면의 강의별 수(중요도 × 미열람·복습 대상·나중)와 오늘 안 끝난 모아풀기 회차. */
  const survey=useCallback(async()=>{
    setLoading(true);
    const read=await Promise.all(lanesRef.current.map(async l=>{
      try{
        const mix=await api<RootMixInfo>(`${l.base}/mix`);
        return {...l,mix,title:mix.title,error:undefined,view:undefined};
      }catch(e){
        const message=e instanceof ApiError&&e.status===404?'공개된 Main-Quiz가 없습니다.':(e as Error).message;
        return {...l,mix:undefined,error:message,view:undefined};
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

  const tiersOf=(key:string)=>laneTiers[key]??ALL;
  const optionsOf=(key:string):RootMixOptions=>({tiers:tiersOf(key),unseen,ignoreSchedule,order,...(prereqs?{prereqs}:{})});
  const openOf=(l:Lane)=>l.mix?.open.find(o=>sameOptions(o.options,optionsOf(l.key)));
  /** 강의 줄의 수. 같은 조건으로 이어 풀 회차가 있으면 남은 수. */
  const countOf=(l:Lane)=>l.error||!l.mix||!tiersOf(l.key).length?0:openOf(l)?.left??mixCount(l.mix,tiersOf(l.key),unseen,ignoreSchedule);
  const live=lanes.filter(l=>l.mix&&!l.error);
  const eligible=live.filter(l=>countOf(l)>0);
  const totalCount=eligible.reduce((sum,l)=>sum+countOf(l),0);
  /** 전체 칩 하나를 모든 강의에 적용한다(강의별로 바꾼 그 중요도를 덮어쓴다). 다른 중요도는 강의별 값 그대로. */
  function setTierEverywhere(tier:RootTierName,on:boolean) {
    setLaneTiers(old=>{
      const next={...old};
      for(const l of live){const now=old[l.key]??ALL;next[l.key]=ROOT_TIERS.filter(t=>t===tier?on:now.includes(t));}
      return next;
    });
  }
  function setLaneTier(key:string,tier:RootTierName,on:boolean) {
    setLaneTiers(old=>{const now=old[key]??ALL;return {...old,[key]:ROOT_TIERS.filter(t=>t===tier?on:now.includes(t))};});
  }

  async function begin() {
    if(advancing||writes.blocked||!eligible.length)return;
    setAdvancing(true);setError('');
    try{
      // 같은 조건의 안 끝난 회차는 그대로 잇고, 없으면 모아풀기 회차를 연다. 요청은 한 줄로 순서대로 간다.
      orderRef.current=order;
      const started=eligible.map(l=>{const open=openOf(l);
        return open?Promise.resolve({sessionId:open.sessionId,phases:open.phases}):writes.run(l.base+'/mix-sessions',optionsOf(l.key));});
      if(started.some(p=>!p))return;
      // 같은 조건으로 오늘 이미 다 푼 강의: 섞을 문항은 없지만 마침 화면에 결과로 남긴다(#219 e198b5c8).
      const finished=live.filter(l=>!eligible.includes(l)).flatMap(l=>{
        const closed=l.mix?.closed?.find(c=>sameOptions(c.options,optionsOf(l.key)));return closed?[{key:l.key,closed}]:[];});
      const closedViews=await Promise.all(finished.map(f=>api<RootView>(sessionPath(f.closed.sessionId)).catch(()=>null)));
      setLanes(all=>all.map(l=>{const i=finished.findIndex(f=>f.key===l.key);const v=i<0?null:closedViews[i];
        return {...l,closed:v?{count:v.count,summary:v.summary}:undefined};}));
      const ids=await Promise.all(started as Promise<{sessionId:string;phases?:RootMixPhases}>[]);
      const views=await Promise.all(ids.map(r=>api<RootView>(sessionPath(r.sessionId))));
      stack.current=[];
      setLanes(all=>all.map(l=>{const i=eligible.findIndex(e=>e.key===l.key);return i<0?{...l,view:undefined,phases:undefined}:{...l,view:views[i],phases:ids[i].phases};}));
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
  // 마침 화면: 이번에 푼 강의와, 새로고침 전에 이미 끝낸 강의(closed).
  const results=phase==='solve'?lanes.flatMap(l=>{const r=l.view?{count:l.view.count,summary:l.view.summary}:l.closed;
    return r?[{key:l.key,title:l.title??l.runId,...r}]:[];}):[];
  const done=solving.reduce((sum,l)=>sum+Math.min(l.view!.position,l.view!.count),0);
  const shown:RootView|null=cur?.view&&!allDone?{...cur.view,position:done,count:total,canUndo:stack.current.length>0,finished:false}:null;
  const back=()=>(window.history.state?.idx>0?navigate(-1):navigate('/study'));
  const count=(n:number)=>n.toLocaleString('ko-KR');

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
        <section className="mq-today mq-mix-options" aria-label="모아풀기 시작">
          <div className="mq-today-text">
            <div className="mq-mix-tiers">
              <div className="mq-focus" role="group" aria-label="중요도">
                {ROOT_TIERS.map(tier=>{
                  const having=live.filter(l=>tiersOf(l.key).includes(tier)).length;
                  const on=live.length>0&&having===live.length,some=having>0&&!on;
                  // 끄면 어느 강의에도 중요도가 남지 않는 칩은 끌 수 없다.
                  const last=on&&ROOT_TIERS.every(t=>t===tier||!live.some(l=>tiersOf(l.key).includes(t)));
                  const n=live.reduce((sum,l)=>sum+mixCount(l.mix,[tier],unseen,ignoreSchedule),0);
                  return <button key={tier} type="button" aria-pressed={on?true:some?'mixed':false}
                    disabled={loading||advancing||last||!live.length}
                    className={[n?'':'is-empty',some?'is-some':''].filter(Boolean).join(' ')||undefined}
                    onClick={()=>setTierEverywhere(tier,!on)}>
                    {on&&<Icon.check/>}{tier}<b>{loading?'…':count(n)}</b></button>;
                })}
              </div>
              <button type="button" className="mq-mix-expand" aria-expanded={perLecture} aria-controls="mq-mix-lectures"
                disabled={!live.length} onClick={()=>setPerLecture(v=>!v)}>강의별<Icon.chevronDown/></button>
            </div>
            <div className="mq-mix-checks">
              <label><input type="checkbox" checked={ignoreSchedule} disabled={advancing}
                onChange={e=>setIgnoreSchedule(e.target.checked)}/>복습 주기 이전 문제도 보기</label>
              <label><input type="checkbox" checked={unseen} disabled={advancing}
                onChange={e=>setUnseen(e.target.checked)}/>미열람 문항 보기</label>
              <label><input type="checkbox" checked={prereqs} disabled={advancing}
                onChange={e=>setPrereqs(e.target.checked)}/>선행 문항 포함</label>
            </div>
            <div className="mq-mix-modes">
              <div className="mq-mode" role="radiogroup" aria-label="문항 순서">
                {([['ordered','순서대로'],['random','섞어서']] as [RootMixOrder,string][]).map(([value,label])=>
                  <button key={value} type="button" role="radio" aria-checked={order===value} className={order===value?'is-on':''}
                    disabled={advancing} onClick={()=>setOrder(value)}>{label}</button>)}
              </div>
              <div className="mq-mode" role="radiogroup" aria-label="풀이 모드">
                {([['recall','주관식'],['mcq','객관식']] as [QuizMode,string][]).map(([value,label])=>
                  <button key={value} type="button" role="radio" aria-checked={mode===value} className={mode===value?'is-on':''}
                    disabled={advancing} onClick={()=>{saveQuizMode(value);setMode(value);}}>{label}</button>)}
              </div>
            </div>
          </div>
          <button className="mq-start-button" disabled={loading||advancing||writes.blocked||!eligible.length} onClick={()=>void begin()} aria-busy={advancing}>
            <Icon.play/>{eligible.some(l=>openOf(l))?'모아풀기 재개':'모아풀기 시작'}
            <span className="mq-card-count" aria-label={`${totalCount}문항`} aria-live="polite">{loading?'…':count(totalCount)}</span></button>
          {advancing&&<span className="sr-only" role="status">첫 문항을 여는 중…</span>}
        </section>
        <ul className="mq-mix-list" id="mq-mix-lectures" aria-label="고른 강의">
          {lanes.map(l=>{
            const n=countOf(l),open=openOf(l);
            return <li key={l.key} className={l.error||!n?'is-off':undefined}>
              <span className="mq-mix-title">{l.title??l.runId}</span>
              <span className="mq-mix-count">{loading?'…':l.error?`열 수 없음 · ${l.error}`:open?`남은 ${count(n)}문항`:`${count(n)}문항`}</span>
              {perLecture&&l.mix&&!l.error&&<div className="mq-focus mq-mix-lane-tiers" role="group" aria-label={`${l.title??l.runId} 중요도`}>
                {ROOT_TIERS.map(tier=>{
                  const on=tiersOf(l.key).includes(tier),k=mixCount(l.mix,[tier],unseen,ignoreSchedule);
                  return <button key={tier} type="button" aria-pressed={on} disabled={advancing} className={k?undefined:'is-empty'}
                    onClick={()=>setLaneTier(l.key,tier,!on)}>{on&&<Icon.check/>}{tier}<b>{count(k)}</b></button>;
                })}
              </div>}
            </li>;
          })}
        </ul>
        <p><Link to="/study">강의 다시 선택</Link></p>
      </>}
    </section>
    :allDone?(writes.blocked||writes.queued>0)?<p role="status">마지막 저장과 미확인 요청을 확인 중입니다. 완료 현황은 확인 뒤 표시합니다.</p>
    :<section className="mq-done">
      <div className="mq-today mq-done-card"><div className="mq-today-text"><h2>오늘 모아풀기를 마쳤어요</h2>
        <p><b>{results.length}</b>개 강의 · <b>{results.reduce((sum,r)=>sum+r.count,0)}</b>문항</p></div>
        <div className="root-actions"><button className="pill-button" disabled={writes.blocked||!stack.current.length} onClick={()=>undo()}>되돌리기 <kbd>Z</kbd></button>
          <button className="mq-start-button" onClick={()=>navigate('/study')}>강의 목록으로</button></div></div>
      <ul className="mq-mix-list" aria-label="강의별 결과">
        {results.map(r=><li key={r.key}><span className="mq-mix-title">{r.title}</span>
          <span className="mq-mix-count">{r.count}문항 · 첫 학습 {r.summary.learned}/{r.summary.total} · 회상 가능 {r.summary.recalled}</span></li>)}
      </ul>
      <UndoKey disabled={writes.blocked||!stack.current.length} onUndo={undo}/>
    </section>
    :shown&&cur?<>
      <RootSolve view={shown} title={cur.title} scope={JSON.stringify([account,cur.subject,cur.runId])} disabled={writes.blocked}
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
