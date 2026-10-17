import { useEffect, useState } from "react";
import { api } from "../api";
import { SlideImage } from "../SlideImage";
import type { BankSlide } from "../types/bank";
import "./personal-question-slides.css";

type SlideChoice = BankSlide & { assetId: string };
type Choices = { slides: SlideChoice[]; selectedAssetIds: string[] };

export function PersonalQuestionSlides({ base, sourceQuestionId, selected, onChange, busy }: {
  base: string; sourceQuestionId?: string; selected: string[] | null;
  onChange: (ids: string[] | null) => void; busy: boolean;
}) {
  const [choices, setChoices] = useState<Choices | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setChoices(null); setError(""); onChange(null);
    const query = sourceQuestionId ? `?sourceQuestionId=${encodeURIComponent(sourceQuestionId)}` : "";
    void api<Choices>(`${base}/personal-question-slides${query}`, { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return;
      setChoices(value); onChange(value.selectedAssetIds);
    }).catch(cause => { if (!controller.signal.aborted) setError((cause as Error).message); });
    return () => controller.abort();
  }, [base, sourceQuestionId, retry, onChange]);
  const label = (slide: SlideChoice) => `${slide.sourceId && slide.sourceId !== "self" ? `${slide.sourceFilename || "다른 강의"} · ` : ""}PDF ${slide.page}쪽`;
  return <section className="personal-question-slides" aria-label="참고 슬라이드">
    <h3>참고 슬라이드</h3>
    {error ? <p role="alert">{error} <button type="button" disabled={busy} onClick={() => setRetry(value => value + 1)}>다시 불러오기</button></p>
      : !choices ? <p role="status">슬라이드를 불러오는 중…</p> : <>
        {sourceQuestionId ? <small>현재 문제의 슬라이드를 자동 선택했습니다. 선택을 바꾸거나 삭제할 수 있습니다.</small> : null}
        <p>{selected?.length ? `${selected.length}장 연결` : "연결된 슬라이드 없음"}</p>
        <div className="personal-selected-slides">{choices.slides.filter(slide => selected?.includes(slide.assetId)).map(slide =>
          <figure key={slide.assetId}>
            <SlideImage src={slide.url} alt={label(slide)} loading="lazy" />
            <figcaption>{label(slide)} <button type="button" className="is-quiet" disabled={busy}
              aria-label={`${label(slide)} 연결 삭제`} onClick={() => onChange(selected!.filter(id => id !== slide.assetId))}>삭제</button></figcaption>
          </figure>)}</div>
        {selected?.length ? <button type="button" className="is-quiet" disabled={busy} onClick={() => onChange([])}>연결 모두 삭제</button> : null}
        {choices.slides.length ? <details><summary>슬라이드 선택·변경</summary>
          <fieldset disabled={busy}><legend>참고할 슬라이드 선택</legend>
            {choices.slides.map(slide => <label key={slide.assetId}><input type="checkbox" checked={selected?.includes(slide.assetId) ?? false}
              onChange={event => onChange(event.target.checked ? [...(selected ?? []), slide.assetId] : selected!.filter(id => id !== slide.assetId))} />{label(slide)}</label>)}
          </fieldset></details> : <small>등록된 슬라이드가 없습니다.</small>}
      </>}
  </section>;
}
