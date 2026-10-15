import { useState } from "react";
import { SlideImage } from "../SlideImage";
import type { SlidePreloader } from "../slidePreload";
import type { BankSlide } from "../types/bank";

export function splitSlides(slides: BankSlide[]) {
  const marked = slides.filter(slide => slide.primary);
  // 옛 API와 쪽 정보가 없는 문항도 첫 장은 바로 볼 수 있다.
  const primary = marked.length ? marked : slides.slice(0, 1);
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
    {extra.length ? <details className="bank-answer-context bank-extra-slides"
      onToggle={event => setExpanded(event.currentTarget.open)}>
      <summary>추가 참고 슬라이드 {extra.length}장</summary>
      {expanded ? extra.map(image) : null}
    </details> : null}
  </section>;
}
