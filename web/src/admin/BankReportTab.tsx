import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { FEEDBACK_LABEL } from "../bank/feedback";
import { Stem } from "../lecture/Stem";
import type { BankReportBoard, BankReportGroup, BankReportStatus } from "../types/bank";

/**
 * 학생이 Quiz Bank 를 풀다 누른 「문제 있음」을 본다.
 *
 * **같은 문항의 신고는 한 묶음이다.** 여럿이 같은 자리에서 멈췄다는 것이 그 자체로 정보다.
 * 편을 가로질러 서버가 묶어 준다(`GET /api/admin/bank-feedback`).
 *
 * **여기서 문항을 고치지는 못한다.** 은행은 ChatGPT 응답을 러너가 정리한 것이라 고치는
 * 길이 그 둘이다 — 강의 패널의 「다시 정리」 또는 「ChatGPT로 만들기」. 여기서 하는 일은
 * 신고를 읽고 반영했다 · 그대로 둔다를 적는 것까지다.
 *
 * **보이는 문항은 지금 은행의 것이다.** 신고 줄에 문면이 없어서다. 다시 만들면 ChatGPT 가
 * 같은 ID 에 다른 문항을 낼 수 있으므로, 옛 빌드에서 온 신고는 「옛 판」으로 갈라 적는다.
 *
 * 목록은 위(`AdminPage`)에서 읽어 내려온다 — 열린 수가 탭 이름 옆에 서야 해서다.
 */
export function BankReportTab({ board, onChanged }: { board: BankReportBoard | null; onChanged: () => void }) {
  const [showDone, setShowDone] = useState(false);

  if (!board) return <p className="notice">불러오는 중…</p>;
  const isOpen = (g: BankReportGroup) => g.reports.some((r) => r.status === "open");
  const shown = showDone ? board.questions : board.questions.filter(isOpen);

  return (
    <section className="card-review">
      {/* 0건도 답이다. 빈 화면으로 두면 못 불러온 것과 같다. */}
      <p className="admin-summary">
        {board.open ? (
          <>
            안 본 문항 <strong>{board.open}개</strong>
          </>
        ) : (
          <>안 본 신고 없음</>
        )}
        {board.done ? <> · 본 것 {board.done}개</> : null}
        {board.done ? (
          <>
            {" "}
            <button className="is-quiet" onClick={() => setShowDone((v) => !v)}>
              {showDone ? "안 본 것만" : "본 것도 보기"}
            </button>
          </>
        ) : null}
      </p>
      <p className="card-review-note">
        문항은 여기서 고치지 않습니다. 고치려면 그 강의 패널에서 <strong>다시 정리</strong>(같은 ChatGPT 응답을
        다시 정리) 또는 <strong>ChatGPT로 만들기</strong>(새로 만들기)를 누르세요.
      </p>
      {shown.map((group) => (
        <ReportGroup key={`${group.subject}/${group.runId}/${group.questionId}`} group={group} onChanged={onChanged} />
      ))}
    </section>
  );
}

const STATUS_LABEL: Record<BankReportStatus, string> = { open: "열림", resolved: "반영함", wontfix: "그대로 둠" };
const VERDICT_LABEL: Record<string, string> = { wrong: "외부지식 · 틀림", doubt: "외부지식 · 의심" };

/** 서버는 UTC 로 준다. 잘라 쓰면 한국 시각보다 아홉 시간 이르게 찍힌다. */
function when(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function ReportGroup({ group, onChanged }: { group: BankReportGroup; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const q = group.question;
  const open = group.reports.filter((r) => r.status === "open");
  const closed = open.length === 0 ? group.reports[0]?.status : null;
  const stale = group.reports.filter((r) => r.stale).length;
  const verdict = group.medicalReview && group.medicalReview.verdict !== "ok" ? group.medicalReview : null;

  async function decide(status: BankReportStatus) {
    // 열린 것만 닫고, 다시 열 때는 이 문항의 신고 전부를 연다.
    const ids = (status === "open" ? group.reports : open).map((r) => r.id);
    setBusy(true);
    setError("");
    try {
      await api("/api/admin/bank-feedback", { method: "PUT", body: JSON.stringify({ ids, status }) });
      onChanged();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    // 닫은 묶음은 흐리게만 한다. 「카드 검토」의 `is-deleted` 는 취소선을 그어 문항이 지워진 것처럼 읽힌다.
    <article className="card-review-row" style={closed ? { opacity: 0.7 } : undefined}>
      <header className="card-review-head">
        <span className="card-review-where">
          {group.subject} · {group.date.slice(5)} · {group.title} · {group.questionId}
          {q ? ` · ${q.format}` : ""}
        </span>
        <span className="tag is-warn">신고 {group.reports.length}건</span>
        {stale ? <span className="tag">옛 판 신고 {stale}건</span> : null}
        {verdict ? <span className="tag is-warn">{VERDICT_LABEL[verdict.verdict] ?? verdict.verdict}</span> : null}
        {closed ? <span className="tag is-ok">{STATUS_LABEL[closed]}</span> : null}
      </header>

      {q ? (
        <dl className="card-review-card">
          <dt>질문</dt>
          <dd>
            <Stem text={q.question} />
            {q.options.length ? (
              <ul>
                {q.options.map((o) => (
                  <li key={o.id}>
                    {q.correct_option_ids.includes(o.id) ? <strong>{o.id}. {o.text} ✓</strong> : `${o.id}. ${o.text}`}
                  </li>
                ))}
              </ul>
            ) : null}
          </dd>
          <dt>답</dt>
          <dd>
            {q.answer_pairs.length ? (
              <ul>
                {q.answer_pairs.map((p) => (
                  <li key={`${p.left}-${p.right}`}>
                    {p.left} → {p.right}
                  </li>
                ))}
              </ul>
            ) : q.correct_order.length ? (
              q.correct_order.join(" → ")
            ) : (
              <Stem text={q.answer} />
            )}
          </dd>
        </dl>
      ) : (
        <p className="card-review-why">지금 은행에 이 문항이 없습니다 — 다시 만들면서 빠졌습니다.</p>
      )}

      {verdict ? (
        <p className="card-review-why">
          외부지식 검토: {verdict.note}
          {verdict.suggested_answer ? <> — 맞는 답: {verdict.suggested_answer}</> : null}
        </p>
      ) : null}

      <ul className="card-review-why">
        {group.reports.map((r) => (
          <li key={r.id} style={r.status === "open" ? undefined : { opacity: 0.6 }}>
            <strong>{FEEDBACK_LABEL[r.category] ?? r.category}</strong>
            {r.comment ? <> — {r.comment}</> : null}
            <small>
              {" "}
              · {r.email || "알 수 없음"} · {when(r.createdAt)}
              {r.stale ? " · 옛 판" : ""}
            </small>
          </li>
        ))}
      </ul>

      <div className="card-review-actions">
        <Link className="card-review-by" to={`/bank/${encodeURIComponent(group.subject)}/${group.runId}`}>
          풀이 창 열기
        </Link>
        {open.length ? (
          <>
            <button className="is-primary" disabled={busy} onClick={() => void decide("resolved")}>
              반영했다
            </button>
            <button disabled={busy} onClick={() => void decide("wontfix")}>
              그대로 둔다
            </button>
          </>
        ) : (
          <button className="is-quiet" disabled={busy} onClick={() => void decide("open")}>
            다시 열기
          </button>
        )}
      </div>
      {error ? <p className="notice is-error">{error}</p> : null}
    </article>
  );
}
