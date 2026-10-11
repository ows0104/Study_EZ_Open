import { Link } from "react-router-dom";
import { Stem } from "../lecture/Stem";
import { SlideImage } from "../SlideImage";
import type { LearningFeedback as FeedbackValue, SourceRef } from "../types/learning";

export function SourceRefs({ refs }: { refs?: SourceRef[] }) {
  return refs?.length ? <small className="learning-muted">{refs.map(r => `${r.source_id === "EXT" ? "외부 지식" : r.source_id} ${r.locator}`).join(" · ")}</small> : null;
}

export function LearningFeedback({ value, picked = [] }: { value: FeedbackValue; picked?: string[] }) {
  const explanationOnly = value.answer === undefined && value.correct === undefined;
  const explanations = value.optionExplanations ?? [];
  const focused = explanations.filter(e => value.correctOptionIds?.includes(e.option_id) || picked.includes(e.option_id));
  const rest = explanations.filter(e => !focused.includes(e));
  const showExplanation = (e: typeof explanations[number]) => <div className="learning-option-explanation" key={e.option_id}>
    <b>{e.option_id}</b><p><Stem text={e.text} /></p></div>;
  return <section className="learning-feedback" aria-label={explanationOnly ? "학습 설명" : "정답과 해설"}>
    <div className="learning-answer-heading"><h3>{explanationOnly ? "기억할 내용" : "정답"}</h3>
      {value.correct != null ? <span className={`learning-result ${value.correct ? "is-correct" : "is-wrong"}`}>{value.correct ? "✓ 정답" : "오답"}</span> : null}</div>
    <div className="learning-answer">
      {value.answerPairs?.length ? <dl className="learning-answer-pairs">{value.answerPairs.map((p, i) => <div key={i}><dt>{p.left}</dt><dd>→ {p.right}</dd></div>)}</dl>
        : value.correctOrder?.length ? <ol>{value.correctOrder.map((item, i) => <li key={i}>{item}</li>)}</ol>
        : <p><Stem text={explanationOnly ? value.minimum : value.answer ?? value.minimum} /></p>}
    </div>
    {focused.length ? <div className="learning-answer-explanations">{focused.map(showExplanation)}</div> : null}
    {rest.length ? <details><summary>나머지 선지 해설 · {rest.length}개</summary>{rest.map(showExplanation)}</details> : null}
    {value.answerUnits?.length && !explanations.length ? <details><summary>풀이·채점 기준</summary><ul>{value.answerUnits.map((a, i) => <li key={i}><Stem text={a} /></li>)}</ul></details> : null}
    {value.explanation ? explanationOnly ? <p><Stem text={value.explanation} /></p>
      : <details><summary>개념 설명</summary><p><Stem text={value.explanation} /></p><p><b>기억할 내용</b> <Stem text={value.minimum} /></p></details> : null}
    {value.sourceConflict ? <p className="learning-warning">자료 충돌: {value.sourceConflict}</p> : null}
    {value.medicalReview && value.medicalReview.verdict !== "ok" ? <p className="learning-warning">정답 검토 · {value.medicalReview.note}<br />{value.medicalReview.suggested_answer}</p> : null}
  </section>;
}

export function LearningReferences({ value, subject, runId }: { value: FeedbackValue; subject?: string; runId?: string }) {
  const slides = value.slides ?? [];
  const [first, ...following] = slides;
  const renderSlide = (slide: typeof first) => <figure key={slide.page}>
    <figcaption><span>강의록 {slide.page}쪽</span><a href={slide.url} target="_blank" rel="noreferrer">크게 보기 ↗</a></figcaption>
    <SlideImage src={slide.url} alt={`강의록 참고 슬라이드 ${slide.page}쪽`} />
  </figure>;
  return <aside className="learning-references" aria-label="참고 슬라이드">
    <header><h3>참고 슬라이드</h3>{value.sourceDocument ? <a href={value.sourceDocument.url} target="_blank" rel="noreferrer">강의록 열기 ↗</a>
      : subject && runId ? <Link target="_blank" to={`/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`}>강의 자료 ↗</Link> : null}</header>
    {first ? renderSlide(first) : <p className="learning-muted">{value.slideStatus || "이 문항의 슬라이드가 아직 준비되지 않았어요."}</p>}
    {following.length ? <details><summary>다른 참고 슬라이드 · {following.length}장</summary>{following.map(renderSlide)}</details> : null}
    {Boolean(slides.length) && value.slideStatus ? <p className="learning-muted">{value.slideStatus}</p> : null}
    {value.missingSlidePages?.length ? <p className="learning-muted">이미지 준비 중 · {value.missingSlidePages.join(", ")}쪽</p> : null}
    <SourceRefs refs={value.sourceRefs} />
  </aside>;
}
