import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router-dom";
import { api } from "../api";
import "../styles/feedback.css";

type Attachment = { file: File; url: string };
type PreQuizContext = {
  subject: string; runId: string; itemId: string; title: string; stem: string;
  answer?: string; explanation?: string;
};
const prequizCategories = [
  ["content", "답·설명 오류"], ["wording", "질문이 모호해요"],
  ["difficulty", "난이도가 맞지 않아요"], ["scope", "강의 범위와 달라요"], ["other", "기타"],
] as const;
function readImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () => reject(new Error("캡처 파일을 읽지 못했습니다."));
    reader.readAsDataURL(file);
  });
}

/** `launch`를 주면 그 모양으로 여는 버튼을 그린다(좌측 메뉴의 「문의하기」). 대화상자는 같다. */
export function FeedbackButton({ prequiz, launch }: {
  prequiz?: PreQuizContext;
  launch?: { className: string; content: ReactNode; title?: string };
} = {}) {
  const location = useLocation();
  const id = useId();
  const pending = useRef(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const attachments = useRef<Attachment[]>([]);
  const [shots, setShots] = useState<Attachment[]>([]);
  const [message, setMessage] = useState("");
  const [page, setPage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [report, setReport] = useState<PreQuizContext | null>(null);
  const [category, setCategory] = useState("content");
  // 닫혀 있는 동안은 대화상자 내용을 그리지 않는다 — 풀이 화면에 입력칸·문항 글이 숨은 채 남지 않게.
  const [open, setOpen] = useState(false);
  useEffect(() => () => {
    attachments.current.forEach((shot) => URL.revokeObjectURL(shot.url));
  }, []);
  function updateShots(next: Attachment[]) {
    attachments.current = next;
    setShots(next);
  }
  function add(files: File[]) {
    if (busy) return;
    setError("");
    const next = [...attachments.current];
    for (const file of files) {
      if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
        setError("PNG, JPG, WebP 캡처만 첨부할 수 있습니다."); continue;
      }
      if (file.size > 3 * 1024 * 1024 || file.size === 0) {
        setError("캡처는 한 장당 3MB 이하로 첨부해 주세요."); continue;
      }
      if (next.length >= 3) { setError("캡처는 최대 3장까지 첨부할 수 있습니다."); break; }
      next.push({ file, url: URL.createObjectURL(file) });
    }
    updateShots(next);
  }
  function close() {
    if (pending.current) return;
    setOpen(false);
    dialog.current?.close();
    opener.current?.focus();
  }
  async function submit() {
    if (pending.current || !message.trim()) return;
    pending.current = true;
    setBusy(true); setError("");
    try {
      const screenshots = await Promise.all(shots.map(async ({ file }) => ({
        name: file.name.slice(0, 200), data: await readImage(file),
      })));
      await api<{ id: number }>(report ? "/api/feedback/prequiz" : "/api/feedback", {
        method: "POST", body: JSON.stringify({ message: message.trim(), page, screenshots,
          ...(report ? { ...report, category } : {}),
        }),
      });
      attachments.current.forEach((shot) => URL.revokeObjectURL(shot.url));
      updateShots([]); setMessage(""); setSent(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "보내지 못했습니다. 다시 시도해 주세요.");
    } finally { pending.current = false; setBusy(false); }
  }
  return <>
    <button ref={opener} className={launch?.className ?? "feedback-launch"} title={launch?.title} onClick={() => {
      setReport(prequiz ?? null); setPage(location.pathname);
      setSent(false); setError(""); setOpen(true); dialog.current?.showModal();
      window.requestAnimationFrame(() => input.current?.focus());
    }}>{launch?.content ?? (prequiz ? "문제 제보" : "피드백")}</button>
    {createPortal(<dialog ref={dialog} className="feedback-dialog" aria-labelledby={`${id}-title`}
      onCancel={(event) => { event.preventDefault(); close(); }}
      onPaste={(event) => {
        const files = Array.from(event.clipboardData.files);
        if (files.length) { event.preventDefault(); add(files); }
      }} onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => { event.preventDefault(); add(Array.from(event.dataTransfer.files)); }}>
      {open ? <>
      <header><h2 id={`${id}-title`}>{prequiz ? "예습 문제 제보" : "피드백 보내기"}</h2>
        <button className="is-quiet" disabled={busy} onClick={close} aria-label="피드백 닫기">닫기</button>
      </header>
      {sent ? <div role="status"><p>{prequiz ? "제보를 보냈습니다. 관리자가 확인하겠습니다." : "피드백을 보냈습니다. 관리자가 확인하겠습니다."}</p>
        <button onClick={close}>확인</button></div> :
      <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        {report ? <>
          <p className="feedback-context">{report.title} · {report.itemId}</p>
          <p className="feedback-question">{report.stem}</p>
          <p className="feedback-hint">질문·답·설명과 근거가 관리자에게 함께 전달됩니다.</p>
          <label className="feedback-category" htmlFor={`${id}-category`}>제보 유형
            <select id={`${id}-category`} disabled={busy} value={category} onChange={(event) => setCategory(event.target.value)}>
              {prequizCategories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </> : null}
        <label htmlFor={`${id}-message`}>{report ? "어떤 부분을 확인하면 될까요?" : "불편한 점이나 원하는 기능을 알려 주세요."}</label>
        <textarea ref={input} id={`${id}-message`} required maxLength={4000} rows={5}
          disabled={busy} value={message} onChange={(event) => setMessage(event.target.value)} />
        <p className="feedback-context">보고 있던 화면: {page}</p>
        <label className="feedback-attach">화면 캡처 첨부
          <input aria-label="화면 캡처 파일 선택" type="file" multiple accept="image/png,image/jpeg,image/webp" disabled={busy}
            onChange={(event) => { add(Array.from(event.target.files ?? [])); event.target.value = ""; }} />
        </label>
        <p className="feedback-hint">캡처를 붙여넣거나 여기에 끌어 놓을 수도 있어요. 최대 3장 · 한 장당 3MB</p>
        <div className="feedback-shots">{shots.map((shot, index) => <figure key={shot.url}>
          <img src={shot.url} alt={`첨부 캡처 ${index + 1}`} /><figcaption>{shot.file.name}</figcaption>
          <button type="button" disabled={busy} aria-label={`캡처 ${index + 1} 삭제`} onClick={() => {
            URL.revokeObjectURL(shot.url); updateShots(attachments.current.filter((item) => item !== shot));
          }}>삭제</button></figure>)}</div>
        {error ? <p className="notice is-error" role="alert">{error}</p> : null}
        <footer><button type="button" className="is-quiet" disabled={busy} onClick={close}>나중에</button>
          <button type="submit" disabled={busy || !message.trim()}>{busy ? "보내는 중…" : report ? "제보 보내기" : "보내기"}</button></footer>
      </form>}
      </> : null}
    </dialog>, document.body)}
  </>;
}
