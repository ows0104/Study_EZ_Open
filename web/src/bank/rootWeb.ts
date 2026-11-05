import { api } from '../api';
import { absoluteUrl, extensionCompatible, extensionInputMinimum, requestPreview } from '../bridge/previewBridge';
import { loadLatestBankPrompt } from './prompt';
import type { BankSource } from '../types/bank';

export function webGenerationId(raw:string) {
  try {const header=/^\uFEFF?<!-- STUDYEZ_BANK_FILE (\{[^\n]+\}) -->/.exec(raw);
    const value=header?JSON.parse(header[1]).generation_id:undefined;
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
  const prompt=latest.prompt+'\n\n뿌리 학습용 추가 설계 계약\n'+
    (p.inputMode==='source'?'첨부 원본 전체의 뼈대·기초 회상에서 세부 연결로 이어지는 문항을 작성한다. 별도 원본 전용 단계가 독립 지도·출제포인트를 작성해 이후 이 문항과 대조한다. ':'아래 Concept map·출제포인트를 원본과 대조해 필요한 전체 회상 방향을 실제 문항으로 시험한다. ')+
    '발문 제공/정답 회상/해설 등장을 구별하며 방향 전체를 단일 문항으로 회상하게 한다. 목록 밖 누락도 확인하고 범위·중요도·불확실성을 보존한다. matching/sequence/보기 풀은 이번에 사용하지 않는다.\n'+
    '완성 MD 첫 줄 STUDYEZ_BANK_FILE JSON에 추가 필드 "generation_id": "'+id+'"를 반드시 넣는다. 기존 과목·강의 ID·버전과 실제 파일 검증 계약은 유지한다.\n'+
    JSON.stringify(p.inputMode==='source'?{scope:p.scope}:{conceptMap:p.conceptMap,points:p.points,scope:p.scope});
  const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(prompt));
  const promptHash=[...new Uint8Array(hash)].map(n=>n.toString(16).padStart(2,'0')).join('');
  const dispatch=await api<{send:boolean}>(base+'/web-dispatch',{method:'POST',body:JSON.stringify({promptVersion:latest.version,promptHash})});
  if(!dispatch.send)throw new Error('전송 요청이 이미 기록되어 있습니다. 자동으로 중복 전송하지 않습니다. 완성된 MD 수신을 기다리거나 파일을 불러오세요.');
  await requestPreview({requestId:'roots-'+id,lectureId:p.subject+'/'+p.runId,provider:'chatgpt',mode:'bank',
    prompt,promptVersion:latest.version,autoSend:true,files:p.sources.map(s=>({id:s.assetId,filename:s.filename,
      contentType:s.filename.toLowerCase().endsWith('.pdf')?'application/pdf':'text/markdown',downloadUrl:absoluteUrl(s.downloadUrl)}))});
}

export async function saveRootWebFile(id:string,file:File) {
  if(file.size>8000000)throw new Error('8MB 이하의 완성 MD 파일을 선택하세요.');
  const raw=await file.text();
  if(webGenerationId(raw)!==id)throw new Error('이 자동출제 요청의 MD 파일이 아닙니다.');
  const header=JSON.parse(/^\uFEFF?<!-- STUDYEZ_BANK_FILE (\{[^\n]+\}) -->/.exec(raw)![1]);
  const bytes=new TextEncoder().encode(raw);const hash=await crypto.subtle.digest('SHA-256',bytes);
  const sha256=[...new Uint8Array(hash)].map(n=>n.toString(16).padStart(2,'0')).join('');
  await api('/api/admin/root-generation/'+id+'/web-response',{method:'PUT',body:JSON.stringify({raw,source:'manual',promptVersion:header.prompt_version,
    responseFile:{filename:file.name,byteLength:bytes.byteLength,sha256}})});
}
