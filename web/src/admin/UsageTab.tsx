import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { UsageBoard, UsageDetail, UsageRow } from "../types";

/**
 * 누가 이 사이트를 쓰고 있는가.
 *
 * 2026-09-19 관리자 지시 — 「사용자별 사이트 이용현황을 내가 볼 수 있게 하고 싶어.」
 * 한 줄이 한 사람이고, 이름을 누르면 그 사람의 강의별 내역이 아래로 펴진다.
 *
 * **여기 수는 웹에서 한 것과 받아 간 것뿐이다.** 덱은 apkg로 나가 안키에서 풀리고
 * 그 진행은 서버가 못 본다. 그래서 "받기"는 받아 간 것이지 푼 것이 아니고, 그렇게
 * 읽히게 그리지 않는다 — 사연은 `server/app/routes/usage.py` 머리에 있다.
 *
 * **목록을 이 탭 안에서 읽는다.** 계정 탭과 다른 점이다 — 그쪽은 탭 이름 옆에
 * 대기 수를 세워야 해서 위에서 읽어 내려온다. 이 탭에는 그런 숫자가 없다.
 * 늘 서 있는 수(전체 사용자 수 같은 것)를 탭 옆에 달면 곧 아무도 안 읽는다.
 */
export function UsageTab() {
  const [board, setBoard] = useState<UsageBoard | null>(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState("");
  const [detail, setDetail] = useState<UsageDetail | null>(null);
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    api<UsageBoard>("/api/admin/usage")
      .then(setBoard)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  // 펼 때마다 다시 읽는다. 사람 수만큼 미리 받아 두면 첫 화면이 느려지고,
  // 관리자가 한 번에 보는 사람은 하나다.
  const open = useCallback((row: UsageRow) => {
    if (openId === row.id) {
      setOpenId("");
      return;
    }
    setOpenId(row.id);
    setDetail(null);
    setDetailError("");
    api<UsageDetail>(`/api/admin/usage/${row.id}`)
      .then(setDetail)
      .catch((cause: Error) => setDetailError(cause.message));
  }, [openId]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!board) return <p className="notice">불러오는 중…</p>;

  const now = new Date(board.now);
  const active = board.users.filter((row) => row.recentGrades > 0).length;
  const never = board.users.filter((row) => !row.lastAt).length;

  return (
    <section className="admin-usage">
      {/* 세 수가 서로 다른 것을 말한다 — 얼마나 있나 · 지금 쓰나 · 한 번도 안 왔나. */}
      <p className="admin-summary">
        전체 {board.users.length}명 · 최근 {board.recentDays}일에 푼 사람{" "}
        <strong>{active}명</strong>
        {never ? <> · 한 번도 안 연 사람 {never}명</> : null}
      </p>

      <table className="admin-table">
        <thead>
          <tr>
            <th>이메일</th>
            <th>마지막</th>
            <th title={`최근 ${board.recentDays}일 동안 카드를 찍은 횟수`}>
              최근 {board.recentDays}일
            </th>
            <th title="웹에서 푼 카드 수. 안키에서 푼 것은 서버에 안 남는다">예습 · 복습</th>
            <th title="웹으로 풀었거나 파일을 받아 간 편">편</th>
            <th title="받기 버튼을 누른 자료의 갈래 수. 받아 간 것이지 푼 것이 아니다">받기</th>
          </tr>
        </thead>
        <tbody>
          {board.users.map((row) => (
            <UserRows
              key={row.id}
              row={row}
              now={now}
              isOpen={openId === row.id}
              detail={openId === row.id ? detail : null}
              detailError={openId === row.id ? detailError : ""}
              onToggle={() => open(row)}
            />
          ))}
        </tbody>
      </table>
    </section>
  );
}

function UserRows({
  row,
  now,
  isOpen,
  detail,
  detailError,
  onToggle,
}: {
  row: UsageRow;
  now: Date;
  isOpen: boolean;
  detail: UsageDetail | null;
  detailError: string;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className={row.lastAt ? "" : "is-idle"}>
        <td>
          <button className="admin-usage-name" onClick={onToggle} aria-expanded={isOpen}>
            {isOpen ? "▾" : "▸"} {row.email || row.id}
          </button>
          {row.isAdmin ? <span className="tag is-ok">관리자</span> : null}
          {/* **0이 「안 썼다」인지 「못 썼다」인지를 가르는 표시다.** 승인이 안 난
              사람은 아무것도 못 보므로 0인 것이 당연하다. */}
          {row.hasAccess ? null : <span className="tag">승인 대기</span>}
        </td>
        <td>{since(row.lastAt, now)}</td>
        <td className="num">{row.recentGrades || "—"}</td>
        <td className="num">
          {row.pre.cards || 0} · {row.main.cards || 0}
        </td>
        <td className="num">{row.lectures || "—"}</td>
        <td className="num">{row.grabs.kinds || "—"}</td>
      </tr>
      {isOpen ? (
        <tr className="admin-usage-detail">
          <td colSpan={6}>
            {detailError ? <p className="notice is-error">{detailError}</p> : null}
            {!detail && !detailError ? <p className="notice">불러오는 중…</p> : null}
            {detail ? <LectureList detail={detail} now={now} /> : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}

function LectureList({ detail, now }: { detail: UsageDetail; now: Date }) {
  // 손댄 편이 하나도 없는 것도 답이다. 빈 표로 두면 못 불러온 것과 같아 보인다.
  if (!detail.lectures.length) return <p className="notice">아직 손댄 편이 없습니다.</p>;
  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>강의</th>
          <th title="웹에서 푼 카드 · 괄호는 본인이 맞다고 찍은 수(서버 판정이 아니다)">예습</th>
          <th>복습</th>
          <th title="받기 버튼을 누른 자료">받기</th>
          <th>마지막</th>
        </tr>
      </thead>
      <tbody>
        {detail.lectures.map((row) => (
          <tr key={`${row.subject}/${row.runId}`}>
            <td>
              {/* 지워진 편은 제목이 없다. 그때는 run_id로 그린다 — 줄을 버리면
                  받아 간 수가 위의 요약과 안 맞는다. */}
              {row.title || row.runId}
              <small>
                {row.subject} · {row.date ?? row.runId}
                {row.preview ? " · 예습 대화" : ""}
              </small>
            </td>
            <td className="num">{cards(row.pre)}</td>
            <td className="num">{cards(row.main)}</td>
            <td>{row.grabs.length ? row.grabs.map(grabLabel).join(", ") : "—"}</td>
            <td>{since(row.lastAt, now)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** 푼 카드 수. 괄호 안은 **본인이 맞다고 찍은 것**이라 정답률로 안 적는다. */
function cards(track: { cards: number; selfCorrect: number }): string {
  if (!track.cards) return "—";
  return `${track.cards} (${track.selfCorrect})`;
}

const GRAB_LABELS: Record<string, string> = {
  notes_prev: "작년 필기",
  notes_current: "올해 필기",
  pre_apkg: "예습덱",
  main_apkg: "복습덱",
};

function grabLabel(kind: string): string {
  return GRAB_LABELS[kind] ?? kind;
}

/**
 * 얼마나 전인가.
 *
 * **날짜보다 이것이 답에 가깝다.** 관리자가 보는 것은 "9월 12일"이 아니라
 * "일주일째 안 들어왔다"이고, 그 판단을 날짜에서 사람이 다시 계산하게 만들면
 * 목록을 훑는 일이 산수가 된다. 오래된 것만 날짜로 적는다.
 */
function since(iso: string | null, now: Date): string {
  if (!iso) return "없음";
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "없음";
  const hours = (now.getTime() - when.getTime()) / 3_600_000;
  if (hours < 1) return "방금";
  if (hours < 24) return `${Math.floor(hours)}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 14) return `${days}일 전`;
  return when.toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}
