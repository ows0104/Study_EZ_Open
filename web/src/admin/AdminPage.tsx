import { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "../api";
import type { AdminOverview, AppUser, JobBoard } from "../types";
import { jobMoving, jobOpen } from "../jobProgress";
import { LectureTab } from "./LectureTab";
import { QuizTab } from "./QuizTab";
import { UsersTab } from "./UsersTab";
import { isUnconfirmed, isUnmatched, pending, runnerAlive } from "./rows";

/**
 * 관리 화면의 겉틀.
 *
 * **한 화면에 다 붙어 있던 것을 탭으로 갈랐다**(2026-09-04 관리자 지시 — "너무
 * 많은 게 한 번에 붙어 있다"). 가른 축은 *지금 무엇을 하려고 왔는가*이고,
 * 셋의 내용과 순서를 관리자가 직접 적어 줬다.
 *
 *     퀴즈   위는 지금 도는 것과 진행도, 아래는 지금까지 만들어진 퀴즈들
 *     계정   신청이 들어온 계정 — 승인
 *     강의   매칭 · 과목 이름 잇기 · 편별 자료 체크리스트와 예습 링크
 *
 * **일감 판이 겉틀에서 「퀴즈」 탭 안으로 내려갔다.** 표보다 먼저 서라는
 * 2026-09-01 지시는 그 탭 안에서 지켜진다(맨 위). 다른 탭에서는 안 보이게
 * 되는 대신, 도는 일감 수가 탭 이름 옆에 선다 — 갈라 놓은 화면에서 남은 일이
 * 다른 탭에 있으면 그 일은 없는 것이 되기 때문이다. 러너가 안 붙었다는 경고만
 * 겉틀에 남긴다. 그건 어느 탭에 있든 손을 대야 하는 사실이다.
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

  // 퀴즈 탭의 숫자만 **남은 일이 아니라 도는 일**이다. 만들어진 덱 수를 적으면
  // 늘 서 있는 숫자가 되고, 그런 숫자는 곧 안 읽힌다.
  const inFlight = (board?.running.length ?? 0) + (board?.waiting.length ?? 0) + (board?.held.length ?? 0);
  const waitingUsers = (users ?? []).filter((row) => !row.isApproved).length;
  const lectureTodo = overview.lectures.filter(
    (row) => pending(row).length > 0 || isUnmatched(row) || isUnconfirmed(row),
  ).length;
  const queued = overview.lectures.filter((row) => jobOpen(row.prequizJob)).length;

  return (
    <div className="admin">
      <h1>관리</h1>
      <p className="admin-summary">
        강의 {overview.lectures.length}편 · 러너{" "}
        <strong>{runnerAlive(overview.runner) ? (overview.runner?.busy ? "만드는 중" : "대기") : "안 붙음"}</strong>
      </p>

      {queued > 0 && !runnerAlive(overview.runner) ? (
        <p className="notice is-error">
          덱 일감 {queued}개가 기다리는데 <strong>러너가 안 붙어 있습니다.</strong> 만드는 것은
          노트북이 합니다 — 거기서 <code>python -m studyez agent</code>를 띄우면 이어서 집어 갑니다.
        </p>
      ) : null}

      {/* 0이면 안 그린다 — 늘 서 있는 숫자는 곧 안 읽힌다. */}
      <nav className="admin-tabs" aria-label="관리 화면">
        <NavLink to="/admin" end className={tabClass} title="지금 도는 것과 기다리는 것">
          퀴즈
          {inFlight ? <span className="admin-tab-count">{inFlight}</span> : null}
        </NavLink>
        <NavLink to="/admin/users" className={tabClass} title="승인을 기다리는 신청">
          계정
          {waitingUsers ? <span className="admin-tab-count">{waitingUsers}</span> : null}
        </NavLink>
        <NavLink to="/admin/lectures" className={tabClass} title="체크가 남았거나 매칭을 확인해야 하는 편">
          강의
          {lectureTodo ? <span className="admin-tab-count">{lectureTodo}</span> : null}
        </NavLink>
      </nav>

      <Routes>
        <Route index element={<QuizTab overview={overview} board={board} onBoard={setBoard} />} />
        <Route path="users" element={<UsersTab users={users} onChanged={loadUsers} />} />
        <Route path="lectures" element={<LectureTab overview={overview} onChanged={load} />} />
        {/* 하루 나가 있던 주소다(2026-09-04). 눌러 둔 사람이 빈 화면을 보지 않게
            제자리로 보낸다. */}
        <Route path="match" element={<Navigate to="/admin/lectures" replace />} />
        {/* 없는 탭은 첫 탭으로. 주소를 손으로 고쳤을 때 빈 화면을 주지 않는다. */}
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </div>
  );
}
