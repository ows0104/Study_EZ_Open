import { useId, useState, type FormEvent } from "react";
import { api } from "../api";

const COMPLETE_MARK = "STUDYEZ_BANK_COMPLETE";

/** 강의별 수동 전달도 확장과 같은 저장·검수 경로를 사용한다. */
export function BankResponseInput({ subject, runId, disabled, onSaved }: {
  subject: string;
  runId: string;
  disabled: boolean;
  onSaved: () => void;
}) {
  const id = useId();
  const [raw, setRaw] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const text = raw.trim();
  const complete = text.endsWith(COMPLETE_MARK);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (saving || disabled || text.length < 200 || !complete) return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await api(`/api/admin/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank-response`, {
        method: "PUT",
        // 링크 필드를 생략해 저장된 공유·개인 링크를 보존한다.
        body: JSON.stringify({ raw: text }),
      });
      setRaw("");
      setSaved(true);
      onSaved();
    } catch (cause) {
      setError((cause as Error).message);
    } finally { setSaving(false); }
  }

  return <details className="link-editor">
    <summary>답변 직접 붙여넣기</summary>
    <form className="link-editor" onSubmit={event => void save(event)}>
      <p className="panel-hint">저장할 강의: {subject} · {runId}. ChatGPT 답변 전체를 마지막 {COMPLETE_MARK} 줄까지 복사하세요. 여러 답변으로 나뉘었다면 순서대로 모두 붙여 넣으세요.</p>
      <label className="link-editor-field" htmlFor={id}>
        <span>퀴즈뱅크 답변 본문</span>
        <textarea id={id} rows={10} maxLength={2_000_000} value={raw} disabled={saving}
          style={{ width: "100%", resize: "vertical" }} spellCheck={false}
          placeholder="이 강의의 완성된 답변 전체를 붙여 넣으세요."
          onChange={event => { setRaw(event.target.value); setSaved(false); setError(""); }} />
      </label>
      {text && !complete ? <p className="panel-hint">끝에 {COMPLETE_MARK} 표시가 없습니다. 답변이 끝까지 완성되었는지 확인하세요.</p> : null}
      {text && text.length < 200 ? <p className="panel-hint">답변 본문은 200자 이상이어야 합니다.</p> : null}
      <div className="link-editor-actions">
        <button type="submit" className="is-primary" disabled={disabled || saving || text.length < 200 || !complete}>
          {saving ? "저장 중…" : "답변 저장·검수 요청"}
        </button>
      </div>
      <p className="panel-hint">저장하면 이 강의의 응답 원문을 교체하고 검수·게시를 요청합니다. 검수 중인 작업이 끝난 뒤 저장할 수 있습니다.</p>
      {saved ? <p role="status" className="panel-hint">답변을 저장했습니다. 러너가 켜져 있으면 검수·게시를 진행합니다.</p> : null}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    </form>
  </details>;
}
