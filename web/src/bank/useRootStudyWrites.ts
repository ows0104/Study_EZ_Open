import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api';

type Request = {requestId:string;path:string;body:Record<string,unknown>;conflict:boolean;acknowledged?:boolean};
export function useRootStudyWrites(scope: string, saved: (result:{sessionId:string}, request:Request)=>Promise<void>) {
  const prefix=`studyez:root-write:${scope}:`;
  const [pending,setPending]=useState<Request|null>(null);
  const [conflicts,setConflicts]=useState<Request[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [storageBlocked,setStorageBlocked]=useState(false);
  const lock=useRef(false);
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
    setPending(rows.find(r=>!r.conflict)??null);
    setConflicts(rows.filter(r=>r.conflict));
    return rows;
  }
  useEffect(()=>{try{read();setStorageBlocked(false);}catch{setStorageBlocked(true);setError('보관된 요청을 읽지 못했습니다. 원본을 보존했으며 새 저장은 중지했습니다.');}},[prefix]);
  async function send(request:Request) {
    if(lock.current)return;
    lock.current=true;setBusy(true);setPending(request);setError('');
    let stored=false;
    try {
      localStorage.setItem(prefix+request.requestId,JSON.stringify(request));
      stored=true;
      const result=await api<{sessionId:string}>(request.path,{method:'POST',body:JSON.stringify(request.body)});
      await saved(result,request);
      localStorage.removeItem(prefix+request.requestId);
      read();
    } catch(e) {
      if(e instanceof ApiError && e.status===409) {
        try{localStorage.setItem(prefix+request.requestId,JSON.stringify({...request,conflict:true}));read();}
        catch{/* Keep the live request if browser storage is unavailable. */}
      }
      setError(stored?(e as Error).message:'미확인 요청을 이 브라우저에 보관하지 못했습니다. 화면을 닫기 전에 입력을 복사하고 다시 저장하세요.');
    } finally {lock.current=false;setBusy(false);}
  }
  function run(path:string, body:Record<string,unknown>) {
    if(storageBlocked||pending||lock.current||conflicts.some(r=>!r.acknowledged))return;
    const requestId=crypto.randomUUID();
    return send({requestId,path,body:{...body,requestId},conflict:false});
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
  return {run,retry:()=>pending?send(pending):undefined,acknowledge,pending,conflicts,busy,error,
    blocked:storageBlocked||busy||!!pending||conflicts.some(r=>!r.acknowledged),setError};
}
