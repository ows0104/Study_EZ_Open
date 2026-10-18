import { SlideImage } from "../SlideImage";
import { useState } from "react";
import type { SlidePreloader } from "../slidePreload";
import type { BankAnswer } from "../types/bank";

function referenceLabel(reference: string) {
  return reference.replace(/\b((?:19|20)\d{2})(?!\d)\s*년?\s*/, "$1년 · ");
}

type ExamSlide = NonNullable<BankAnswer["jokboSlides"]>[number];

function OriginalPage({ slide, preload }: { slide: ExamSlide; preload?: SlidePreloader }) {
  const [expanded, setExpanded] = useState(false);
  return <details className="bank-answer-context" onToggle={event => setExpanded(event.currentTarget.open)}>
    <summary>원본 PDF 펼쳐보기 · {slide.pdfFilename} · {slide.page}쪽</summary>
    {expanded ? <SlideImage src={slide.url} preload={preload}
      alt={`족보 ${slide.references.join(", ")} · PDF ${slide.page}쪽`} /> : null}
  </details>;
}

export function BankJokboSlides({ slides, preload }: {
  slides: BankAnswer["jokboSlides"]; preload?: SlidePreloader;
}) {
  if (!slides?.length) return null;
  const title = slides.some(slide => slide.primary) ? "핵심 근거 · 족보" : "참고 족보 문제";
  const questions = [...new Map(slides.flatMap(slide => slide.questions ?? [])
    .map(question => [JSON.stringify([question.reference, question.stem, question.options]), question])).values()];
  return <section className="bank-slides bank-jokbo-slides" aria-label={title}>
    <h2>{title}</h2>
    {questions.map((question, index) => <article className="bank-jokbo-question" key={index}>
      <p className="bank-note">{referenceLabel(question.reference)}</p>
      <p className="bank-jokbo-stem">{question.stem}</p>
      {question.options.length ? <ul>{question.options.map((option, i) => <li key={i}>{option}</li>)}</ul> : null}
      {question.needsFigure ? <p className="bank-note">그림·표는 아래 원본 PDF에서 확인하세요.</p> : null}
    </article>)}
    {!questions.length ? <p className="bank-note">문제 본문이 아직 연결되지 않았습니다. 원본 PDF를 펼쳐 확인하세요.</p> : null}
    {slides.map(slide => <figure key={`${slide.pdfFilename}:${slide.page}`}>
      <figcaption className="bank-note">{slide.references.map(referenceLabel).join(" · ")}</figcaption>
      <OriginalPage slide={slide} preload={preload} />
    </figure>)}
  </section>;
}
