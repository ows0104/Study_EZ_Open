import { useState } from "react";
import { SlideImage } from "../SlideImage";
import type { SlidePreloader } from "../slidePreload";
import type { BankSlide } from "../types/bank";

export function splitSlides(slides: BankSlide[]) {
  const marked = slides.filter(slide => slide.primary);
  // 내용 대조 결과가 없는 문항을 첫 쪽으로 대신하지 않는다.
  const primary = marked;
  const pages = new Set(primary.map(slide => slide.page));
  return { primary, extra: slides.filter(slide => !pages.has(slide.page)) };
}

export function BankSlides({ slides, preload }: { slides: BankSlide[]; preload?: SlidePreloader }) {
  const [expanded, setExpanded] = useState(false);
  const { primary, extra } = splitSlides(slides);
  if (!slides.length) return null;
  const image = (slide: BankSlide) => (
    <SlideImage key={slide.page} preload={preload} src={slide.url} alt={`필기 ${slide.page}쪽`} />
  );
  return <section className="bank-slides" aria-label="근거 슬라이드">
    {primary.map(image)}
    {!primary.length ? <p className="bank-note">확인된 핵심 근거 슬라이드가 없습니다.</p> : null}
    {extra.length ? <details className="bank-answer-context bank-extra-slides"
      onToggle={event => setExpanded(event.currentTarget.open)}>
      <summary>추가 참고 슬라이드 {extra.length}장</summary>
      {expanded ? extra.map(image) : null}
    </details> : null}
  </section>;
}
