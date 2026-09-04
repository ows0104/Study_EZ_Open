import { useState } from "react";
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

  if (!users) return <p className="notice">불러오는 중…</p>;

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
      <table className="admin-table">
        <thead>
          <tr>
            <th>이메일</th>
            <th>상태</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {users.map((row) => (
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
