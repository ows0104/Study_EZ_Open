import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, openSignedFile } from "../api";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import { Stem } from "../lecture/Stem";
import type { BankFormat, BankFullQuestion, BankReviewBoard, BankReviewCard, BankReviewGroup } from "../types/bank";

const decisionLabel = { edit: "수정함", accept: "검토 완료", delete: "제외함" };
const formats: BankFormat[] = ["basic", "cloze", "list", "ox", "mcq", "multi_select", "matching", "sequence"];
const formatLabels: Record<BankFormat, string> = {
  basic: "기본", cloze: "빈칸", list: "목록", ox: "OX", mcq: "객관식", multi_select: "복수 선택",
  matching: "짝짓기", sequence: "순서",
};
const directionLabels: Record<string, string> = {
  direct: "직접", reverse: "역방향", mechanism: "기전", discrimination: "구별",
  integration: "통합", sequence: "순서", trap: "함정",
};

export function BankCardReview() {
  const { subject, runId } = useParams();
  const [search] = useSearchParams();
  const focusId = subject && runId ? search.get("question") ?? "" : "";
  const [board, setBoard] = useState<BankReviewBoard | null>(null);
  const [error, setError] = useState("");
  const [showDone, setShowDone] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const load = useCallback(async () => {
    const query = new URLSearchParams();
    if (subject) query.set("subject", subject);
    if (runId) query.set("runId", runId);
    if (subject && (showAll || focusId)) query.set("all", "true");
    try {
      const next = await api<BankReviewBoard>(`/api/admin/bank-review?${query}`);
      setBoard(next);
      setError("");
    } catch (cause) { setError((cause as Error).message); }
  }, [subject, runId, showAll, focusId]);
  useEffect(() => { setBoard(null); void load(); }, [load]);
  async function changed() { bumpPreviewVersion(); await load(); }
  async function openSource(group: BankReviewGroup, assetId: string) {
    try { await openSignedFile(`/api/lectures/${encodeURIComponent(group.subject)}/${encodeURIComponent(group.runId)}/files/${encodeURIComponent(assetId)}`); }
    catch (cause) { setError((cause as Error).message); }
  }
  const visible = (card: BankReviewCard) => focusId && !showAll
    ? card.question.question_id === focusId : showDone || showAll || !card.edit;
  return <section className="card-review bank-card-review">
    <h2>Main-Quiz 문항 검토</h2>
    <p className="card-review-note">검증으로 제외된 문항과 외부지식 검토에서 틀림·의심으로 표시된 문항을 확인합니다.
      수정 후 검증을 통과하면 바로 학습에 반영됩니다. 같은 원문을 다시 정리해도 수정 내용이 유지됩니다.</p>
    <div className="card-review-actions">
      {board ? <span>미검토 {board.open}개 · 처리한 문항 {board.done}개</span> : null}
      <button onClick={() => void load()}>새로 불러오기</button>
      <label><input type="checkbox" checked={showDone} onChange={e => setShowDone(e.target.checked)} /> 처리한 문항도 보기</label>
      {subject ? <label><input type="checkbox" checked={showAll} onChange={e => setShowAll(e.target.checked)} /> 이 강의 전체 문항</label> : null}
    </div>
    {error ? <p className="notice is-error" role="alert">{error}</p> : null}
    {!board && !error ? <p>불러오는 중…</p> : null}
    {board && !board.banks.some(g => g.cards.some(visible)) ? <p>{focusId && !showAll
      ? "이 문항이 없습니다. 다시 생성되었거나 제외되었을 수 있습니다." : "검토할 문항이 없습니다."}</p> : null}
    {board?.banks.map(group => <div key={`${group.subject}/${group.runId}`}>
      {group.cards.some(visible) ? <>
        <h3>{group.subject} · {group.date} · {group.title}</h3>
        {group.sources?.length ? <div className="card-review-actions">{group.sources.map(s =>
          <button key={s.id} onClick={() => void openSource(group, s.assetId)}>{s.id} · {s.kind === "notes_current" ? "강의 필기" : "족보"} 열기</button>)}</div> : null}
      </> : null}
      {group.cards.filter(visible).map(card => <ReviewRow
        key={`${group.buildId}/${card.question.question_id}`}
        group={group} card={card} onChanged={changed} focus={card.question.question_id === focusId} />)}
    </div>)}
  </section>;
}

function ReviewRow({ group, card, onChanged, focus }: {
  group: BankReviewGroup; card: BankReviewCard; onChanged: () => Promise<void>; focus: boolean;
}) {
  const [editing, setEditing] = useState(focus);
  const row = useRef<HTMLElement>(null);
  useEffect(() => { if (focus) row.current?.scrollIntoView({ block: "start" }); }, [focus]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const q = card.question;
  const path = `/api/admin/lectures/${encodeURIComponent(group.subject)}/${encodeURIComponent(group.runId)}/bank/cards/${encodeURIComponent(q.question_id)}`;
  async function save(action: "edit" | "accept" | "delete" | "reset", question?: BankFullQuestion) {
    setBusy(true); setError("");
    try {
      await api(path, { method: "PUT", body: JSON.stringify({ action, question, buildId: group.buildId, expectedQuestion: q }) });
      setEditing(false);
      await onChanged();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  const review = card.medicalReview;
  return <article ref={row} className="card-review-row">
    <header className="card-review-head">
      <strong>{q.question_id}</strong><span>{formatLabels[q.format] ?? q.format} · {directionLabels[q.retrieval_direction] ?? q.retrieval_direction}</span>
      {card.errors.length ? <span className="tag is-warn">검증으로 제외됨</span> : null}
      {review && review.verdict !== "ok" ? <span className="tag is-warn">외부지식 · {review.verdict === "wrong" ? "틀림" : "의심"}</span> : null}
      {card.edit ? <span className="tag">{decisionLabel[card.edit.action]}</span> : null}
    </header>
    {card.errors.length ? <ul className="card-review-why">{card.errors.map((e, i) => <li key={i}>{e}</li>)}</ul> : null}
    {review && review.verdict !== "ok" ? <p className="card-review-why">
      {card.edit?.action === "edit" ? "수정 전 외부지식 검토" : "외부지식 검토"}: {review.note}
      {review.suggested_answer ? <><br />제안된 답: {review.suggested_answer}</> : null}
    </p> : null}
    {editing ? <QuestionEditor question={q} group={group} busy={busy} onSave={next => save("edit", next)} onCancel={() => setEditing(false)} /> : <>
      <dl className="card-review-card">
        <dt>질문</dt><dd><Stem text={q.question ?? "원문 없음"} />
          {q.options?.length ? <ul>{q.options.map((o, i) => <li key={i}>{o.id}. {o.text}{q.correct_option_ids.includes(o.id) ? " ✓" : ""}</li>)}</ul> : null}
          {q.matching_left?.length ? <p>왼쪽: {q.matching_left.join(" · ")}<br />오른쪽: {q.matching_right.join(" · ")}</p> : null}
          {q.sequence_items?.length ? <p>항목: {q.sequence_items.join(" · ")}</p> : null}
        </dd>
        <dt>정답</dt><dd><Stem text={q.answer ?? ""} />
          {q.answer_pairs?.map((p, i) => <div key={i}>{p.left} → {p.right}</div>)}
          {q.correct_order?.length ? <p>{q.correct_order.join(" → ")}</p> : null}
        </dd>
        <dt>채점 단위</dt><dd>{q.answer_units?.join(" · ")}</dd>
        <dt>선행 문항</dt><dd>{q.prerequisites?.join(", ") || "없음"}</dd>
        <dt>출처</dt><dd>{q.source_refs?.map((r, i) => <div key={i}>{r.source_id} · {r.locator}</div>)}</dd>
      </dl>
      {card.edit ? <details className="card-review-was"><summary>원본과 처리 기록</summary>
        <p>{card.edit.by} · {new Date(card.edit.at).toLocaleString("ko-KR")}</p>
        <Stem text={card.edit.original.question ?? ""} /><Stem text={card.edit.original.answer ?? ""} />
        <p>원래 선행 문항: {card.edit.original.prerequisites?.join(", ") || "없음"}</p>
        {card.edit.original.options?.map((o, i) => <div key={i}>{o.id}. {o.text}</div>)}
        {card.edit.original.matching_right?.length ? <p>원래 오른쪽 항목: {card.edit.original.matching_right.join(" · ")}</p> : null}
        {card.edit.original.answer_pairs?.map((p, i) => <div key={i}>{p.left} → {p.right}</div>)}
        {card.edit.original.correct_order?.length ? <p>원래 순서: {card.edit.original.correct_order.join(" → ")}</p> : null}
      </details> : null}
      <div className="card-review-actions">
        <button className="is-primary" disabled={busy || !q.question} onClick={() => setEditing(true)}>문항 수정</button>
        {!card.errors.length && !card.edit ? <button disabled={busy} onClick={() => void save("accept")}>그대로 사용</button> : null}
        {card.edit?.action !== "delete" ? <button disabled={busy} onClick={() => void save("delete")}>학습에서 제외</button> : null}
        {card.edit ? <button disabled={busy} onClick={() => void save("reset")}>원본으로 되돌리기</button> : null}
        <Link to={`/admin/bank-cards/${encodeURIComponent(group.subject)}/${encodeURIComponent(group.runId)}`}>이 강의 문항 보기</Link>
      </div>
    </>}
    {error ? <p className="notice is-error bank-edit-error" role="alert">{error}</p> : null}
  </article>;
}

function Lines({ label, values, onChange, hint }: { label: string; values: string[]; onChange: (value: string[]) => void; hint?: string }) {
  // Keep blank lines while typing so Enter can create the next item.
  return <label>{label}<textarea rows={3} value={values.join("\n")} onChange={e => onChange(e.target.value.split("\n"))} />
    <small>{hint ?? "한 줄에 한 항목"}</small></label>;
}

function Pairs({ label, values, onChange, leftLabel, rightLabel }: {
  label: string; values: [string, string][]; onChange: (value: [string, string][]) => void; leftLabel: string; rightLabel: string;
}) {
  return <fieldset className="bank-edit-pairs"><legend>{label}</legend>
    {values.map((pair, i) => <div key={i}>
      <input aria-label={`${leftLabel} ${i + 1}`} placeholder={leftLabel} value={pair[0]} onChange={e => onChange(values.map((p, j) => j === i ? [e.target.value, p[1]] : p))} />
      <input aria-label={`${rightLabel} ${i + 1}`} placeholder={rightLabel} value={pair[1]} onChange={e => onChange(values.map((p, j) => j === i ? [p[0], e.target.value] : p))} />
      <button type="button" aria-label={`${label} ${i + 1} 삭제`} onClick={() => onChange(values.filter((_, j) => j !== i))}>×</button>
    </div>)}
    <button type="button" onClick={() => onChange([...values, ["", ""]])}>항목 추가</button>
  </fieldset>;
}

function QuestionEditor({ question, group, busy, onSave, onCancel }: {
  question: BankFullQuestion; group: BankReviewGroup; busy: boolean; onSave: (q: BankFullQuestion) => Promise<void>; onCancel: () => void;
}) {
  const [q, setQ] = useState<BankFullQuestion>(() => structuredClone(question));
  function field<K extends keyof BankFullQuestion>(key: K, value: BankFullQuestion[K]) { setQ(prev => ({ ...prev, [key]: value })); }
  function format(value: BankFormat) {
    setQ(prev => ({ ...prev, format: value,
      options: value === "mcq" || value === "multi_select" ? prev.options : [],
      correct_option_ids: value === "mcq" || value === "multi_select" ? prev.correct_option_ids : [],
      matching_left: value === "matching" ? prev.matching_left : [], matching_right: value === "matching" ? prev.matching_right : [],
      answer_pairs: value === "matching" ? prev.answer_pairs : [],
      sequence_items: value === "sequence" ? prev.sequence_items : [], correct_order: value === "sequence" ? prev.correct_order : [],
    }));
  }
  const trim = (items: string[]) => items.map(x => x.trim()).filter(Boolean);
  function cleaned(): BankFullQuestion {
    return { ...q, question: q.question.trim(), answer: q.answer.trim(),
      answer_units: trim(q.answer_units), prerequisites: trim(q.prerequisites),
      matching_left: trim(q.matching_left), matching_right: trim(q.matching_right),
      sequence_items: trim(q.sequence_items), correct_order: trim(q.correct_order), correct_option_ids: trim(q.correct_option_ids) };
  }
  return <form className="card-review-edit" onSubmit={e => { e.preventDefault(); void onSave(cleaned()); }}>
    <fieldset disabled={busy} className="bank-edit-fields">
      <label>개념<select value={q.concept_id} onChange={e => field("concept_id", e.target.value)}>{group.concepts.map(c => <option key={c.id} value={c.id}>{c.id} · {c.title}</option>)}</select></label>
      <label>문항 형식<select value={q.format} onChange={e => format(e.target.value as BankFormat)}>{formats.map(f => <option key={f} value={f}>{formatLabels[f]}</option>)}</select></label>
      <label>회상 방향<select value={q.retrieval_direction} onChange={e => field("retrieval_direction", e.target.value)}>{Object.entries(directionLabels).map(([d, text]) => <option key={d} value={d}>{text}</option>)}</select></label>
      <label>질문<textarea rows={4} required value={q.question} onChange={e => field("question", e.target.value)} /></label>
      {q.format === "cloze" ? <small>빈칸은 {"{{c1}}"}, {"{{c2}}"}로 표시하고 채점 단위는 빈칸 등장 순서로 적으세요.</small> : null}
      <label>정답<textarea rows={3} required value={q.answer} onChange={e => field("answer", e.target.value)} /></label>
      <Lines label="채점 단위" values={q.answer_units} onChange={v => field("answer_units", v)} />
      <fieldset><legend>선행 문항{q.retrieval_direction === "integration" ? " · 통합 문항은 필수" : ""}</legend>
        <small>기초가 되는 문항을 선택하세요.</small>
        <div className="bank-prerequisites">{group.questions.filter(p => p.id !== q.question_id).map(p => <label key={p.id}>
          <input type="checkbox" checked={q.prerequisites.includes(p.id)} disabled={!p.available && !q.prerequisites.includes(p.id)}
            onChange={e => field("prerequisites", e.target.checked ? [...q.prerequisites, p.id] : q.prerequisites.filter(id => id !== p.id))} />
          <span>{p.id} · {p.question}{p.available ? "" : " (학습에서 제외됨)"}</span>
        </label>)}</div>
      </fieldset>
      {q.format === "mcq" || q.format === "multi_select" ? <>
        <Pairs label="선택지" values={q.options.map(o => [o.id, o.text])} leftLabel="선택지 ID" rightLabel="선택지 내용" onChange={v => field("options", v.map(([id, text]) => ({ id, text })))} />
        <Lines label="정답 선택지 ID" values={q.correct_option_ids} onChange={v => field("correct_option_ids", v)} />
      </> : null}
      {q.format === "matching" ? <>
        <Lines label="왼쪽 항목" values={q.matching_left} onChange={v => field("matching_left", v)} />
        <Lines label="오른쪽 항목" values={q.matching_right} onChange={v => field("matching_right", v)} hint="한 줄에 한 항목 · 중복 값을 제거한 뒤 정답 쌍도 맞춰 주세요." />
        <Pairs label="정답 쌍" values={q.answer_pairs.map(p => [p.left, p.right])} leftLabel="왼쪽 값" rightLabel="오른쪽 값" onChange={v => field("answer_pairs", v.map(([left, right]) => ({ left, right })))} />
      </> : null}
      {q.format === "sequence" ? <>
        <Lines label="순서 항목" values={q.sequence_items} onChange={v => field("sequence_items", v)} />
        <Lines label="정답 순서" values={q.correct_order} onChange={v => field("correct_order", v)} />
      </> : null}
      <details><summary>중요도·난이도·출처</summary>
        <label>출처 충돌<select value={q.conflict_id} onChange={e => field("conflict_id", e.target.value)}>
          <option value="">없음</option>
          {group.conflicts?.map(c => <option key={c.id} value={c.id}>{c.id} · {c.description}</option>)}
        </select></label>
        <label>단계<select value={q.tier} onChange={e => field("tier", e.target.value as BankFullQuestion["tier"])}>{["Core", "Advanced", "Optional"].map(t => <option key={t}>{t}</option>)}</select></label>
        <label>중요도<input type="number" min={1} max={5} value={q.importance} onChange={e => field("importance", Number(e.target.value))} /></label>
        <label>난이도<input type="number" min={1} max={5} value={q.item_difficulty} onChange={e => field("item_difficulty", Number(e.target.value))} /></label>
        <Pairs label="출처" values={q.source_refs.map(r => [r.source_id, r.locator])} leftLabel="출처 ID (S1·S2·EXT)" rightLabel="쪽·위치" onChange={v => field("source_refs", v.map(([source_id, locator]) => ({ source_id, locator })))} />
        <label>출제 근거<textarea value={q.exam_rationale} onChange={e => field("exam_rationale", e.target.value)} /></label>
      </details>
      <div className="card-review-actions"><button className="is-primary" type="submit">{busy ? "검증하고 저장 중…" : "검증하고 저장"}</button><button type="button" onClick={onCancel}>취소</button></div>
    </fieldset>
  </form>;
}
