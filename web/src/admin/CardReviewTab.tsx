import { useState } from "react";
import { ApkgNote, CardRow } from "../cards/CardRow";
import type { CardReview } from "../types";

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

  if (!review) return <p className="notice">불러오는 중…</p>;
  const shown = showDone ? review.cards : review.cards.filter((card) => !card.edit);

  // 「이 편 카드 전부」는 걷어냈다(2026-09-23 관리자 — 「카드 검토할때 검토표시된것만
  // 확인하고 고치려고 하는 거였어」). 표시가 없는 카드는 풀이 화면에서 고친다.
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
      {shown.map((card) => (
        <CardRow key={`${card.subject}/${card.runId}/${card.kind}/${card.itemId}`} card={card} onChanged={onChanged} />
      ))}
    </section>
  );
}
