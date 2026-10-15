import { SlideImage } from "../SlideImage";
import type { SlidePreloader } from "../slidePreload";
import type { BankAnswer } from "../types/bank";

export function BankJokboSlides({ slides, preload }: { slides: BankAnswer["jokboSlides"]; preload?: SlidePreloader }) {
  if (!slides?.length) return null;
  return <section className="bank-slides bank-jokbo-slides" aria-label="참고한 족보">
    <h2>참고한 족보</h2>
    {slides.map(slide => <figure key={`${slide.pdfFilename}:${slide.page}`}>
      <figcaption><b>{slide.references.join(" · ")}</b><br />{slide.pdfFilename} · PDF {slide.page}쪽{" · "}
        <a href={slide.url} target="_blank" rel="noreferrer">지면 크게 보기 ↗</a>
      </figcaption>
      <SlideImage src={slide.url} preload={preload} alt={`족보 ${slide.references.join(", ")} · PDF ${slide.page}쪽`} />
    </figure>)}
  </section>;
}
