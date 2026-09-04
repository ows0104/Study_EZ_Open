import { useMemo, useState } from "react";
import { api } from "../api";
import type { AppUser } from "../types";

/**
 * 계정 승인.
 *
 * 가입은 누구나 하지만 승인 전에는 아무것도 안 보인다. Supabase에 메일 주소를
 * 넣은 사람과 이 학년 학생이 같지 않기 때문이고, 그 판단은 사람이 한다.
 *
 * **목록은 위(`AdminPage`)에서 읽어 내려온다.** 탭 뒤로 들어간 화면이라, 여기서
 * 읽으면 이 탭을 열기 전에는 기다리는 사람이 몇인지 알 길이 없다 — 그 수는 탭
 * 이름 옆에 선다.
 */
export function UsersTab({ users, onChanged }: { users: AppUser[] | null; onChanged: () => void }) {
  const [busy, setBusy] = useState("");
  // **신청이 들어온 계정이 먼저다**(2026-09-04 관리자 지시). 승인이 이 화면에서
  // 하는 유일한 일이라, 기다리는 사람이 목록 아래에 섞여 있으면 화면이 할 일을
  // 안 말한다. 그 안에서는 들어온 순서 그대로다 — 서버가 그렇게 준다.
  const sorted = useMemo(
    () => [...(users ?? [])].sort((a, b) => Number(a.isApproved) - Number(b.isApproved)),
    [users],
  );

  if (!users) return <p className="notice">불러오는 중…</p>;
  const waiting = users.filter((row) => !row.isApproved).length;

  async function setApproval(row: AppUser, isApproved: boolean) {
    setBusy(row.id);
    try {
      await api(`/api/admin/users/${row.id}/approval`, {
        method: "PUT",
        body: JSON.stringify({ isApproved }),
      });
      onChanged();
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="admin-users">
      {/* 기다리는 사람이 없다는 것도 답이다. 빈 화면으로 두면 못 불러온 것과 같다. */}
      <p className="admin-summary">
        {waiting ? (
          <>
            승인 대기 <strong>{waiting}명</strong> · 전체 {users.length}명
          </>
        ) : (
          <>기다리는 신청 없음 · 전체 {users.length}명</>
        )}
      </p>
      <table className="admin-table">
        <thead>
          <tr>
            <th>이메일</th>
            <th>상태</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.id} className={row.isApproved ? "" : "is-unmatched"}>
              <td>
                {row.email || row.id}
                {row.isAdmin ? <span className="tag is-ok">관리자</span> : null}
              </td>
              <td>{row.isApproved ? "승인됨" : "대기"}</td>
              <td>
                <button
                  disabled={busy === row.id}
                  onClick={() => setApproval(row, !row.isApproved)}
                >
                  {row.isApproved ? "승인 취소" : "승인"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
