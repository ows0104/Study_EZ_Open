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
  const [confirmed, setConfirmed] = useState(false);
  // 복사한 Markdown의 굵게·인라인 코드·닫는 코드블록은 완료 표시의 일부가 아니다.
  const text = raw.trim().replace(
    /(?:\*\*|__|`{1,3})?STUDYEZ_BANK_COMPLETE(?:\*\*|__|`{1,3})?(?:\s*\n```)?\s*$/,
    COMPLETE_MARK,
  );
  const complete = text.endsWith(COMPLETE_MARK);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    setSaved(false);
    if (disabled) { setError("다른 작업이 진행 중입니다. 검수가 끝난 뒤 다시 저장해주세요. 입력한 답변은 그대로 남아 있습니다."); return; }
    if (text.length < 200) { setError("답변 본문이 너무 짧습니다. ChatGPT의 퀴즈뱅크 답변 전체를 붙여 넣어주세요. (200자 이상)"); return; }
    if (!complete && !confirmed) { setError("완료 표시가 없습니다. 답변을 끝까지 붙여 넣었다면 아래 확인란을 선택한 뒤 다시 저장해주세요."); return; }
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await api(`/api/admin/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank-response`, {
        method: "PUT",
        // 링크 필드를 생략해 저장된 공유·개인 링크를 보존한다.
        // 수동으로 전체 복사를 확인한 경우에도 기존 전달 계약의 끝 표시를 붙인다.
        body: JSON.stringify({ raw: complete ? text : `${text}\n${COMPLETE_MARK}` }),
      });
      setRaw("");
      setConfirmed(false);
      setSaved(true);
      onSaved();
    } catch (cause) {
      setError((cause as Error).message);
    } finally { setSaving(false); }
  }

  return <details className="link-editor">
    <summary>답변 직접 붙여넣기</summary>
    <form className="link-editor" onSubmit={event => void save(event)}>
      <p className="panel-hint">저장할 강의: {subject} · {runId}. ChatGPT 답변 전체를 복사하세요. 여러 답변으로 나뉘었다면 순서대로 모두 붙여 넣으세요.</p>
      <label className="link-editor-field" htmlFor={id}>
        <span>퀴즈뱅크 답변 본문</span>
        <textarea id={id} rows={10} maxLength={2_000_000} value={raw} disabled={saving}
          style={{ width: "100%", resize: "vertical" }} spellCheck={false}
          placeholder="이 강의의 완성된 답변 전체를 붙여 넣으세요."
          onChange={event => { setRaw(event.target.value); setSaved(false); setError(""); setConfirmed(false); }} />
      </label>
      {text && !complete ? <>
        <p className="panel-hint">끝에 완료 표시({COMPLETE_MARK})가 없습니다. ChatGPT 답변이 중간에 끊기지 않았는지 확인하세요.</p>
        <label><input type="checkbox" checked={confirmed} disabled={saving}
          onChange={event => { setConfirmed(event.target.checked); setError(""); }} /> 답변 전체를 끝까지 붙여 넣었습니다</label>
      </> : null}
      {text && text.length < 200 ? <p className="panel-hint">답변 본문은 200자 이상이어야 합니다.</p> : null}
      <div className="link-editor-actions">
        <button type="submit" className="is-primary" disabled={saving}>
          {saving ? "저장 중…" : "답변 저장·검수 요청"}
        </button>
      </div>
      {disabled ? <p className="panel-hint">다른 작업이 진행 중이어서 지금은 저장할 수 없습니다. 입력 내용은 유지되니 검수가 끝난 뒤 저장해주세요.</p> : null}
      <p className="panel-hint">저장하면 이 강의의 응답 원문을 교체하고 검수·게시를 요청합니다. 검수 중인 작업이 끝난 뒤 저장할 수 있습니다.</p>
      {saved ? <p role="status" className="panel-hint">답변을 저장했습니다. 러너가 켜져 있으면 검수·게시를 진행합니다.</p> : null}
      {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    </form>
  </details>;
}
