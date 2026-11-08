import { useEffect, useState } from 'react';
import { getDocument, GlobalWorkerOptions, PDFDataRangeTransport, type PDFDocumentLoadingTask, type PDFDocumentProxy } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { SlideImage } from '../SlideImage';
import { apiUrl, authHeader } from '../api';
import type { RootPdfSlide } from '../types/rootLearning';

GlobalWorkerOptions.workerSrc=workerUrl;
const CHUNK=524288;
// A lecture PDF stays open while the learner studies it: reopening it for every answer
// re-read the file header, trailer and page tree before the first slide could draw.
const KEEP_OPEN_MS=20*60_000;
const RENDERED_LIMIT=16;

/**
 * Byte ranges through the API with the login header (R2 has no CORS rule).
 * Letting PDF.js open the URL itself always began with a full GET, so every new
 * document streamed the whole lecture PDF (22 MB) before the ranges started.
 */
class ApiRangeTransport extends PDFDataRangeTransport {
  failed?:(cause:Error)=>void;
  constructor(length:number,initial:Uint8Array,private url:string,private headers:Record<string,string>){super(length,initial);}
  override requestDataRange(begin:number,end:number){
    void fetchRange(this.url,this.headers,begin,end-1).then(({bytes})=>this.onDataRange(begin,bytes))
      .catch(cause=>this.failed?.(cause as Error));
  }
}

async function fetchRange(url:string,headers:Record<string,string>,first:number,last:number) {
  const response=await fetch(url,{headers:{...headers,Range:`bytes=${first}-${last}`}});
  if(response.status!==206&&response.status!==200)throw new Error(`참고 자료 범위 요청 실패 (${response.status})`);
  const total=Number(response.headers.get('Content-Range')?.split('/')[1]??response.headers.get('Content-Length'));
  let bytes=new Uint8Array(await response.arrayBuffer());
  if(response.status===200)bytes=bytes.slice(first,last+1);
  return {bytes,total};
}

type Entry={doc:Promise<PDFDocumentProxy>;task?:PDFDocumentLoadingTask;users:number;timer?:ReturnType<typeof setTimeout>};
const documents=new Map<string,Entry>();
const assets=()=>new URL('pdfjs/',new URL(import.meta.env.BASE_URL,window.location.href)).href;

function open(slide:RootPdfSlide):Entry {
  const key=slide.proxyPath??slide.url;
  const existing=documents.get(key);
  if(existing)return existing;
  const options={enableXfa:false,cMapUrl:assets()+'cmaps/',cMapPacked:true,standardFontDataUrl:assets()+'standard_fonts/',
    wasmUrl:assets()+'wasm/',disableStream:true,disableAutoFetch:true,rangeChunkSize:CHUNK};
  const entry:Entry={users:0,doc:null as unknown as Promise<PDFDocumentProxy>};
  entry.doc=(async()=>{
    if(!slide.proxyPath){const task=getDocument({...options,url:slide.url});entry.task=task;return task.promise;}
    const url=apiUrl(slide.proxyPath),headers=await authHeader();
    const head=await fetchRange(url,headers,0,CHUNK-1);
    if(!Number.isFinite(head.total)||head.total<=0)throw new Error('참고 자료 크기를 확인하지 못했습니다.');
    const range=new ApiRangeTransport(head.total,head.bytes,url,headers);
    const task=getDocument({...options,range});entry.task=task;
    // A lost range would leave PDF.js waiting forever: drop the document so the slide fails and a retry reopens it.
    range.failed=()=>{if(documents.get(key)===entry)documents.delete(key);void task.destroy();};
    return task.promise;
  })();
  documents.set(key,entry);
  // A failed load must not stay cached for the next question or a retry.
  entry.doc.catch(()=>{if(documents.get(key)===entry)documents.delete(key);});
  return entry;
}

function acquire(slide:RootPdfSlide){
  const key=slide.proxyPath??slide.url;
  const entry=open(slide);
  clearTimeout(entry.timer);entry.users++;
  return {promise:entry.doc,release:()=>{
    if(--entry.users===0)entry.timer=setTimeout(()=>{
      if(documents.get(key)===entry)documents.delete(key);
      void entry.task?.destroy();
    },KEEP_OPEN_MS);
  }};
}

// Drawn slides (data URLs), most recent last. Prepared ahead for the coming answers.
const rendered=new Map<string,Promise<string>>();
const slideKey=(slide:RootPdfSlide)=>`${slide.proxyPath??slide.url.split('?')[0]}#${slide.page}`;

function render(slide:RootPdfSlide):Promise<string> {
  const key=slideKey(slide);
  const old=rendered.get(key);
  if(old){rendered.delete(key);rendered.set(key,old);return old;}
  const pdf=acquire(slide);
  let timer:ReturnType<typeof setTimeout>|undefined;
  const drawn=(async()=>{
    try {
      const doc=await Promise.race([pdf.promise,new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(new Error('참고 자료 응답 시간 초과')),45_000);})]);
      const page=await doc.getPage(slide.page);
      const natural=page.getViewport({scale:1});
      const scale=Math.min(2,1800/Math.max(natural.width,natural.height));
      const viewport=page.getViewport({scale});
      const canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);
      await page.render({canvas,viewport}).promise;
      page.cleanup();
      return canvas.toDataURL('image/png');
    } finally {clearTimeout(timer);pdf.release();}
  })();
  rendered.set(key,drawn);
  drawn.catch(()=>{if(rendered.get(key)===drawn)rendered.delete(key);});
  while(rendered.size>RENDERED_LIMIT)rendered.delete(rendered.keys().next().value!);
  return drawn;
}

/** Open and draw these slides now so the answer shows them without waiting. */
export function prewarmPdfSlides(slides:RootPdfSlide[]){
  // One at a time: the visible answer's slide must not queue behind many others.
  void slides.reduce<Promise<unknown>>((before,slide)=>before.then(()=>render(slide)).catch(()=>{}),Promise.resolve());
}

function PdfSlide({slide}:{slide:RootPdfSlide}){
  const [image,setImage]=useState('');
  const [failed,setFailed]=useState(false);
  useEffect(()=>{
    let live=true;
    setImage('');setFailed(false);
    render(slide).then(url=>{if(live)setImage(url);}).catch(()=>{if(live)setFailed(true);});
    return()=>{live=false;};
  },[slide.url,slide.proxyPath,slide.page]);
  const label=slide.references?.length?`${slide.references.map(referenceLabel).join(' · ')} · PDF ${slide.page}쪽`
    :`${slide.sourceFilename} · PDF ${slide.page}쪽`;
  // 그림이 먼저, 출처 줄은 그 아래(2026-11-08 사용자 지시).
  return <figure className="bank-evidence-slide main-quiz-pdf-slide">
    {image?<SlideImage src={image} alt={label}/>:failed?<p role="alert">참고 슬라이드를 불러오지 못했습니다. 원본 열기로 확인하거나 새로고침해 주세요.</p>:<p role="status">슬라이드 불러오는 중…</p>}
    <figcaption>{label}{' · '}<a href={`${slide.url}#page=${slide.page}`} target="_blank" rel="noreferrer">원본 열기</a></figcaption>
  </figure>;
}

/** 「2023 79번」 → 「2023년 · 79번」 (Quiz Bank 족보 표시와 같다). */
function referenceLabel(reference:string){
  return reference.replace(/\b((?:19|20)\d{2})(?!\d)\s*년?\s*/,'$1년 · ');
}

function Extra({slides,label}:{slides:RootPdfSlide[];label:string}){
  const [expanded,setExpanded]=useState(false);
  if(!slides.length)return null;
  return <details className="bank-answer-context bank-extra-slides" onToggle={e=>setExpanded(e.currentTarget.open)}>
    <summary>{label} {slides.length}장</summary>
    {expanded&&slides.map(s=><PdfSlide key={`${s.sourceId}:${s.page}`} slide={s}/>)}</details>;
}

/**
 * 강의록 슬라이드. 판의 근거 보강이 있으면(`focusKnown`) Quiz Bank처럼 내용 대조로 고른 핵심만 펼치고
 * 나머지는 접는다. 없으면 종전처럼 첫 장을 펼치되 핵심이라고 표시하지 않는다.
 */
export function RootPdfSlides({slides,focusKnown=false,statusKnown=false}:{slides:RootPdfSlide[];focusKnown?:boolean;statusKnown?:boolean}){
  if(!slides.length)return null;
  const open=focusKnown?slides.filter(s=>s.primary):slides.slice(0,1);
  const rest=slides.filter(s=>!open.includes(s));
  return <section className="bank-slides main-quiz-pdf-slides" aria-label="참고 슬라이드">
    {open.map(s=><PdfSlide key={`${s.sourceId}:${s.page}`} slide={s}/>)}
    {focusKnown&&!open.length&&!statusKnown&&<p className="bank-note">확인된 핵심 근거 슬라이드가 없습니다.</p>}
    <Extra slides={rest} label="추가 참고 슬라이드"/>
  </section>;
}

/** 족보 지면(정리본 PDF의 실제 문항 쪽). 핵심이면 「핵심 근거 · 족보」로 펼치고, 아니면 첫 장을 펼친다. */
export function RootJokboSlides({slides}:{slides:RootPdfSlide[]}){
  if(!slides.length)return null;
  const core=slides.filter(s=>s.primary);
  const open=core.length?core:slides.slice(0,1);
  const title=core.length?'핵심 근거 · 족보':'참고 족보 문제';
  return <section className="bank-slides bank-jokbo-slides main-quiz-pdf-slides" aria-label={title}>
    <h2>{title}</h2>
    {open.map(s=><PdfSlide key={`${s.sourceId}:${s.page}`} slide={s}/>)}
    <Extra slides={slides.filter(s=>!open.includes(s))} label="추가 족보 지면"/>
  </section>;
}
