import type { AdminRow } from "../types";
import { lectureHref } from "../links";

/**
 * 어느 편인지 말하는 첫 칸. **탭마다 표가 달라도 이 칸은 같다** — 진행 표와
 * 매칭 표가 각자 그리면 한쪽만 저자·판이 빠진 채로 남는다.
 */
export function LectureCell({ row }: { row: AdminRow }) {
  return (
    <td>
      <a href={lectureHref(row)} target="_blank" rel="noreferrer">
        {row.title}
      </a>
      <small>
        {row.subject} · {row.runId} · {row.date}
        {row.author ? ` · ${row.author}${row.version ? `v${row.version}` : ""}` : ""}
      </small>
    </td>
  );
}
