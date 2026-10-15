import { Stem } from "../lecture/Stem";
import { sourceNote } from "./sourceNotes";
import "./source-notes.css";

/** The answer teaches the concept; this optional comparison explains source differences. */
export function BankSourceNote({ conflict, external }: { conflict?: string; external?: boolean }) {
  const note = sourceNote(conflict ?? "");
  if (!note.text) return external ? <p className="bank-evidence-note">외부 근거 참고</p> : null;
  return <aside className="bank-source-note" aria-label="자료 비교">
    {note.pending ? <p className="bank-source-pending"><b>확인 필요</b> <Stem text={note.pending} /></p> : null}
    <details>
      <summary><span>자료 비교</span><span className="bank-source-summary">서로 다른 설명과 판단 근거</span></summary>
      <div className="bank-source-content">
        {note.rows.length ? <dl>{note.rows.filter(row => row.label !== "미해결").map((row, i) => <div key={i}>
          <dt>{row.label}</dt><dd><Stem text={row.text} /></dd>
        </div>)}</dl> : <p className="bank-source-legacy"><Stem text={note.text} /></p>}
        {external ? <p className="bank-evidence-note">정답 판단에 외부 근거를 참고했습니다.</p> : null}
      </div>
    </details>
  </aside>;
}
