import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Stem } from "../lecture/Stem";
import type { CardAction, ReviewCard } from "../types";

/**
 * 카드 한 장을 보고 괜찮다 · 고친다 · 뺀다 · 되돌린다.
 *
 * **두 자리가 같이 쓴다** — 관리 화면의 「카드 검토」 탭(편을 가로질러 걸린 것만)과
 * 강의 화면의 「카드 검토」 절(그 편의 카드 전부, 2026-09-23 관리자 지시 — 「관리
 * 패널 말고 그 강의 패널에서 고칠 수 있게 해줘」). 두 곳에 적으면 한쪽에만 빈칸
 * 원문 처리가 붙는 날이 온다.
 *
 * 규칙은 서버에 있다(`server/app/routes/cards.py`). 웹 풀이는 누르는 즉시, 덱은
 * 다음 publish 에서 바뀐다(`runner/site_edits.py`).
 */
export function ApkgNote() {
  return (
    <p className="card-review-note">
      고치거나 뺀 것은 <strong>웹 풀이</strong>에 바로, <strong>덱(.apkg)</strong>에는 다음 publish(야간 쓸기)에서
      반영됩니다. 고친 카드는 Anki에서 다시 받으면 같은 카드로 갱신되고, 뺀 카드는 이미 받아 간 사람의 Anki에서는
      지워지지 않습니다.
    </p>
  );
}

const REASONS: Record<string, string> = {
  question_ambiguous: "무엇을 묻는지 좁혀지지 않는다",
  needs_options: "보기·비교 대상이 있어야 답이 정해진다",
  answer_underspecified: "조건이 빠져 답이 열려 있다",
  blank_axis_missing: "빈칸이 무엇을 묻는지 안 선다",
};

const ACTIONS: Record<CardAction, string> = { ok: "괜찮음", edit: "고침", delete: "뺌" };

/** 서버는 UTC 로 준다. 잘라 쓰면 한국 시각보다 아홉 시간 이르게 찍힌다. */
function when(iso: string) {
  return new Date(iso).toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function kindLabel(kind: "pre" | "main") {
  return kind === "pre" ? "예습" : "복습";
}

export function CardRow({
  card,
  onChanged,
  onOpenLecture,
  focus = false,
}: {
  card: ReviewCard;
  onChanged: (next: ReviewCard) => void;
  onOpenLecture?: () => void;
  /** 풀이 화면에서 이 카드를 지목해 왔다. 내려와서 고치는 상태로 연다. */
  focus?: boolean;
}) {
  const [editing, setEditing] = useState(focus && card.edit?.action !== "delete");
  const self = useRef<HTMLElement>(null);
  useEffect(() => {
    if (focus) self.current?.scrollIntoView({ block: "center" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // 빈칸 카드는 원문을 고친다. 원문이 아직 안 올라온 옛 카드는 질문 칸을 잠근다.
  const cloze = card.qtype === "cloze";
  const front = cloze ? card.sourceStem : card.stem;
  const [draft, setDraft] = useState({ stem: front, answer: card.answer, explanation: card.explanation });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [slideOpen, setSlideOpen] = useState(false);

  const path = `/api/admin/lectures/${encodeURIComponent(card.subject)}/${card.runId}/cards/${card.kind}/${card.itemId}`;

  async function send(init: RequestInit) {
    setBusy(true);
    setError("");
    try {
      onChanged(await api<ReviewCard>(path, init));
      setEditing(false);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const decide = (action: CardAction, body: Record<string, string> = {}) =>
    send({ method: "PUT", body: JSON.stringify({ action, ...body }) });

  function save() {
    const { stem, ...rest } = draft;
    if (!cloze) return decide("edit", draft);
    // 원문이 없으면 질문은 안 보낸다 — 서버가 편 문장으로는 덱을 못 고친다.
    return decide("edit", card.sourceStem ? { sourceStem: stem, ...rest } : rest);
  }

  function startEdit() {
    setDraft({ stem: front, answer: card.answer, explanation: card.explanation });
    setEditing(true);
  }

  const deleted = card.edit?.action === "delete";
  const flag = card.flag;

  return (
    <article
      ref={self}
      className={`card-review-row${deleted ? " is-deleted" : ""}${focus ? " is-focus" : ""}`}
    >
      <header className="card-review-head">
        <span className="card-review-where">
          {card.subject} · {card.date.slice(5)} · {card.title} · {kindLabel(card.kind)} · {card.itemId}
        </span>
        {flag ? (
          <span className={`tag ${flag.why === "defect" ? "is-warn" : ""}`}>
            {flag.why === "defect" ? "문항 결함" : "빈칸 축"}
            {flag.reason ? ` — ${REASONS[flag.reason] ?? flag.reason}` : ""}
          </span>
        ) : null}
        {card.edit ? <span className="tag is-ok">{ACTIONS[card.edit.action]}</span> : null}
        {onOpenLecture ? (
          <button className="is-quiet" onClick={onOpenLecture}>
            이 편 카드 전부
          </button>
        ) : null}
      </header>

      {flag?.note ? <p className="card-review-why">{flag.note}</p> : null}
      {flag?.reproduced ? (
        <p className="card-review-why">
          질문만 보고 푼 답: <em>{flag.reproduced}</em>
        </p>
      ) : null}

      {editing ? (
        <div className="card-review-edit">
          <label>
            {cloze ? "질문 (빈칸은 {{c1::답}})" : "질문"}
            <textarea
              rows={3}
              value={draft.stem}
              disabled={cloze && !card.sourceStem}
              placeholder={cloze && !card.sourceStem ? "이 빈칸 카드는 원문이 아직 안 올라왔습니다 — 다음 publish 뒤에 고칠 수 있습니다" : ""}
              onChange={(e) => setDraft({ ...draft, stem: e.target.value })}
            />
          </label>
          <label>
            답
            <textarea rows={2} value={draft.answer} onChange={(e) => setDraft({ ...draft, answer: e.target.value })} />
          </label>
          <label>
            해설
            <textarea
              rows={4}
              value={draft.explanation}
              onChange={(e) => setDraft({ ...draft, explanation: e.target.value })}
            />
          </label>
          <div className="card-review-actions">
            <button className="is-primary" disabled={busy} onClick={save}>
              저장
            </button>
            <button className="is-quiet" disabled={busy} onClick={() => setEditing(false)}>
              취소
            </button>
          </div>
        </div>
      ) : (
        <dl className="card-review-card">
          <dt>질문</dt>
          <dd>
            <Stem text={card.stem} />
            {card.edit?.action === "edit" && card.stem !== card.original.stem ? (
              <small className="card-review-was">
                원래: <Stem text={card.original.stem} />
              </small>
            ) : null}
          </dd>
          <dt>답</dt>
          <dd>
            <Stem text={card.answer} />
            {card.edit?.action === "edit" && card.answer !== card.original.answer ? (
              <small className="card-review-was">
                원래: <Stem text={card.original.answer} />
              </small>
            ) : null}
          </dd>
          {card.explanation ? (
            <>
              <dt>해설</dt>
              <dd>
                <Stem text={card.explanation} />
              </dd>
            </>
          ) : null}
        </dl>
      )}

      {card.slideUrl ? (
        <div className="card-review-slide">
          <button className="is-quiet" onClick={() => setSlideOpen((v) => !v)}>
            {slideOpen ? "슬라이드 접기" : `슬라이드 ${card.slideNo} 보기`}
          </button>
          {slideOpen ? <img src={card.slideUrl} alt={`슬라이드 ${card.slideNo}`} /> : null}
        </div>
      ) : null}

      {error ? <p className="notice is-error">{error}</p> : null}

      {editing ? null : (
        <div className="card-review-actions">
          {card.edit ? (
            <>
              <span className="card-review-by">
                {card.edit.editedBy}
                {card.edit.editedAt ? ` · ${when(card.edit.editedAt)}` : ""}
              </span>
              <button disabled={busy} onClick={() => send({ method: "DELETE" })}>
                되돌리기
              </button>
              {deleted ? null : (
                <button disabled={busy} onClick={startEdit}>
                  고치기
                </button>
              )}
            </>
          ) : (
            <>
              <button disabled={busy} onClick={() => decide("ok")}>
                괜찮음
              </button>
              <button disabled={busy} onClick={startEdit}>
                고치기
              </button>
              <button disabled={busy} onClick={() => decide("delete")}>
                빼기
              </button>
            </>
          )}
        </div>
      )}
    </article>
  );
}
