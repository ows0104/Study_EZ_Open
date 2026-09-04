import { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "../api";
import type { AdminOverview, AppUser, JobBoard } from "../types";
import { jobMoving, jobOpen } from "../jobProgress";
import { MatchTab } from "./MatchTab";
import { ProgressTab } from "./ProgressTab";
import { RunnerBoard } from "./RunnerBoard";
import { UsersTab } from "./UsersTab";
import { isUnconfirmed, isUnmatched, pending, runnerAlive } from "./rows";

/**
 * 관리 화면의 겉틀.
 *
 * **한 화면에 다 붙어 있던 것을 탭으로 갈랐다**(2026-09-04 관리자 지시 — "너무
 * 많은 게 한 번에 붙어 있다"). 가른 축은 *지금 무엇을 하려고 왔는가*다.
 *
 *     진행   자료가 다 올라왔는가 — 체크리스트 · 예습 링크 · 검토 표시
 *     매칭   어느 시간의 강의인가 — 편별 매칭 · 과목 이름 잇기
 *     계정   승인
 *
 * **탭 밖에 남는 것이 둘 있다.** 요약 한 줄과 일감 판이다. 일감 판은 표보다
 * 먼저 서라는 지시(2026-09-01)를 받은 자리라 탭 뒤로 못 넣는다 — 도는 것도
 * 기다리는 것도 없으면 스스로 안 그린다. 탭 이름 옆 숫자도 같은 이유다:
 * 갈라 놓은 화면에서 남은 일이 다른 탭에 있으면, 그 일은 없는 것이 된다.
 */
/** 고른 탭에 표시를 남긴다. NavLink 기본값(`active`)은 이 앱의 이름이 아니다. */
const tabClass = ({ isActive }: { isActive: boolean }) => (isActive ? "is-active" : "");

export function AdminPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [board, setBoard] = useState<JobBoard | null>(null);
  const [users, setUsers] = useState<AppUser[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<AdminOverview>("/api/admin/overview")
      .then(setOverview)
      .catch((cause: Error) => setError(cause.message));
    // 일감은 따로 읽는다. `/overview`는 편마다 최근 일감을 하나씩 들고 있어서
    // **겹쳐 도는 편을 순서대로 볼 수 없다** — 그 답은 이쪽에 있다.
    api<JobBoard>("/api/admin/prequiz-jobs")
      .then(setBoard)
      .catch(() => {});
  }, []);

  // 계정은 폴링에서 뺀다. 10초마다 다시 읽어 봐야 사람이 그 사이에 가입하는
  // 화면이 아니다. 승인을 누른 뒤에만 다시 읽는다.
  const loadUsers = useCallback(() => {
    api<AppUser[]>("/api/admin/users")
      .then(setUsers)
      .catch(() => {});
  }, []);

  useEffect(load, [load]);
  useEffect(loadUsers, [loadUsers]);

  // 도는 일감이 있는 동안만 다시 읽는다. 한 편에 15분이 걸리는데 사람이 새로고침을
  // 눌러야 진행이 보이면, 그 진행은 없는 것과 같다. 끝나면 폴링도 멈춘다.
  //
  // **`held`는 안 센다.** 사람을 기다리는 줄이라 다시 읽어 봐야 같은 값이다.
  const working =
    (board?.running.length ?? 0) > 0 ||
    (board?.waiting.length ?? 0) > 0 ||
    (overview?.lectures ?? []).some((row) => jobMoving(row.prequizJob));
  useEffect(() => {
    if (!working) return;
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, [working, load]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!overview) return <p className="notice">불러오는 중…</p>;

  const incomplete = overview.lectures.filter((row) => pending(row).length > 0).length;
  const needsMatch = overview.lectures.filter((row) => isUnmatched(row) || isUnconfirmed(row)).length;
  const waitingUsers = (users ?? []).filter((row) => !row.isApproved).length;
  const queued = overview.lectures.filter((row) => jobOpen(row.prequizJob)).length;

  return (
    <div className="admin">
      <h1>관리</h1>
      <p className="admin-summary">
        강의 {overview.lectures.length}편 · 러너{" "}
        <strong>{runnerAlive(overview.runner) ? (overview.runner?.busy ? "만드는 중" : "대기") : "안 붙음"}</strong>
      </p>

      <RunnerBoard board={board} onBoard={setBoard} />

      {queued > 0 && !runnerAlive(overview.runner) ? (
        <p className="notice is-error">
          덱 일감 {queued}개가 기다리는데 <strong>러너가 안 붙어 있습니다.</strong> 만드는 것은
          노트북이 합니다 — 거기서 <code>python -m studyez agent</code>를 띄우면 이어서 집어 갑니다.
        </p>
      ) : null}

      {/* 숫자는 **남은 일**이다. 0이면 안 그린다 — 늘 서 있는 숫자는 곧 안 읽힌다. */}
      <nav className="admin-tabs" aria-label="관리 화면">
        <NavLink to="/admin" end className={tabClass} title="자료가 다 올라왔는가">
          진행
          {incomplete ? <span className="admin-tab-count">{incomplete}</span> : null}
        </NavLink>
        <NavLink to="/admin/match" className={tabClass} title="시간표에 못 붙었거나 아직 확인 안 한 편">
          매칭
          {needsMatch ? <span className="admin-tab-count">{needsMatch}</span> : null}
        </NavLink>
        <NavLink to="/admin/users" className={tabClass} title="승인을 기다리는 사람">
          계정
          {waitingUsers ? <span className="admin-tab-count">{waitingUsers}</span> : null}
        </NavLink>
      </nav>

      <Routes>
        <Route index element={<ProgressTab overview={overview} onChanged={load} />} />
        <Route path="match" element={<MatchTab overview={overview} onChanged={load} />} />
        <Route path="users" element={<UsersTab users={users} onChanged={loadUsers} />} />
        {/* 없는 탭은 첫 탭으로. 주소를 손으로 고쳤을 때 빈 화면을 주지 않는다. */}
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </div>
  );
}
