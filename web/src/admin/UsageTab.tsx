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
  const active = board.users.filter((row) => row.recentCards > 0).length;
  const never = board.users.filter((row) => !row.lastAt).length;

  return (
    <section className="admin-usage">
      {/* 세 수가 서로 다른 것을 말한다 — 얼마나 있나 · 지금 쓰나 · 한 번도 안 왔나. */}
      <p className="admin-summary">
        전체 {board.users.length}명 · 최근 {board.recentDays}일에 푼 사람{" "}
        <strong>{active}명</strong>
        {never ? <> · 한 번도 안 연 사람 {never}명</> : null}
      </p>

      {/* **접속과 링크 열기는 표가 선 날부터만 찬다.** 이 줄이 없으면 그 전의 0이
          「안 들어왔다」로 읽힌다 — 루트 CLAUDE.md 의 함정 ③ 이 그것이다. */}
      <p className="admin-note">
        접속은 {stamp(board.visitsSince)}부터 · 예습 링크 열기는 {stamp(board.opensSince)}부터
        남습니다. 그 전에 한 것은 어디에도 안 남아 있어 0으로 보입니다.
      </p>

      <table className="admin-table">
        <thead>
          <tr>
            <th>이메일</th>
            <th>마지막</th>
            <th title={`최근 ${board.recentDays}일 중 들어온 날 · 밑은 누적으로 들어온 횟수`}>
              접속
            </th>
            {/* **카드 수다.** 「찍기」로 적었더니 접속 횟수로 읽혔다(2026-09-19).
                같은 카드를 세 번 봐도 한 장이라, 「이 주에 무엇을 봤나」에 답한다. */}
            <th title={`최근 ${board.recentDays}일 동안 푼 카드 수. 같은 카드를 여러 번 봐도 한 장이다`}>
              최근 {board.recentDays}일 카드
            </th>
            <th title="웹에서 푼 카드 수(예습 · 복습). 안키에서 푼 것은 서버에 안 남는다">
              웹 풀이
            </th>
            <th title="받기 버튼을 누른 자료. 받아 간 것이지 푼 것이 아니다">덱 받기</th>
            <th title="우리 화면에서 예습 링크를 누른 횟수(기본 · 개인). 링크를 복사해 받은 사람이 연 것은 안 들어온다">
              예습 링크
            </th>
            <th title="웹으로 풀었거나 파일을 받아 간 편">편</th>
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
        <td className="num">
          {row.visits.days ? (
            <>
              {row.visits.recentDays}일<small>누적 {row.visits.times}번</small>
            </>
          ) : (
            "—"
          )}
        </td>
        <td className="num">{row.recentCards ? `${row.recentCards}장` : "—"}</td>
        {/* **웹에서 푸는 사람과 받아 가는 사람은 다른 사람이다.** 한 칸에 합쳐
            적으면 그 둘이 안 갈린다 — 편 수를 각자 밑에 붙여 둔다. */}
        <td className="num">
          {row.pre.cards || row.main.cards ? (
            <>
              {row.pre.cards} · {row.main.cards}
              <small>{row.webLectures}편</small>
            </>
          ) : (
            "—"
          )}
        </td>
        <td className="num">
          {row.grabLectures ? (
            <>
              {row.grabLectures}편<small>{row.grabs.kinds}갈래</small>
            </>
          ) : (
            "—"
          )}
        </td>
        <td className="num">
          {/* **기본과 개인을 나란히 둔다.** 반이 같이 읽는 대화를 쓰는 사람과 자기
              대화를 쓰는 사람이 갈리는지가 이 둘을 붙여 놓아야 보인다. */}
          {row.opens.share || row.opens.mine ? (
            <>
              기본 {row.opens.share} · 개인 {row.opens.mine}
            </>
          ) : (
            "—"
          )}
          {/* 아무것도 없는 사람 밑에 「저장 0」을 세우지 않는다. 늘 서 있는 0은
              줄을 채우기만 하고 아무 말도 안 한다. */}
          {row.previews || row.prompt.custom ? (
            <small>
              {row.previews ? `저장 ${row.previews}` : ""}
              {row.previews && row.prompt.custom ? " · " : ""}
              {row.prompt.custom ? "프롬프트 고침" : ""}
            </small>
          ) : null}
        </td>
        <td className="num">{row.lectures || "—"}</td>
      </tr>
      {isOpen ? (
        <tr className="admin-usage-detail">
          <td colSpan={8}>
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
  return (
    <>
      {/* 고쳐 쓴 사람의 문구는 그대로 보여 준다 — 「고쳤다」만으로는 어떻게 쓰는지
          알 수 없고, 그것이 이 칸을 보는 이유다. */}
      <p className="admin-summary">
        예습 프롬프트{" "}
        {detail.user.previewPrompt ? (
          <q>{detail.user.previewPrompt}</q>
        ) : (
          <span className="tag">기본 문구</span>
        )}
      </p>
      {detail.lectures.length ? (
        <LectureTable detail={detail} now={now} />
      ) : (
        // 손댄 편이 없는 것도 답이다. 빈 표로 두면 못 불러온 것과 같아 보인다.
        <p className="notice">아직 손댄 편이 없습니다.</p>
      )}
    </>
  );
}

function LectureTable({ detail, now }: { detail: UsageDetail; now: Date }) {
  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>강의</th>
          <th title="웹에서 푼 카드 · 괄호는 본인이 맞다고 찍은 수(서버 판정이 아니다)">예습</th>
          <th>복습</th>
          <th title="받기 버튼을 누른 자료">받기</th>
          <th title="우리 화면에서 이 편의 예습 링크를 누른 횟수">링크</th>
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
                {/* 기본 링크가 아니라 이 사람이 저장해 둔 개인 대화다. */}
                {row.preview ? " · 개인 대화" : ""}
              </small>
            </td>
            <td className="num">{cards(row.pre)}</td>
            <td className="num">{cards(row.main)}</td>
            <td>{row.grabs.length ? row.grabs.map(grabLabel).join(", ") : "—"}</td>
            <td className="num">
              {row.opens.share || row.opens.mine
                ? `기본 ${row.opens.share} · 개인 ${row.opens.mine}`
                : "—"}
            </td>
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

/** 「언제부터」 한 줄. 아직 한 줄도 안 쌓였으면 그렇게 적는다 — 날짜 자리를
 *  비워 두면 문장이 「부터 남습니다」가 된다. */
function stamp(iso: string | null): string {
  if (!iso) return "(아직 없음)";
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "(아직 없음)";
  return when.toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
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
