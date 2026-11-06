import { useEffect, useState } from 'react';
import { api, ApiError } from '../api';
import { useAuth } from '../auth';
import type { RootOverview } from '../types/rootLearning';

type Entry = {mode:'legacy'} | {mode:'structured'; overview:RootOverview};
export function useMainQuizEntry(subject:string,runId:string,enabled=true,version=0) {
  const {session}=useAuth();
  const scope=JSON.stringify([session?.user.id??'',subject,runId,version]);
  const [state,setState]=useState<{scope:string;entry:Entry|null;error:string}|null>(null);
  useEffect(()=>{
    if(!enabled)return;
    let live=true;
    api<Entry>(`/api/main-quiz/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/entry`)
      .then(entry=>{
        if(entry.mode!=='legacy'&&(entry.mode!=='structured'||!entry.overview))throw Error('Main Quiz 자료 상태를 확인하지 못했습니다. 다시 불러오세요.');
        if(live)setState({scope,entry,error:''});
      }).catch(cause=>{
        if(!live)return;
        setState({scope,entry:cause instanceof ApiError&&[404,405].includes(cause.status)?{mode:'legacy'}:null,
          error:cause instanceof ApiError&&[404,405].includes(cause.status)?'':cause.message});
      });
    return()=>{live=false;};
  },[scope,subject,runId,enabled]);
  return state?.scope===scope?state:{entry:null,error:''};
}
