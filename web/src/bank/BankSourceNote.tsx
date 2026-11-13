import { Stem } from "../lecture/Stem";
import type { BankAnswer } from "../types/bank";
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

/**
 * Main-Quiz 답 화면의 자료 충돌 배지(2026-11-13 사용자 「화면 배지부터 진행해줘」).
 * 충돌 설명 전체는 접힌 「이 문항 검토 기록」에 그대로 있고, 여기서는 충돌이 있다는 것과 판단 한 줄만 보인다.
 * 서버가 준 충돌 기록(conflict) 또는 근거 상태 「자료 충돌」만 쓴다 — 화면이 충돌을 추측하지 않는다.
 */
export function SourceConflictBadge({ answer }: { answer: BankAnswer }) {
  const note = sourceNote(answer.conflict ?? "");
  const status = answer.evidenceStatus?.category === "source_conflict" ? answer.evidenceStatus : null;
  if (!note.text && !status) return null;
  const judgment = note.rows.find(row => row.label === "판단")?.text
    ?? (note.text ? note.text.split(/\r?\n/).find(line => line.trim()) : status?.reason);
  return <aside className="bank-conflict-badge" role="note" aria-label="자료 충돌">
    <p><span className="bank-conflict-tag">자료 충돌</span> 자료끼리 설명이 다른 문항입니다. 시험 정답은 이 답과 다를 수 있습니다.</p>
    {judgment ? <p className="bank-conflict-judgment"><b>판단</b> <Stem text={judgment} /></p> : null}
    <p className="bank-conflict-more">자료별 설명은 아래 「이 문항 검토 기록」에 있습니다.</p>
  </aside>;
}
