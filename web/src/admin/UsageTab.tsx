import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { UsageBoard, UsageDetail, UsageRow } from "../types/account";

/**
 * 누가 이 사이트를 쓰고 있는가.
 *
 * 2026-09-19 관리자 지시 — 「사용자별 사이트 이용현황을 내가 볼 수 있게 하고 싶어.」
 * 한 줄이 한 사람이고, 이름을 누르면 그 사람의 강의별 내역이 아래로 펴진다.
 *
 * ## 칸은 넷뿐이다
 *
 * 같은 날 관리자가 **못 읽겠다고** 했다 — 「무슨 말인지 모르겠어. 매칭이 안돼.
 * 직관적으로 중요한 지표만」. 그 전에는 칸이 여덟이었고 칸마다 숫자 밑에 작은
 * 글씨가 한 줄씩 더 붙어 있었다. **머리글 하나에 값이 둘이면 눈이 짝을 못 짓는다.**
 *
 *     마지막     언제 마지막으로 뭔가를 했나
 *     푼 카드    이 기간에 웹에서 푼 카드      ○장
 *     받은 덱    이 기간에 파일을 받아 간 편   ○편
 *     예습 링크  이 기간에 연 편 — 기본·개인
 *
 * 나머지(개인 대화 수·프롬프트·강의별 내역)는 **펴야 보인다.** 늘 보일 필요가
 * 없는 값이 표에 서 있으면 중요한 넷이 안 읽힌다.
 *
 * ## 기간을 자른다
 *
 * 누적은 「지금 쓰고 있나」에 답을 못 한다 — 한 번 찬 수는 안 줄어서, 두 달 전에
 * 열심히 한 사람과 이번 주에 하는 사람이 같은 크기로 보인다. 기간은 서버가
 * 정하고(`?window=`) **무엇을 쟀는지 문장으로 실어 보낸다** — 화면이 「이번 블럭」
 * 이라고만 적으면 보는 사람이 그게 언제부터인지 모른다.
 */
export function UsageTab() {
  const [board, setBoard] = useState<UsageBoard | null>(null);
  const [picked, setPicked] = useState("block");
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState("");
  const [detail, setDetail] = useState<UsageDetail | null>(null);
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    setBoard(null);
    api<UsageBoard>(`/api/admin/usage?window=${picked}`)
      .then(setBoard)
      .catch((cause: Error) => setError(cause.message));
  }, [picked]);

  // 펼 때마다 다시 읽는다. 사람 수만큼 미리 받아 두면 첫 화면이 느려지고,
  // 관리자가 한 번에 보는 사람은 하나다.
  const open = useCallback(
    (row: UsageRow) => {
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
    },
    [openId],
  );

  if (error) return <p className="notice is-error">{error}</p>;

  return (
    <section className="admin-usage">
      {/* 기간이 먼저 선다. 아래 숫자가 전부 이것에 매여 있어서, 표를 보고 나서
          기간을 찾게 하면 그 사이에 이미 잘못 읽는다. */}
      <nav className="admin-window" aria-label="기간">
        {(board?.windows ?? [{ key: "block", label: "이번 블럭" }]).map((choice) => (
          <button
            key={choice.key}
            className={choice.key === picked ? "is-active" : ""}
            onClick={() => setPicked(choice.key)}
          >
            {choice.label}
          </button>
        ))}
      </nav>

      {board ? (
        <Board
          board={board}
          openId={openId}
          detail={detail}
          detailError={detailError}
          onToggle={open}
        />
      ) : (
        <p className="notice">불러오는 중…</p>
      )}
    </section>
  );
}

function Board({
  board,
  openId,
  detail,
  detailError,
  onToggle,
}: {
  board: UsageBoard;
  openId: string;
  detail: UsageDetail | null;
  detailError: string;
  onToggle: (row: UsageRow) => void;
}) {
  const now = new Date(board.now);
  const active = board.users.filter((row) => row.cards > 0 || row.decks > 0).length;
  const never = board.users.filter((row) => !row.lastAt).length;

  return (
    <>
      {/* **무엇을 쟀는지 문장으로 적는다.** 「이번 블럭」만으로는 언제부터인지 모른다. */}
      <p className="admin-summary">
        {board.window.label} · {span(board.window.from, board.window.to)} · 쓴 사람{" "}
        <strong>{active}명</strong> / {board.users.length}명
        {never ? <> · 한 번도 안 연 사람 {never}명</> : null}
      </p>

      <table className="admin-table">
        <thead>
          <tr>
            <th>이메일</th>
            <th title="마지막으로 웹에서 풀거나 파일을 받아 간 때. 이 칸만 기간을 안 탄다">
              마지막
            </th>
            <th title="이 기간에 웹에서 푼 카드. 같은 카드를 여러 번 봐도 한 장이다">푼 카드</th>
            <th title="이 기간에 강의록이나 덱을 받아 간 편. 받아 간 것이지 푼 것이 아니다">
              받은 덱
            </th>
            <th title="이 기간에 예습 링크를 연 편. 기본 링크와 개인 대화를 갈라서 센다">
              예습 링크
            </th>
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
              onToggle={() => onToggle(row)}
            />
          ))}
        </tbody>
      </table>

      {/* 예습 링크 열기는 표가 선 날부터만 찬다. 이 줄이 없으면 그 전의 0이
          「안 눌렀다」로 읽힌다 — 루트 CLAUDE.md 의 함정 ③ 이 그것이다. */}
      <p className="admin-note">
        예습 링크 열기는 {stamp(board.opensSince)}부터 남습니다 — 그 전에 누른 것은 어디에도 안
        남아 있어 0으로 보입니다. 덱을 안키에서 푼 것도 서버에 안 남습니다.
      </p>
    </>
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
        <td className="num">{row.cards ? `${row.cards}장` : "—"}</td>
        <td className="num">{row.decks ? `${row.decks}편` : "—"}</td>
        <td className="num">
          {/* **기본과 개인을 나란히 둔다.** 반이 같이 읽는 대화를 쓰는 사람과 자기
              대화를 쓰는 사람이 갈리는지가 이 둘을 붙여 놓아야 보인다. */}
          {row.opens.share || row.opens.mine
            ? `기본 ${row.opens.share} · 개인 ${row.opens.mine}`
            : "—"}
        </td>
      </tr>
      {isOpen ? (
        <tr className="admin-usage-detail">
          <td colSpan={5}>
            {detailError ? <p className="notice is-error">{detailError}</p> : null}
            {!detail && !detailError ? <p className="notice">불러오는 중…</p> : null}
            {detail ? <LectureList row={row} detail={detail} now={now} /> : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}

function LectureList({ row, detail, now }: { row: UsageRow; detail: UsageDetail; now: Date }) {
  return (
    <>
      {/* 펴야 보이는 것 둘 — 저장해 둔 개인 대화 수와, 고쳐 쓴 프롬프트 문구.
          「고쳤다」만으로는 어떻게 쓰는지 알 수 없고, 그것이 이 칸을 보는 이유다.
          **여기는 기간을 안 자른다** — 펴는 것은 그 사람의 전부를 보려는 것이다. */}
      <p className="admin-summary">
        전체 기간 · 저장한 개인 대화 {row.previews}개 · 예습 프롬프트{" "}
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
          <th>기존 복습</th>
          <th title="복습 카드에서 평가한 문항 수 · 괄호는 마지막 평가가 Good·Easy인 문항 수">복습 카드</th>
          <th title="받기 버튼을 누른 자료">받기</th>
          <th title="이 편의 예습 링크를 누른 횟수">링크</th>
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
                {row.preview ? " · 개인 대화" : ""}
              </small>
            </td>
            <td className="num">{cards(row.pre)}</td>
            <td className="num">{cards(row.main)}</td>
            <td className="num">{row.bank ? cards(row.bank) : "—"}</td>
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

/** 날짜 하나. 아직 한 줄도 안 쌓였으면 그렇게 적는다 — 자리를 비워 두면 문장이
 *  「부터 남습니다」가 된다. */
function stamp(iso: string | null): string {
  if (!iso) return "(아직 없음)";
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "(아직 없음)";
  return when.toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}

/** 잰 구간을 한 마디로. 끝이 없으면 지금까지다. */
function span(from: string | null, to: string | null): string {
  if (!from) return "전체 기간";
  return to ? `${stamp(from)} ~ ${stamp(to)}` : `${stamp(from)}부터 지금까지`;
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
