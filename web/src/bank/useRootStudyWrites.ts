import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api';

type Request = {requestId:string;path:string;body:Record<string,unknown>;conflict:boolean;acknowledged?:boolean;
  /** Order of creation; reloaded requests are sent again in this order. */
  seq?:number;
  /** Never sent: it followed a request the server refused, so it is kept, not replayed. */
  unsent?:boolean};
type Result={sessionId:string;version:number};
type Waiter={resolve:(r:Result)=>void;reject:(e:Error)=>void};

/**
 * Ordered study writes that do not hold the screen.
 *
 * Each request is kept in this browser before it is sent and removed only after the server
 * confirms it. Requests go one at a time in order (each event carries the version the
 * previous one produces). A lost response halts the queue until the learner retries the
 * same requests; a refused one (409) is preserved with every request queued after it.
 */
export function useRootStudyWrites(scope: string) {
  const prefix=`studyez:root-write:${scope}:`;
  const [pending,setPending]=useState<Request[]>([]);
  const [conflicts,setConflicts]=useState<Request[]>([]);
  const [busy,setBusy]=useState(false);
  const [slow,setSlow]=useState(false);
  const [halted,setHalted]=useState(false);
  const [error,setError]=useState('');
  const [storageBlocked,setStorageBlocked]=useState(false);
  const queue=useRef<Request[]>([]);
  const waiters=useRef(new Map<string,Waiter>());
  const running=useRef(false);
  const stopped=useRef(false);
  const lock=useRef(false);
  const counter=useRef(0);
  function read() {
    const rows:Request[]=[];
    for(let i=0;i<localStorage.length;i++) {
      const key=localStorage.key(i)!;
      if(!key.startsWith(prefix))continue;
      const r=JSON.parse(localStorage.getItem(key)!) as Request;
      if(typeof r.requestId!=='string'||!r.path?.startsWith('/api/root-learning/')||!r.body
        ||key!==prefix+r.requestId||r.body.requestId!==r.requestId)throw new Error('보관된 요청 형식을 확인하세요. 원본을 보존했습니다.');
      rows.push(r);
    }
    const open=rows.filter(r=>!r.conflict).sort((a,b)=>(a.seq??0)-(b.seq??0));
    queue.current=open;setPending(open);
    setConflicts(rows.filter(r=>r.conflict));
    return open;
  }
  useEffect(()=>{
    try{
      // Requests left by an earlier page wait for an explicit retry, as before.
      if(read().length){stopped.current=true;setHalted(true);}
      setStorageBlocked(false);
    }catch{setStorageBlocked(true);setError('보관된 요청을 읽지 못했습니다. 원본을 보존했으며 새 저장은 중지했습니다.');}
  },[prefix]);
  useEffect(()=>{
    const leaving=(event:BeforeUnloadEvent)=>{if(!queue.current.length)return;event.preventDefault();event.returnValue='';};
    window.addEventListener('beforeunload',leaving);return()=>window.removeEventListener('beforeunload',leaving);
  },[]);
  function settle(id:string,how:'resolve'|'reject',value:Result|Error){
    const w=waiters.current.get(id);waiters.current.delete(id);
    if(w)how==='resolve'?w.resolve(value as Result):w.reject(value as Error);
  }
  async function pump() {
    if(running.current||stopped.current)return;
    running.current=true;setBusy(true);
    try {
      while(queue.current.length&&!stopped.current) {
        const r=queue.current[0];
        const timer=setTimeout(()=>setSlow(true),2500);
        try {
          const result=await api<Result>(r.path,{method:'POST',body:JSON.stringify(r.body)});
          localStorage.removeItem(prefix+r.requestId);
          queue.current=queue.current.slice(1);setPending(queue.current);
          settle(r.requestId,'resolve',result);
        } catch(e) {
          const cause=e as Error;
          if(e instanceof ApiError&&e.status===409) {
            // The refused request and everything built on it are preserved, never replayed.
            const kept=queue.current.map((q,i)=>({...q,conflict:true,...(i?{unsent:true}:{})}));
            try{for(const q of kept)localStorage.setItem(prefix+q.requestId,JSON.stringify(q));}
            catch{/* Keep the live requests if browser storage is unavailable. */}
            queue.current=[];setPending([]);setConflicts(old=>[...old.filter(o=>!kept.some(k=>k.requestId===o.requestId)),...kept]);
            for(const q of kept)settle(q.requestId,'reject',cause);
          } else {
            stopped.current=true;setHalted(true);
            for(const q of queue.current)settle(q.requestId,'reject',cause);
          }
          setError(cause.message);
        } finally {clearTimeout(timer);setSlow(false);}
      }
    } finally {running.current=false;setBusy(false);}
  }
  /** Queue a write. The promise settles when the server confirms (or refuses) it. */
  function run(path:string, body:Record<string,unknown>):Promise<Result>|undefined {
    if(storageBlocked||stopped.current||conflicts.some(r=>!r.acknowledged))return;
    const requestId=crypto.randomUUID();
    const request:Request={requestId,path,body:{...body,requestId},conflict:false,seq:Date.now()*1000+(counter.current++%1000)};
    try{localStorage.setItem(prefix+requestId,JSON.stringify(request));}
    catch{setError('미확인 요청을 이 브라우저에 보관하지 못했습니다. 화면을 닫기 전에 입력을 복사하고 다시 저장하세요.');return;}
    setError('');
    const promise=new Promise<Result>((resolve,reject)=>waiters.current.set(requestId,{resolve,reject}));
    promise.catch(()=>{});
    queue.current=[...queue.current,request];setPending(queue.current);
    void pump();
    return promise;
  }
  /** Send the same stored requests again, in order. Resolves when the queue is empty. */
  async function retry() {
    if(running.current)return;
    stopped.current=false;setHalted(false);setError('');
    await pump();
    if(!queue.current.length&&!stopped.current)return true;
  }
  async function acknowledge(reload:()=>Promise<void>) {
    if(lock.current)return;
    lock.current=true;setBusy(true);
    try {
      await reload();
      for(const r of conflicts)localStorage.setItem(prefix+r.requestId,JSON.stringify({...r,acknowledged:true}));
      read();setError('');
    }catch(e){setError((e as Error).message);}finally{lock.current=false;setBusy(false);}
  }
  const unacknowledged=conflicts.some(r=>!r.acknowledged);
  return {run,retry,acknowledge,pending:halted&&pending.length?pending[0]:null,queued:pending.length,conflicts,busy,slow,halted,error,
    blocked:storageBlocked||halted||unacknowledged,setError};
}
