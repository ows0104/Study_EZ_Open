import { useMemo, useState } from "react";
import type { AdminOverview, AdminRow } from "../types/admin";
import type { JobBoard } from "../types/jobs";
import { LectureCell } from "./LectureCell";
import { RunnerBoard } from "./RunnerBoard";

/**
 * **퀴즈 진행 상황.** 위는 지금 도는 것, 아래는 지금까지 만들어진 것.
 *
 * 관리자 지시(2026-09-04) — "위에는 현재 돌아가는 거 진행상황 및 진행도, 그
 * 아래에는 지금 만들어진 퀴즈들." 도는 것과 만들어진 것이 한 화면에 위아래로
 * 서면 「이게 끝나면 저 줄에 붙는다」가 그대로 보인다.
 *
 * **한 번에 열 줄만 편다**(같은 지시). 학기가 가면 수백 줄이 되는 목록인데 그
 * 아래에는 아무것도 없어서, 다 펴 두면 최신 열 줄을 보려고 매번 위를 찾아야 한다.
 */
type Filter = "all" | "pre" | "main" | "flagged" | "stale";

/** 처음에 펴는 줄 수. 나머지는 눌러서 펼친다. */
const FIRST_PAGE = 10;

/** 「더 보기」 한 번에 붙는 줄 수. */
const MORE = 20;

/** 만들어진 퀴즈 한 줄. 편과 갈래가 짝이다 — 한 편에서 예습·복습 둘이 나온다. */
type Deck = {
  row: AdminRow;
  kind: "pre" | "main";
  itemCount: number;
  reviewFlagged: number;
  slidesUnused: number;
  builtAt: string | null;
  /** 이 덱을 구운 필기 판. 파일명을 못 읽었으면 `null`이다. */
  sourceVersion: number | null;
  /** 지금 올라와 있는 필기 판. */
  lectureVersion: number | null;
  /** 덱 파일(`.apkg`)이 실제로 올라와 있나. 기록만 있고 파일이 없을 수 있다. */
  hasFile: boolean;
  /** 웹 풀이 문항 수. 예습만 있다. */
  webItems: number;
};

const kindLabels = { pre: "Pre-Quiz", main: "Main-Quiz" } as const;

/**
 * **옛 판으로 구운 덱인가.** 판을 둘 다 알 때만 말한다.
 *
 * 새 판이 올라왔는데 한 갈래만 다시 구우면 그 편의 두 줄이 서로 다른 판을 들게
 * 되고, 「일부만 교체」가 바로 그 모양이다(2026-09-04 관리자 지시).
 */
function stale(deck: Deck): boolean {
  return deck.sourceVersion !== null && deck.lectureVersion !== null && deck.sourceVersion < deck.lectureVersion;
}

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
        sourceVersion: meta?.sourceVersion ?? null,
        lectureVersion: row.version,
        hasFile,
        webItems: kind === "pre" ? row.preItemCount : 0,
      });
    }
  }
  // 새로 구운 것이 위다. 만든 때가 없는 줄(기록이 없는 덱)은 강의 날짜로 세운다 —
  // 아래로 몰아 두면 정작 봐야 할 줄이 표 끝에 숨는다.
  return out.sort((a, b) => (b.builtAt ?? b.row.date).localeCompare(a.builtAt ?? a.row.date));
}

/**
 * 만든 때. **러너가 적어 준 글자를 그대로 자른다.**
 *
 * 시간대를 다시 계산하지 않는다 — 이 값은 덱 파일을 구운 노트북의 시각이고,
 * 브라우저 시간대로 옮기면 "몇 시에 구웠나"가 실제와 어긋난다.
 */
function builtLabel(iso: string): string {
  return iso.replace("T", " ").slice(0, 16);
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
  const [shown, setShown] = useState(FIRST_PAGE);
  const all = useMemo(() => decks(overview.lectures), [overview]);
  const rows = useMemo(() => {
    if (filter === "flagged") return all.filter((deck) => deck.reviewFlagged > 0);
    if (filter === "stale") return all.filter(stale);
    if (filter === "all") return all;
    return all.filter((deck) => deck.kind === filter);
  }, [all, filter]);
  const staleCount = useMemo(() => all.filter(stale).length, [all]);

  // 거르기를 바꾸면 다시 열 줄부터. 앞 갈래에서 펼쳐 둔 만큼이 남아 있으면
  // 「더 보기」가 이미 눌린 것처럼 보인다.
  function pick(next: Filter) {
    setFilter(next);
    setShown(FIRST_PAGE);
  }

  const rest = rows.length - shown;

  return (
    <>
      <RunnerBoard board={board} onBoard={onBoard} />

      <h2 className="admin-section">만들어진 퀴즈 {all.length}</h2>
      <div className="admin-filters" role="group" aria-label="거르기">
        {(
          [
            ["all", `전체 ${all.length}`],
            ["pre", "Pre-Quiz"],
            ["main", "Main-Quiz"],
            ["flagged", "검토 표시"],
            // 옛 판으로 구운 덱이 없으면 그 갈래도 안 그린다. 늘 서 있는 0은
            // 곧 안 읽힌다.
            ...(staleCount ? ([["stale", `옛 판 ${staleCount}`]] as const) : []),
          ] as const
        ).map(([key, label]) => (
          <button key={key} className={filter === key ? "is-active" : ""} onClick={() => pick(key as Filter)}>
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
            <th>만든 때</th>
            <th>표시</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, shown).map((deck) => (
            <tr key={`${deck.row.subject}/${deck.row.runId}/${deck.kind}`}>
              <LectureCell row={deck.row} />
              <td>
                {kindLabels[deck.kind]}
                {/* 무슨 판으로 구웠나. 모르면 안 적는다. */}
                {deck.sourceVersion !== null ? <small>v{deck.sourceVersion}로 구움</small> : null}
              </td>
              <td>
                {deck.itemCount || "—"}
                {deck.kind === "pre" && deck.webItems ? <small>웹 풀이 {deck.webItems}</small> : null}
              </td>
              {/* 만든 때는 러너가 적는다. 안 적혀 있으면 **모른다**고 말한다 —
                  강의 날짜로 메우면 만든 때처럼 읽힌다. */}
              <td className="tabular">{deck.builtAt ? builtLabel(deck.builtAt) : <small>기록 없음</small>}</td>
              <td>
                {/* 판이 올라갔는데 이 갈래는 옛 자료로 구운 상태. 한 편의 두 줄
                    중 하나만 이 표시를 달면 그것이 「일부만 교체」다. */}
                {stale(deck) ? (
                  <span className="tag is-warn">
                    옛 판 v{deck.sourceVersion} · 지금 v{deck.lectureVersion}
                  </span>
                ) : null}
                {/* 기록은 있는데 덱 파일이 없다. 사람이 받을 것이 없다는 뜻이다. */}
                {deck.hasFile ? null : <span className="tag is-warn">덱 파일 없음</span>}
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
      {rest > 0 ? (
        <div className="admin-more">
          <button onClick={() => setShown(shown + MORE)}>{Math.min(MORE, rest)}개 더 보기</button>
          <small>
            {shown}/{rows.length}
          </small>
        </div>
      ) : null}
    </>
  );
}
