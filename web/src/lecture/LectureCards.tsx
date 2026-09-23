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
 * 사이드 패널에서도 고치기로 넘어갈 수 있게 해줘.」
 *
 * **검토 표시된 카드만 든다**(같은 날 관리자 — 「카드 검토할때 검토표시된것만 확인하고
 * 고치려고 하는 거였어. 풀이화면에서는 전체 다 가능하지만.」). 한동안 「전부 보기」로
 * 이 편의 카드 전부를 펼 수 있었는데 걷어냈다. 표시가 없는 카드를 고치는 길은 하나 —
 * 풀이 화면의 「이 카드 고치기」가 한 장을 지목해 오는 것(`#cards-<갈래>-<id>`)이고,
 * 그때만 그 한 장이 목록 맨 위에 선다.
 *
 * **열 때까지 안 읽는다.** 사이드 패널이나 풀이 화면에서 넘어오면 바로 편다.
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
  const target = readHash();
  // 풀이 화면에서 지목해 온 한 장. 그 갈래에 표시된 카드가 없어도 그 갈래는 선다.
  const focusKind = target?.itemId && counts[target.kind] ? target.kind : undefined;
  const focusId = focusKind ? target!.itemId : "";
  const kinds = (["pre", "main"] as const).filter(
    (kind) => (counts[kind]?.flagged ?? 0) > 0 || kind === focusKind,
  );
  const fromHash = target && kinds.includes(target.kind) ? target.kind : undefined;
  const [kind, setKind] = useState<Kind | null>(fromHash ?? null);
  const [list, setList] = useState<LectureCardList | null>(null);
  const [error, setError] = useState("");
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

  const focusHere = kind === focusKind ? focusId : "";
  const focused = focusHere ? list?.cards.find((card) => card.itemId === focusHere) : undefined;
  const flagged = list?.cards.filter((card) => card.flag && card.itemId !== focusHere) ?? [];
  const shown = focused ? [focused, ...flagged] : flagged;

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
              {option === "pre" ? "예습" : "복습"} 검토 표시 {count.flagged}장
              {/* 안 본 것이 있을 때만 단다. 0이면 늘 서 있는 숫자가 된다. */}
              {count.open ? <span className="admin-tab-count">안 봄 {count.open}</span> : null}
            </button>
          );
        })}
      </div>

      {kind ? (
        <>
          <ApkgNote />
          {error ? <p className="notice is-error">{error}</p> : null}
          {!list && !error ? <p className="notice">불러오는 중…</p> : null}
          {list && focusHere && !focused ? (
            <p className="notice is-warning">{focusHere} 카드가 이 편에 없습니다 — 그 사이 다시 만들어졌을 수 있습니다.</p>
          ) : null}
          {list && !shown.length && !(focusHere && !focused) ? (
            <p className="notice">검토 표시된 카드가 없습니다.</p>
          ) : null}
          {shown.map((card) => (
            <CardRow key={card.itemId} card={card} onChanged={changed} focus={card.itemId === focusHere} />
          ))}
        </>
      ) : null}
    </section>
  );
}
