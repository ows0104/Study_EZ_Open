import { useMemo, useState } from "react";
import { api } from "../api";
import type { AdminOverview, AdminRow } from "../types";
import { CourseAliases } from "./CourseAliases";
import { LectureCell } from "./LectureCell";
import { isUnconfirmed, isUnmatched } from "./rows";

type Candidate = {
  id: string;
  startTime: string;
  slot: number | null;
  title: string;
  details: string;
  professor: string;
  category: string;
};

/**
 * **어느 시간의 강의인가**만 보는 탭.
 *
 * 편별 매칭과 과목 이름 잇기를 한 자리에 뒀다. 둘은 같은 일의 앞뒤다 — 못 붙은
 * 편을 보다가 "이 과목이 폴더 이름과 다르구나"를 알게 되면 바로 아래에서 잇는다.
 * 전에는 그 둘 사이에 표 전체와 계정 목록이 끼어 있었다.
 */
export function MatchTab({ overview, onChanged }: { overview: AdminOverview; onChanged: () => void }) {
  const [onlyTodo, setOnlyTodo] = useState(false);

  const rows = useMemo(() => {
    const all = overview.lectures;
    return onlyTodo ? all.filter((row) => isUnmatched(row) || isUnconfirmed(row)) : all;
  }, [overview, onlyTodo]);

  return (
    <>
      <div className="admin-filters" role="group" aria-label="거르기">
        <button className={onlyTodo ? "" : "is-active"} onClick={() => setOnlyTodo(false)}>
          전체
        </button>
        <button className={onlyTodo ? "is-active" : ""} onClick={() => setOnlyTodo(true)}>
          확인 필요
        </button>
      </div>

      {/* 두 칸짜리 표라 화면 폭을 다 주면 강의 이름과 매칭 사이가 손가락
          하나만큼 벌어진다. 읽는 폭에서 끊는다. */}
      <table className="admin-table is-narrow">
        <thead>
          <tr>
            <th>강의</th>
            <th>시간표 매칭</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <MatchRow key={`${row.subject}/${row.runId}`} row={row} onChanged={onChanged} />
          ))}
        </tbody>
      </table>
      {!rows.length ? <p className="notice">해당하는 강의가 없습니다.</p> : null}

      <CourseAliases overview={overview} onChanged={onChanged} />
    </>
  );
}

function MatchRow({ row, onChanged }: { row: AdminRow; onChanged: () => void }) {
  const base = `/api/admin/lectures/${encodeURIComponent(row.subject)}/${encodeURIComponent(row.runId)}`;
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);

  async function setMatch(timetableEventId: string | null) {
    await api(`${base}/match`, {
      method: "PUT",
      body: JSON.stringify({ timetableEventId, confirmed: true }),
    });
    onChanged();
  }

  return (
    <tr className={row.match.timetableEventId ? "" : "is-unmatched"}>
      <LectureCell row={row} />

      <td>
        {row.match.timetableEventId ? (
          <>
            <span className={row.match.confirmed ? "tag is-ok" : "tag"}>
              {row.match.confirmed ? "확인함" : "자동 매칭"}
            </span>
            <small>{(row.match.eventDetails || row.match.eventTitle || "").split("\n")[0]}</small>
          </>
        ) : (
          <span className="tag is-warn">못 붙음</span>
        )}
        <div className="row">
          {!row.match.confirmed && row.match.timetableEventId ? (
            <button onClick={() => setMatch(row.match.timetableEventId)}>맞음</button>
          ) : null}
          <button
            className="is-quiet"
            onClick={async () => {
              if (candidates) return setCandidates(null);
              setCandidates(await api<Candidate[]>(`/api/admin/timetable-events?date=${row.date}`));
            }}
          >
            {candidates ? "닫기" : "고르기"}
          </button>
        </div>
        {candidates ? (
          <ul className="candidates">
            {candidates.map((candidate) => (
              <li key={candidate.id}>
                <button onClick={() => setMatch(candidate.id)}>
                  {candidate.startTime} {(candidate.details || candidate.title).split("\n")[0]}
                </button>
              </li>
            ))}
            <li>
              <button className="is-quiet" onClick={() => setMatch(null)}>
                연결 끊기
              </button>
            </li>
          </ul>
        ) : null}
      </td>
    </tr>
  );
}
