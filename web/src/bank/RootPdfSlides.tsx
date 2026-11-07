import { useEffect, useState } from 'react';
import { getDocument, GlobalWorkerOptions, type PDFDocumentLoadingTask, type RenderTask } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { SlideImage } from '../SlideImage';
import type { RootPdfSlide } from '../types/rootLearning';

GlobalWorkerOptions.workerSrc=workerUrl;
const documents=new Map<string,{task:PDFDocumentLoadingTask;users:number;timer?:ReturnType<typeof setTimeout>}>();
function acquire(url:string){
  let entry=documents.get(url);
  if(!entry){
    const assets=new URL('pdfjs/',new URL(import.meta.env.BASE_URL,window.location.href)).href;
    entry={task:getDocument({url,enableXfa:false,cMapUrl:assets+'cmaps/',cMapPacked:true,
      standardFontDataUrl:assets+'standard_fonts/',wasmUrl:assets+'wasm/'}),users:0};
    documents.set(url,entry);
  }
  clearTimeout(entry.timer);entry.users++;
  const current=entry;
  return {promise:entry.task.promise,release:()=>{
    if(--current.users===0)current.timer=setTimeout(()=>{documents.delete(url);void current.task.destroy();},15000);
  }};
}

function PdfSlide({slide}:{slide:RootPdfSlide}){
  const [image,setImage]=useState('');
  const [failed,setFailed]=useState(false);
  useEffect(()=>{
    let live=true;
    const pdf=acquire(slide.url);
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
  },[slide.url,slide.page]);
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
