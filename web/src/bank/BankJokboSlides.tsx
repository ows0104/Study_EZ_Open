import { SlideImage } from "../SlideImage";
import { useState } from "react";
import type { SlidePreloader } from "../slidePreload";
import type { BankAnswer } from "../types/bank";

function referenceLabel(reference: string) {
  return reference.replace(/\b((?:19|20)\d{2})(?!\d)\s*년?\s*/, "$1년 · ");
}

export function BankJokboSlides({ slides, preload, collapseReferences = false }: {
  slides: BankAnswer["jokboSlides"]; preload?: SlidePreloader; collapseReferences?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  if (!slides?.length) return null;
  const primary = slides.filter(slide => slide.primary);
  const extra = slides.filter(slide => !slide.primary);
  const title = primary.length ? "핵심 근거 · 족보" : "참고한 족보";
  const image = (slide: NonNullable<BankAnswer["jokboSlides"]>[number]) => <figure key={`${slide.pdfFilename}:${slide.page}`}>
      <figcaption><div className="bank-jokbo-references">
        {slide.references.map(reference => <b className="bank-jokbo-reference" key={reference}>{referenceLabel(reference)}</b>)}
      </div>{slide.pdfFilename} · PDF {slide.page}쪽{" · "}
        {slide.embedded ? "필기 PDF에 첨부된 기출 · " : ""}
        <a href={slide.url} target="_blank" rel="noreferrer">지면 크게 보기 ↗</a>
      </figcaption>
      <SlideImage src={slide.url} preload={preload} alt={`족보 ${slide.references.join(", ")} · PDF ${slide.page}쪽`} />
    </figure>;
  return <section className="bank-slides bank-jokbo-slides" aria-label={title}>
    <h2>{title}</h2>
    {primary.length ? primary.map(image) : collapseReferences ? <details className="bank-answer-context" onToggle={event => setExpanded(event.currentTarget.open)}>
      <summary>참고 족보 {extra.length}장</summary>
      {expanded ? extra.map(image) : null}
    </details> : extra.map(image)}
    {primary.length && extra.length ? <details className="bank-answer-context" onToggle={event => setExpanded(event.currentTarget.open)}>
      <summary>추가 참고 족보 {extra.length}장</summary>
      {expanded ? extra.map(image) : null}
    </details> : null}
  </section>;
}
