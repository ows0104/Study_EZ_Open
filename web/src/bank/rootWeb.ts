import { api } from '../api';
import { absoluteUrl, extensionCompatible, extensionInputMinimum, requestPreview } from '../bridge/previewBridge';
import { loadLatestBankPrompt } from './prompt';
import type { BankSource } from '../types/bank';
import { bankFileMetadata, readBankFile } from './responseFile';

export function webGenerationId(raw:string) {
  try {
    const value=bankFileMetadata(raw).generation_id;
    return typeof value==='string'&&/^[a-f0-9]{32}$/.test(value)?value:null;
  }catch{return null;}
}

export async function sendRootWeb(id:string) {
  if(!extensionCompatible(extensionInputMinimum('bank',true)))throw new Error('최신 Study EZ 브리지를 연결한 뒤 자동전송을 이용하세요.');
  type Packet={subject:string;runId:string;title:string;conceptMap:string;points:string;scope:string;examDate:string|null;
    inputMode?:'source'|'provided';
    sources:(BankSource&{downloadUrl:string})[]};
  const base='/api/admin/root-generation/'+id;
  const {packet:p}=await api<{packet:Packet}>(base+'/web-input');
  const latest=await loadLatestBankPrompt({subject:p.subject,runId:p.runId,title:p.title,bankExamDate:p.examDate??undefined},p.sources);
  const instructions=p.inputMode==='source'?'':'\n첨부 원본과 아래 Concept map·출제포인트를 대조해 필요한 전체 회상 방향을 출제한다.\n'+JSON.stringify({conceptMap:p.conceptMap,points:p.points});
  const prompt=latest.prompt+'\n\n결과 JSON 최상위에 "generation_id": "'+id+'"를 추가한다.\n'+instructions+
    (p.scope?'\n추가 출제 범위: '+p.scope:'');
  const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(prompt));
  const promptHash=[...new Uint8Array(hash)].map(n=>n.toString(16).padStart(2,'0')).join('');
  const dispatch=await api<{send:boolean}>(base+'/web-dispatch',{method:'POST',body:JSON.stringify({promptVersion:latest.version,promptHash})});
  if(!dispatch.send)throw new Error('전송 요청이 이미 기록되어 있습니다. 완성된 파일 수신을 기다리거나 파일을 불러오세요.');
  await requestPreview({requestId:'roots-'+id,lectureId:p.subject+'/'+p.runId,provider:'chatgpt',mode:'bank',
    prompt,promptVersion:latest.version,autoSend:true,files:p.sources.map(s=>({id:s.assetId,filename:s.filename,
      contentType:s.filename.toLowerCase().endsWith('.pdf')?'application/pdf':'text/markdown',downloadUrl:absoluteUrl(s.downloadUrl)}))});
}

export async function saveRootWebFile(id:string,file:File) {
  if(file.size>8_000_000)throw new Error('8MB 이하의 문제은행 파일을 선택하세요.');
  // Identity is verified by the shared contract using the actual file metadata;
  // the server then checks the frozen request's subject/run/version and hash.
  const bytes=new Uint8Array(await file.arrayBuffer());
  const raw=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);
  if(webGenerationId(raw)!==id)throw new Error('이 자동출제 요청의 파일이 아닙니다.');
  const header=bankFileMetadata(raw);
  const identity=header as typeof header & {subject:string;run_id:string};
  const checked=await readBankFile(file,{subject:identity.subject,runId:identity.run_id});
  await api('/api/admin/root-generation/'+id+'/web-response',{method:'PUT',body:JSON.stringify({raw,source:'manual',promptVersion:header.prompt_version,
    responseFile:checked.responseFile})});
}
