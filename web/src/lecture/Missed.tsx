import type { MissedItem } from "../types";
import { Stem } from "./Stem";

/**
 * 오늘 놓친 것.
 *
 * 웹에서 끝까지 훑은 사람에게만 나온다. 몰랐다고 찍은 카드가 그 강의에서 특히
 * 귀 기울일 곳이라는 생각으로 고른다 — 고르는 것은 서버다(`missed_items`).
 *
 * 두 자리에 선다. 다 푼 직후의 Pre-Quiz 창과, 나중에 다시 여는 강의 화면.
 */
export function Missed({ items }: { items: MissedItem[] }) {
  if (!items.length) return null;
  return (
    <section className="missed">
      <h2>오늘 놓친 것 {items.length}개</h2>
      <ol>
        {items.map((entry) => (
          <li key={entry.itemId}>
            <p className="missed-stem">
              <Stem text={entry.stem} />
            </p>
            <p className="missed-target">{entry.answer}</p>
            {entry.examHit ? <span className="badge">기출</span> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
