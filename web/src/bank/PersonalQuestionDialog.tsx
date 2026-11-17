import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import type { BankAnswer, BankFormat, BankQuestion } from "../types/bank";
import { FEEDBACK } from "./feedback";

type Shape = {
  question: string; answer: string; explanation?: string;
  /** Main-Quiz 형식 바꾸기(2026-11-17)부터. 기존 은행 응답에는 없다. */
  format?: BankFormat; mcqMode?: McqMode; options?: { id: string; text: string }[]; correctOptionIds?: string[];
};
type McqMode = "none" | "recall_first" | "comparison";
type Snapshot = {
  original: Shape;
  draft: Shape;
  edited: boolean;
  revision: string;
  comment: string;
  personalAdded?: boolean;
  /** Main-Quiz: false면 개인 수정 없이 제보만 받는다(문제은행과 연결된 판). 기존 은행 응답에는 없다. */
  editable?: boolean;
  /** Main-Quiz: 수정창에서 고를 수 있는 형식. 비었거나 없으면 형식은 그대로 두고 글만 고친다. */
  formats?: BankFormat[];
};
export type PersonalQuestionResult = { question: BankQuestion; answer: BankAnswer; reported: boolean; highlighted?: boolean };

const FORMAT_LABEL: Partial<Record<BankFormat, string>> = {
  basic: "주관식", list: "나열", cloze: "빈칸", ox: "OX", mcq: "객관식", multi_select: "복수 선택",
};
const CHOICE: BankFormat[] = ["mcq", "multi_select"];
/** 판 문항과 같은 빈칸 표기: {정답} 한 겹(studyez_contracts.bank.cloze.INLINE). */
const INLINE = /(?<!\{)\{([^{}\r\n]+)\}(?!\})/g;
const lines = (text: string) => text.split("\n").map(line => line.trim()).filter(Boolean);

export function PersonalQuestionDialog({ base, path: direct, questionId, answerVisible, onClose, onSaved }: {
  /** 기존 은행 API 기준 주소. Main-Quiz는 `path`로 수정 주소를 바로 준다. */
  base?: string; path?: string; questionId: string; answerVisible: boolean; onClose: () => void;
  onSaved: (result: PersonalQuestionResult, reset: boolean) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [format, setFormat] = useState<BankFormat>("basic");
  const [choices, setChoices] = useState("");
  const [correctIds, setCorrectIds] = useState<string[]>([]);
  const [mcqMode, setMcqMode] = useState<McqMode>("comparison");
  const [category, setCategory] = useState("content");
  const [comment, setComment] = useState("");
  const [report, setReport] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = direct ?? `${base}/questions/${encodeURIComponent(questionId)}/personal`;
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    let live = true;
    api<Snapshot>(path).then(next => {
      if (!live) return;
      setSnapshot(next); setQuestion(next.draft.question); setAnswer(next.draft.answer);
      setExplanation(next.draft.explanation ?? "");
      setFormat(next.draft.format ?? next.original.format ?? "basic");
      setChoices((next.draft.options ?? []).map(option => option.text).join("\n"));
      const options = next.draft.options ?? [];
      // 보기는 화면에서 1, 2, 3…으로 다시 매긴다. 판 보기 ID가 A·B여도 같은 순서로 고른 것을 옮긴다.
      setCorrectIds((next.draft.correctOptionIds ?? []).map(id => String(options.findIndex(option => option.id === id) + 1)).filter(id => id !== "0"));
      setMcqMode(next.draft.mcqMode === "recall_first" ? "recall_first" : "comparison");
      setComment(next.comment);
    }).catch(cause => { if (live) setError((cause as Error).message); });
    return () => { live = false; };
  }, [path]);
  useEffect(() => { if (snapshot) dialog.current?.querySelector("textarea")?.focus(); }, [snapshot]);
  const originalFormat = snapshot?.original.format ?? "basic";
  const formats = snapshot?.formats ?? [];
  // 원래 형식이면 지금까지처럼 글만 고친다. 다른 형식이면 형식·구조·해설을 함께 저장한다.
  const restructured = formats.length > 0 && format !== originalFormat;
  const choice = CHOICE.includes(format);
  const changed = snapshot && (restructured || question.trim() !== snapshot.original.question || answer.trim() !== snapshot.original.answer
    || (snapshot.personalAdded && explanation.trim() !== (snapshot.original.explanation ?? "")));
  const noteChanged = snapshot && comment.trim() !== snapshot.comment;
  const editable = snapshot?.editable !== false;
  function changeFormat(next: BankFormat) {
    if (format === "cloze" && next !== "cloze") setQuestion(text => text.replace(INLINE, "$1"));
    if (next === "ox" && !/^[OX]$/i.test(answer.trim())) setAnswer("");
    if (CHOICE.includes(next) && !lines(choices).length && answer.trim()) { setChoices(answer.trim()); setCorrectIds(["1"]); }
    if (next === "mcq" && correctIds.length > 1) setCorrectIds(correctIds.slice(0, 1));
    setFormat(next);
  }
  function structure() {
    return {
      format, mcq_mode: choice ? mcqMode : "none", explanation,
      options: choice ? lines(choices).map((text, index) => ({ id: String(index + 1), text })) : [],
      correct_option_ids: choice ? correctIds : [],
    };
  }
  async function save(reset = false) {
    if (busy || !snapshot) return;
    setBusy(true); setError("");
    try {
      const result = await api<PersonalQuestionResult>(path, { method: "PUT", body: JSON.stringify({
        action: reset ? "reset" : "save", revision: snapshot.revision,
        question: reset ? snapshot.original.question : question,
        answer: reset ? snapshot.original.answer : restructured && (format === "cloze" || choice) ? "" : answer,
        report: !reset && report, category, comment,
        ...(snapshot.personalAdded ? { explanation } : {}),
        ...(!reset && restructured ? { structure: structure() } : {}),
      }) });
      onSaved(result, reset);
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  const formatLabel = (value: BankFormat) => FORMAT_LABEL[value] ?? value;
  return createPortal(<dialog ref={dialog} className="bank-feedback-dialog" aria-labelledby="bank-feedback-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <header><h2 id="bank-feedback-title">{snapshot?.personalAdded ? "내가 추가한 문제 수정" : editable ? "문제 수정·제보" : "문제 제보"}</h2>
        <button type="button" className="is-quiet" aria-label="수정창 닫기" disabled={busy} onClick={onClose}>×</button></header>
      <p className="bank-feedback-id">문항 {questionId}</p>
      {editable ? <p className="bank-personal-hint">수정 내용은 내 계정에만 적용됩니다. 다른 사람의 문제는 바뀌지 않습니다.</p>
        : <p className="bank-personal-hint">이 문항은 개인 수정 없이 제보만 보낼 수 있습니다. 제보는 관리자에게 전달됩니다.</p>}
      {snapshot && !snapshot.personalAdded ? <p className="bank-personal-hint">수정 내용과 피드백은 관리자에게 전달됩니다. 제보 강조를 선택하면 더 눈에 띄게 표시됩니다.</p> : null}
      {!snapshot && !error ? <p role="status">문항을 불러오는 중…</p> : null}
      {snapshot && !editable ? <details className="bank-personal-original" open><summary>문항</summary><p>{snapshot.original.question}</p></details> : null}
      {snapshot && editable ? <>
        {formats.length ? <label>문항 형식<select disabled={busy} value={format} onChange={e => changeFormat(e.target.value as BankFormat)}>
          {formats.map(value => <option key={value} value={value}>{formatLabel(value)}{value === originalFormat ? " (원래 형식)" : ""}</option>)}
        </select></label> : null}
        <label>발문<textarea disabled={busy} required rows={3} maxLength={12000} value={question} onChange={e => setQuestion(e.target.value)} /></label>
        {restructured && format === "cloze" ? <small>가릴 답을 {"{정답}"}처럼 중괄호로 감싸세요. 답을 열면 그 자리에 채워집니다.</small> : null}
        {restructured ? <details className="bank-personal-answer" open>
          <summary>정답·해설</summary>
          {format === "basic" || format === "list" ? <label>정답<textarea disabled={busy} required rows={4} maxLength={12000} value={answer}
            onChange={e => setAnswer(e.target.value)} />{format === "list" ? <small>한 줄에 한 항목, 2개 이상</small> : null}</label> : null}
          {format === "ox" ? <fieldset className="bank-personal-choices" disabled={busy}><legend>정답</legend>
            {["O", "X"].map(mark => <label key={mark}><input type="radio" name="personal-ox" required checked={answer.trim().toUpperCase() === mark}
              onChange={() => setAnswer(mark)} />{mark}</label>)}</fieldset> : null}
          {choice ? <>
            <label>객관식 학습 유형<select disabled={busy} value={mcqMode} onChange={e => setMcqMode(e.target.value as McqMode)}>
              <option value="recall_first">기억 확인형 · 먼저 떠올린 뒤 보기 공개</option>
              <option value="comparison">구별·판단형 · 보기 바로 공개</option>
            </select></label>
            <label>보기<textarea disabled={busy} required rows={4} maxLength={12000} value={choices}
              onChange={e => { setChoices(e.target.value); setCorrectIds([]); }} /><small>한 줄에 하나씩, 2~8개</small></label>
            <fieldset className="bank-personal-choices" disabled={busy}><legend>정답 보기{format === "mcq" ? " (하나)" : " (하나 이상, 전부는 안 됨)"}</legend>
              {lines(choices).map((text, index) => {
                const id = String(index + 1);
                return <label key={id}><input type={format === "mcq" ? "radio" : "checkbox"} name="personal-correct-option"
                  checked={correctIds.includes(id)} onChange={e => setCorrectIds(format === "mcq" ? [id]
                    : e.target.checked ? [...correctIds, id] : correctIds.filter(item => item !== id))} />{id}. {text}</label>;
              })}
            </fieldset>
          </> : null}
          <label>해설 (선택){format === "ox" ? " · O/X의 이유" : ""}<textarea disabled={busy} rows={3} maxLength={12000} value={explanation}
            onChange={e => setExplanation(e.target.value)} /></label>
        </details> : <details className="bank-personal-answer" open={answerVisible || undefined}>
          <summary>정답 확인·수정</summary>
          <label>정답<textarea disabled={busy} required rows={4} maxLength={12000} value={answer} onChange={e => setAnswer(e.target.value)} /></label>
          <small>정답을 수정한 문항은 내 수정본을 기준으로 직접 평가합니다.</small>
        </details>}</> : null}
      {snapshot ? <>
        {snapshot.personalAdded ? <label>설명 (선택)<textarea disabled={busy} rows={3} maxLength={12000}
          value={explanation} onChange={event => setExplanation(event.target.value)} /></label> : null}
        {!snapshot.personalAdded ? <><details className="bank-personal-original"><summary>공용 원문 보기</summary>
          {formats.length ? <p>형식: {formatLabel(originalFormat)}</p> : null}
          <p>{snapshot.original.question}</p><p>{snapshot.original.answer}</p></details>
        <label>피드백 (선택)<textarea disabled={busy} rows={3} maxLength={2000} value={comment}
          placeholder="수정 이유나 문제점을 적어 주세요." onChange={e => setComment(e.target.value)} /></label>
        <label className="bank-personal-report"><input type="checkbox" disabled={busy} checked={report} onChange={e => setReport(e.target.checked)} />제보 강조</label>
        {report ? <label>제보 유형<select disabled={busy} value={category} onChange={e => setCategory(e.target.value)}>
          {FEEDBACK.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select><small>관리자 피드백함에 강조 표시하고 우선 노출합니다.</small></label> : null}</> : null}
      </> : null}
      {error ? <p className="notice is-error" role="alert">{error}</p> : null}
      <footer>
        {snapshot?.edited && !snapshot.personalAdded ? <button type="button" disabled={busy} onClick={() => void save(true)}>원본으로 되돌리기</button> : null}
        <button type="button" className="is-quiet" disabled={busy} onClick={onClose}>취소</button>
        {snapshot ? <button type="submit" disabled={busy || (!changed && !noteChanged && !report)}>
          {busy ? "저장하는 중…" : !editable ? "제보 보내기" : report ? changed || noteChanged ? "내 수정본 저장·제보" : "제보 보내기" : "내 수정본 저장"}
        </button> : null}
      </footer>
    </form>
  </dialog>, document.body);
}
