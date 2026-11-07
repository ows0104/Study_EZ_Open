import { useEffect, useState } from 'react';
import { getDocument, GlobalWorkerOptions, type PDFDocumentLoadingTask, type RenderTask } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { SlideImage } from '../SlideImage';
import { apiUrl, authHeader } from '../api';
import type { RootPdfSlide } from '../types/rootLearning';

GlobalWorkerOptions.workerSrc=workerUrl;
type Entry={task:Promise<PDFDocumentLoadingTask>;users:number;timer?:ReturnType<typeof setTimeout>};
const documents=new Map<string,Entry>();
// The signed R2 URL works for links only: the bucket has no CORS rule, so PDF.js reads
// the same frozen file through the API (with the login header and byte ranges).
function acquire(slide:RootPdfSlide){
  const key=slide.proxyPath??slide.url;
  let entry=documents.get(key);
  if(!entry){
    const assets=new URL('pdfjs/',new URL(import.meta.env.BASE_URL,window.location.href)).href;
    const task=(slide.proxyPath?authHeader():Promise.resolve({})).then(httpHeaders=>getDocument({
      url:slide.proxyPath?apiUrl(slide.proxyPath):slide.url,httpHeaders,enableXfa:false,cMapUrl:assets+'cmaps/',cMapPacked:true,
      standardFontDataUrl:assets+'standard_fonts/',wasmUrl:assets+'wasm/',
      // Through the API, only the byte ranges the drawn pages need: by default PDF.js keeps
      // streaming the whole file (22MB lecture PDFs held the one API instance for ~9s).
      // Each range request passes auth and a DB lookup, so use larger chunks than 64KB.
      ...(slide.proxyPath?{disableStream:true,disableAutoFetch:true,rangeChunkSize:524288}:{})}));
    const created:Entry={task,users:0};entry=created;
    documents.set(key,created);
    // A failed load must not stay cached for the next question or a retry.
    void task.then(t=>t.promise).catch(()=>{if(documents.get(key)===created)documents.delete(key);});
  }
  clearTimeout(entry.timer);entry.users++;
  const current=entry;
  return {promise:current.task.then(t=>t.promise),release:()=>{
    if(--current.users===0)current.timer=setTimeout(()=>{if(documents.get(key)===current)documents.delete(key);void current.task.then(t=>t.destroy());},15000);
  }};
}

function PdfSlide({slide}:{slide:RootPdfSlide}){
  const [image,setImage]=useState('');
  const [failed,setFailed]=useState(false);
  useEffect(()=>{
    let live=true;
    const pdf=acquire(slide);
    let render:RenderTask|undefined;
    setImage('');setFailed(false);
    void (async()=>{
      const doc=await pdf.promise;
      const page=await doc.getPage(slide.page);
      if(!live)return;
      const natural=page.getViewport({scale:1});
      const scale=Math.min(2,1800/Math.max(natural.width,natural.height));
      const viewport=page.getViewport({scale});
      const canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);
      render=page.render({canvas,viewport});await render.promise;
      if(live)setImage(canvas.toDataURL('image/png'));
      page.cleanup();
    })().catch(()=>{if(live)setFailed(true);});
    return()=>{live=false;render?.cancel();pdf.release();};
  },[slide.url,slide.proxyPath,slide.page]);
  const label=`${slide.sourceFilename} · PDF ${slide.page}쪽`;
  return <figure className="bank-evidence-slide main-quiz-pdf-slide"><figcaption>{label}
    {' · '}<a href={`${slide.url}#page=${slide.page}`} target="_blank" rel="noreferrer">원본 열기</a></figcaption>
    {image?<SlideImage src={image} alt={label}/>:failed?<p role="alert">참고 슬라이드를 불러오지 못했습니다. 원본 열기로 확인하거나 새로고침해 주세요.</p>:<p role="status">슬라이드 불러오는 중…</p>}
  </figure>;
}

export function RootPdfSlides({slides}:{slides:RootPdfSlide[]}){
  const [expanded,setExpanded]=useState(false);
  if(!slides.length)return null;
  return <section className="bank-slides main-quiz-pdf-slides" aria-label="참고 슬라이드">
    <h3>참고 슬라이드</h3><PdfSlide slide={slides[0]}/>
    {slides.length>1&&<details className="bank-answer-context" onToggle={e=>setExpanded(e.currentTarget.open)}>
      <summary>추가 참고 슬라이드 {slides.length-1}장</summary>
      {expanded&&slides.slice(1).map(s=><PdfSlide key={`${s.sourceId}:${s.page}`} slide={s}/>)}</details>}
  </section>;
}
