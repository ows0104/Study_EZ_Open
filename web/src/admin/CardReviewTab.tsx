import { useState } from "react";
import { api } from "../api";
import { Stem } from "../lecture/Stem";
import type { CardAction, CardReview, LectureCards, ReviewCard } from "../types";

/**
 * 걸린 카드를 보고 괜찮다 · 고친다 · 뺀다.
 *
 * **2026-09-23 관리자 지시** — 「이상한 카드가 있으면 업로드 단계에서 막히고 있어.
 * 그러지 말고 일단 업로드를 하고, 사이트에서 검토/수정/삭제할 수 있도록 하자.」
 * 그 전까지 문지기(`runner/gate.py`)는 결함 카드 한 장 때문에 덱 전체를 미뤘다.
 * 이제 덱은 나가고, 그 카드가 여기 뜬다.
 *
 * **웹 풀이는 누르는 즉시, 덱(`.apkg`)은 다음 publish 에서 바뀐다**(2026-09-23 —
 * 「사이트에서 고친 카드가 apkg에도 반영되게 해줘」). 러너가 판정을 당겨 가 그 편만
 * 다시 굽는다(`runner/site_edits.py`). 그 사이의 틈을 화면 위에 적어 둔다.
 *
 * **빈칸 카드는 원문을 고친다.** 답이 질문 안(`{{c1::…}}`)에 있어서 편 문장을
 * 고쳐서는 덱으로 못 되돌린다(`quizgen/site_edits.py`).
 *
 * 목록은 위(`AdminPage`)에서 읽어 내려온다. 안 본 카드 수가 탭 이름 옆에 서야
 * 하기 때문이다 — 탭을 열어야 보이는 수는 없는 수다.
 */
export function CardReviewTab({ review, onChanged }: { review: CardReview | null; onChanged: () => void }) {
  const [showDone, setShowDone] = useState(false);
  const [lecture, setLecture] = useState<LectureCards | null>(null);
  const [lectureError, setLectureError] = useState("");

  if (!review) return <p className="notice">불러오는 중…</p>;
  const shown = showDone ? review.cards : review.cards.filter((card) => !card.edit);

  async function openLecture(card: ReviewCard) {
    setLectureError("");
    try {
      setLecture(
        await api<LectureCards>(
          `/api/admin/lectures/${encodeURIComponent(card.subject)}/${card.runId}/cards/${card.kind}`,
        ),
      );
    } catch (cause) {
      setLectureError((cause as Error).message);
    }
  }

  // 한 편 목록에서 판정하면 그 편 목록도, 위의 검토 목록도 다시 읽는다.
  function changedInLecture(next: ReviewCard) {
    setLecture((prev) =>
      prev ? { ...prev, cards: prev.cards.map((c) => (c.itemId === next.itemId ? next : c)) } : prev,
    );
    onChanged();
  }

  if (lecture) {
    return (
      <section className="card-review">
        <p className="admin-summary">
          <button className="is-quiet" onClick={() => setLecture(null)}>
            ← 검토 목록
          </button>{" "}
          {lecture.subject} · {lecture.title} · {kindLabel(lecture.kind)} · 카드 {lecture.cards.length}장
        </p>
        <ApkgNote />
        {lecture.cards.map((card) => (
          <CardRow key={card.itemId} card={card} onChanged={changedInLecture} />
        ))}
      </section>
    );
  }

  return (
    <section className="card-review">
      {/* 0장도 답이다. 빈 화면으로 두면 못 불러온 것과 같다. */}
      <p className="admin-summary">
        {review.open ? (
          <>
            안 본 카드 <strong>{review.open}장</strong>
          </>
        ) : (
          <>안 본 카드 없음</>
        )}
        {review.done ? <> · 본 것 {review.done}장</> : null}
        {review.done ? (
          <>
            {" "}
            <button className="is-quiet" onClick={() => setShowDone((v) => !v)}>
              {showDone ? "안 본 것만" : "본 것도 보기"}
            </button>
          </>
        ) : null}
      </p>
      <ApkgNote />
      {lectureError ? <p className="notice is-error">{lectureError}</p> : null}
      {shown.map((card) => (
        <CardRow
          key={`${card.subject}/${card.runId}/${card.kind}/${card.itemId}`}
          card={card}
          onChanged={onChanged}
          onOpenLecture={() => openLecture(card)}
        />
      ))}
    </section>
  );
}

function ApkgNote() {
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

function kindLabel(kind: "pre" | "main") {
  return kind === "pre" ? "예습" : "복습";
}

function CardRow({
  card,
  onChanged,
  onOpenLecture,
}: {
  card: ReviewCard;
  onChanged: (next: ReviewCard) => void;
  onOpenLecture?: () => void;
}) {
  const [editing, setEditing] = useState(false);
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
    <article className={`card-review-row${deleted ? " is-deleted" : ""}`}>
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
