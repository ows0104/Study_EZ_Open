import type { MissedItem } from "../types/quiz";
import { Stem } from "./Stem";

/**
 * 오늘 놓친 것.
 *
 * 웹에서 끝까지 훑은 사람에게만 나온다. 몰랐다고 찍은 카드가 그 강의에서 특히
 * 귀 기울일 곳이라는 생각으로 고른다 — 고르는 것은 서버다(`missed_items`).
 *
 * **재료는 오늘 Again을 누른 기록이다**(2026-09-18). 뒤에 다시 맞혔어도 남는다 —
 * 일정이 도는 지금 「지금 틀린 상태인 카드」로 고르면 이 목록은 영영 빈다(왜
 * 그런지는 서버의 `missed_items`에 있다).
 *
 * 두 자리에 선다. 다 푼 직후의 Pre-Quiz 창과, 같은 날 다시 여는 강의 화면.
 */
export function Missed({ items, preview = false }: { items: MissedItem[]; preview?: boolean }) {
  if (!items.length) return null;
  return (
    <section className="missed">
      <h2>{preview ? "수업에서 확인할 질문" : "오늘 놓친 것"} {items.length}개</h2>
      <ol>
        {items.map((entry) => (
          <li key={entry.itemId}>
            <p className="missed-stem">
              <Stem text={preview ? entry.lectureFocus || entry.stem : entry.stem} />
            </p>
            {!preview ? <p className="missed-target">{entry.answer}</p> : null}
            {entry.examHit ? <span className="badge">기출</span> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
