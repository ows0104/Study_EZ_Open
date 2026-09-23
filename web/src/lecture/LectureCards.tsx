import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ApkgNote, CardRow } from "../cards/CardRow";
import type { CardReviewCount, LectureCards as LectureCardList, ReviewCard } from "../types";

type Kind = "pre" | "main";

/**
 * 여기로 보내는 주소의 꼬리. `#cards-main` 이면 복습 갈래를 펴고 내려온다(사이드 패널).
 * `#cards-main-c002` 면 그 카드를 고치는 상태로 연다(웹 풀이 화면, 2026-09-23).
 */
export function cardsHash(kind: Kind, itemId = "") {
  return `#cards-${kind}${itemId ? `-${encodeURIComponent(itemId)}` : ""}`;
}

function readHash(): { kind: Kind; itemId: string } | null {
  const m = /^#cards-(pre|main)(?:-(.+))?$/.exec(window.location.hash);
  return m ? { kind: m[1] as Kind, itemId: m[2] ? decodeURIComponent(m[2]) : "" } : null;
}

/**
 * 강의 화면의 「카드 검토」. **관리자에게만 선다.**
 *
 * 2026-09-23 관리자 지시 — 「관리 패널 말고 그 강의 패널에서 고칠 수 있게 해줘.
 * 사이드 패널에서도 고치기로 넘어갈 수 있게 해줘.」 관리 화면의 탭은 편을 가로질러
 * **걸린 카드만** 모으고, 여기는 **이 편의 카드 전부**를 든다 — 풀다가 이상한 카드를
 * 찾았으면 걸리지 않았어도 여기서 고친다.
 *
 * **열 때까지 안 읽는다.** 답까지 든 목록이라 한 편에 100장이 넘고, 강의 화면을 여는
 * 사람 대부분은 고치러 온 것이 아니다. 사이드 패널에서 넘어오면(`#cards-…`) 바로 편다.
 */
export function LectureCards({
  subject,
  runId,
  counts,
}: {
  subject: string;
  runId: string;
  counts: Partial<Record<Kind, CardReviewCount>>;
}) {
  const kinds = (["pre", "main"] as const).filter((kind) => counts[kind]);
  const target = readHash();
  const fromHash = target && kinds.includes(target.kind) ? target.kind : undefined;
  // 풀이 화면에서 한 장을 지목해 왔으면 그 카드. 걸리지 않은 카드일 수 있으므로
  // 그때는 「걸린 것만」을 끈다.
  const focusId = fromHash ? target!.itemId : "";
  const [kind, setKind] = useState<Kind | null>(fromHash ?? null);
  const [list, setList] = useState<LectureCardList | null>(null);
  const [error, setError] = useState("");
  // 걸린 카드가 있으면 그것부터. 없으면 전부.
  const [onlyFlagged, setOnlyFlagged] = useState(!focusId);
  const section = useRef<HTMLElement>(null);

  useEffect(() => {
    if (fromHash && !focusId) section.current?.scrollIntoView({ block: "start" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!kind) return;
    let live = true;
    setList(null);
    setError("");
    api<LectureCardList>(`/api/admin/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/cards/${kind}`)
      .then((next) => live && setList(next))
      .catch((cause: Error) => live && setError(cause.message));
    return () => {
      live = false;
    };
  }, [subject, runId, kind]);

  if (!kinds.length) return null;

  function changed(next: ReviewCard) {
    setList((prev) => (prev ? { ...prev, cards: prev.cards.map((c) => (c.itemId === next.itemId ? next : c)) } : prev));
  }

  const flagged = list?.cards.filter((card) => card.flag) ?? [];
  const shown = list ? (onlyFlagged && flagged.length ? flagged : list.cards) : [];

  return (
    <section className="lecture-section lecture-cards" id="cards" ref={section}>
      <h2>카드 검토</h2>
      <div className="lecture-cards-kinds" role="group" aria-label="갈래">
        {kinds.map((option) => {
          const count = counts[option]!;
          return (
            <button
              key={option}
              className={option === kind ? "is-selected" : ""}
              aria-pressed={option === kind}
              onClick={() => setKind(option === kind ? null : option)}
            >
              {option === "pre" ? "예습" : "복습"} {count.cards}장
              {/* 안 본 걸린 카드가 있을 때만 수를 단다. 0이면 늘 서 있는 숫자가 된다. */}
              {count.open ? <span className="admin-tab-count">걸린 것 {count.open}</span> : null}
            </button>
          );
        })}
      </div>

      {kind ? (
        <>
          <ApkgNote />
          {error ? <p className="notice is-error">{error}</p> : null}
          {!list && !error ? <p className="notice">불러오는 중…</p> : null}
          {list && flagged.length ? (
            <p className="admin-summary">
              걸린 카드 {flagged.length}장 · 전체 {list.cards.length}장{" "}
              <button className="is-quiet" onClick={() => setOnlyFlagged((v) => !v)}>
                {onlyFlagged ? "전부 보기" : "걸린 것만"}
              </button>
            </p>
          ) : null}
          {list && focusId && !list.cards.some((card) => card.itemId === focusId) ? (
            <p className="notice is-warning">{focusId} 카드가 이 편에 없습니다 — 그 사이 다시 만들어졌을 수 있습니다.</p>
          ) : null}
          {shown.map((card) => (
            <CardRow
              key={card.itemId}
              card={card}
              onChanged={changed}
              focus={kind === fromHash && card.itemId === focusId}
            />
          ))}
        </>
      ) : null}
    </section>
  );
}
