import { useState } from "react";
import { SlideImage } from "../SlideImage";
import type { SlidePreloader } from "../slidePreload";
import type { BankSlide } from "../types/bank";

export function splitSlides(slides: BankSlide[]) {
  const marked = slides.filter(slide => slide.primary);
  // 내용 대조 결과가 없는 문항을 첫 쪽으로 대신하지 않는다.
  const primary = marked;
  const pages = new Set(primary.map(slideKey));
  return { primary, extra: slides.filter(slide => !pages.has(slideKey(slide))) };
}

function slideKey(slide: BankSlide) {
  return `${slide.sourceId || "self"}:${slide.page}`;
}

export function BankSlides({ slides, preload, statusKnown = false }: { slides: BankSlide[]; preload?: SlidePreloader; statusKnown?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const { primary, extra } = splitSlides(slides);
  if (!slides.length) return null;
  const image = (slide: BankSlide) => (
    <figure key={slideKey(slide)} className="bank-evidence-slide">
      {slide.sourceFilename ? <figcaption className="bank-note">
        {slide.sourceId && slide.sourceId !== "self" ? "다른 강의 · " : ""}
        {slide.sourceFilename} · PDF {slide.page}쪽
      </figcaption> : null}
      <SlideImage preload={preload} src={slide.url}
        alt={slide.sourceId && slide.sourceId !== "self" ? `${slide.sourceFilename || "다른 강의"} ${slide.page}쪽` : `필기 ${slide.page}쪽`} />
    </figure>
  );
  return <section className="bank-slides" aria-label="근거 슬라이드">
    {primary.map(image)}
    {!primary.length && !statusKnown ? <p className="bank-note">확인된 핵심 근거 슬라이드가 없습니다.</p> : null}
    {extra.length ? <details className="bank-answer-context bank-extra-slides"
      onToggle={event => setExpanded(event.currentTarget.open)}>
      <summary>추가 참고 슬라이드 {extra.length}장</summary>
      {expanded ? extra.map(image) : null}
    </details> : null}
  </section>;
}
