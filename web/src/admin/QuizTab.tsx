import { useMemo, useState } from "react";
import type { AdminOverview, AdminRow, JobBoard } from "../types";
import { LectureCell } from "./LectureCell";
import { RunnerBoard } from "./RunnerBoard";

/**
 * **퀴즈 진행 상황.** 위는 지금 도는 것, 아래는 지금까지 만들어진 것.
 *
 * 관리자 지시(2026-09-04) — "위에는 현재 돌아가는 거 진행상황 및 진행도, 그
 * 아래에는 지금 만들어진 퀴즈들." 도는 것과 만들어진 것이 한 화면에 위아래로
 * 서면 「이게 끝나면 저 줄에 붙는다」가 그대로 보인다.
 *
 * **일감 판이 이 탭 안으로 들어왔다.** 전에는 탭 밖 겉틀에 있었다(표보다 먼저
 * 서라는 2026-09-01 지시). 다른 탭에서도 보이던 것이 안 보이게 되는 대신,
 * 도는 일감 수가 탭 이름 옆에 선다.
 */
type Filter = "all" | "pre" | "main" | "flagged";

/** 만들어진 퀴즈 한 줄. 편과 갈래가 짝이다 — 한 편에서 예습·복습 둘이 나온다. */
type Deck = {
  row: AdminRow;
  kind: "pre" | "main";
  itemCount: number;
  reviewFlagged: number;
  slidesUnused: number;
  builtAt: string | null;
  /** 덱 파일(`.apkg`)이 실제로 올라와 있나. 기록만 있고 파일이 없을 수 있다. */
  hasFile: boolean;
  /** 웹 풀이 문항 수. 예습만 있다. */
  webItems: number;
};

const kindLabels = { pre: "Pre-Quiz", main: "Main-Quiz" } as const;

/**
 * 만들어진 퀴즈를 편에서 뽑아낸다.
 *
 * **두 곳을 다 본다** — 러너가 적은 기록(`runMeta`)과 올라온 덱 파일(`has`).
 * 한쪽만 보면 조용히 빠지는 줄이 생긴다. 기록만 있고 파일이 없는 것은 그 자체가
 * 봐야 할 신호라 지우지 않고 표시로 남긴다.
 */
function decks(lectures: AdminRow[]): Deck[] {
  const out: Deck[] = [];
  for (const row of lectures) {
    for (const kind of ["pre", "main"] as const) {
      const meta = row.runMeta[kind];
      const hasFile = Boolean(row.has[`${kind}_apkg`]);
      if (!meta && !hasFile) continue;
      out.push({
        row,
        kind,
        itemCount: meta?.itemCount ?? 0,
        reviewFlagged: meta?.reviewFlagged ?? 0,
        slidesUnused: meta?.slidesUnused ?? 0,
        builtAt: meta?.builtAt ?? null,
        hasFile,
        webItems: kind === "pre" ? row.preItemCount : 0,
      });
    }
  }
  // 새로 만든 것이 위다. 만든 날이 없는 줄(기록이 없는 덱)은 강의 날짜로 세운다 —
  // 아래로 몰아 두면 정작 봐야 할 줄이 표 끝에 숨는다.
  return out.sort((a, b) => (b.builtAt ?? b.row.date).localeCompare(a.builtAt ?? a.row.date));
}

export function QuizTab({
  overview,
  board,
  onBoard,
}: {
  overview: AdminOverview;
  board: JobBoard | null;
  onBoard: (next: JobBoard) => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const all = useMemo(() => decks(overview.lectures), [overview]);
  const rows = useMemo(() => {
    if (filter === "flagged") return all.filter((deck) => deck.reviewFlagged > 0);
    if (filter === "all") return all;
    return all.filter((deck) => deck.kind === filter);
  }, [all, filter]);

  return (
    <>
      <RunnerBoard board={board} onBoard={onBoard} />

      <h2 className="admin-section">만들어진 퀴즈 {all.length}</h2>
      <div className="admin-filters" role="group" aria-label="거르기">
        {(
          [
            ["all", "전체"],
            ["pre", "Pre-Quiz"],
            ["main", "Main-Quiz"],
            ["flagged", "검토 표시"],
          ] as const
        ).map(([key, label]) => (
          <button key={key} className={filter === key ? "is-active" : ""} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      <table className="admin-table">
        <thead>
          <tr>
            <th>강의</th>
            <th>갈래</th>
            <th>문항</th>
            <th>만든 날</th>
            <th>표시</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((deck) => (
            <tr key={`${deck.row.subject}/${deck.row.runId}/${deck.kind}`}>
              <LectureCell row={deck.row} />
              <td>
                {kindLabels[deck.kind]}
                {/* 기록은 있는데 덱 파일이 없다. 사람이 받을 것이 없다는 뜻이라
                    조용히 넘기지 않는다. */}
                {deck.hasFile ? null : <span className="tag is-warn">덱 파일 없음</span>}
              </td>
              <td>
                {deck.itemCount || "—"}
                {deck.kind === "pre" && deck.webItems ? <small>웹 풀이 {deck.webItems}</small> : null}
              </td>
              {/* 만든 날은 러너가 적는다. 안 적혀 있으면 **모른다**고 말한다 —
                  강의 날짜로 메우면 만든 날처럼 읽힌다. */}
              <td>{deck.builtAt ? deck.builtAt.slice(0, 10) : <small>기록 없음</small>}</td>
              <td>
                {/* 검토 표시가 남은 덱은 사람이 카드 뒷면 경고 박스를 보기 전까지
                    배포해서는 안 된다. */}
                {deck.reviewFlagged ? <span className="tag is-warn">검토 {deck.reviewFlagged}</span> : null}
                {deck.slidesUnused ? <small>미사용 슬라이드 {deck.slidesUnused}</small> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length ? <p className="notice">해당하는 퀴즈가 없습니다.</p> : null}
    </>
  );
}
