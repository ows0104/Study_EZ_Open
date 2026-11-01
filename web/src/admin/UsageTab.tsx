import { useEffect, useState } from "react";
import { api } from "../api";
import type { UsageActivityCatalog, UsageActivityMetric, UsageBoard, UsageDetail, UsageRow, UsageFileRequest } from "../types/account";

const FILES: Record<string, string> = {
  notes_prev: "작년 필기", notes_current: "올해 필기", pre_apkg: "예습덱", main_apkg: "복습덱", jokbo: "족보",
};
const NO_RECORD = <span className="usage-empty">기록 없음</span>;

/** 저장·클릭·평가·파일 요청을 별도로 표시한다. 이 수들을 학습량으로 합산하지 않는다. */
export function UsageTab() {
  const [board, setBoard] = useState<UsageBoard | null>(null);
  const [picked, setPicked] = useState("block");
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState("");
  const [detail, setDetail] = useState<UsageDetail | null>(null);
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setBoard(null);
    setError("");
    api<UsageBoard>(`/api/admin/usage?window=${picked}`)
      .then((data) => { if (!cancelled) setBoard(data); })
      .catch((cause: Error) => { if (!cancelled) setError(cause.message); });
    return () => { cancelled = true; };
  }, [picked]);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setDetailError("");
    if (openId) {
      api<UsageDetail>(`/api/admin/usage/${openId}`)
        .then((data) => { if (!cancelled) setDetail(data); })
        .catch((cause: Error) => { if (!cancelled) setDetailError(cause.message); });
    }
    return () => { cancelled = true; };
  }, [openId]);

  const active = board?.users.filter(hasActivity).length ?? 0;
  return (
    <section className="admin-usage">
      <nav className="admin-window" aria-label="기간">
        {(board?.windows ?? [{ key: "block", label: "이번 블럭" }]).map((choice) => (
          <button key={choice.key} className={choice.key === picked ? "is-active" : ""}
            onClick={() => setPicked(choice.key)}>{choice.label}</button>
        ))}
      </nav>
      {error ? <p className="notice is-error">{error}</p> : null}
      {!board && !error ? <p className="notice">불러오는 중…</p> : null}
      {board ? <>
        <p className="admin-summary">
          {board.window.label} · {dateSpan(board.window.from, board.window.to)} · 활동 기록 있는 사람 <strong>{active}명</strong> / {board.users.length}명
        </p>
        <p className="admin-note usage-legend">
          개인 링크 만들기·저장, 링크 열기·파일 요청은 해당 기간에 마지막 기록이 있는 <b>강의 수</b>, 퀴즈는 웹에서 평가한 <b>문항 수</b>입니다.
          파일 요청은 목적별로 따로 세며 같은 강의가 여러 목적에 포함될 수 있습니다. 이메일을 누르면 전체 기간의 횟수와 시각이 보입니다.
        </p>
        <div className="usage-scroll">
          <table className="admin-table usage-board">
            <thead><tr>
              <th>이메일</th><th>마지막 활동</th>
              {board.activityGroups.map((group) => <th key={group.key}>{group.label}</th>)}
            </tr></thead>
            <tbody>{board.users.map((row) => <UserRows key={row.id} row={row} now={new Date(board.now)} catalog={board}
              isOpen={openId === row.id} detail={openId === row.id && detail?.user.id === row.id ? detail : null}
              detailError={openId === row.id ? detailError : ""}
              onToggle={() => setOpenId((current) => current === row.id ? "" : row.id)} />)}</tbody>
          </table>
        </div>
        <p className="admin-note usage-legend">
          개인 링크 만들기는 시작 시도, 저장은 현재 남아 있는 주소입니다. 외부 AI의 생성 완료·열람 완료를 뜻하지 않습니다. 링크 열기는 사이트에서 누른 기록만 남으며,
          외부 AI에서 읽거나 안키에서 푼 내용은 알 수 없습니다. 예습 링크 기록의 최초 시각: {dateOnly(board.opensSince)}.
          파일 요청은 전송·첨부 완료를 뜻하지 않으며, 과거 기록과 목적을 보내지 않은 요청은 ‘목적 미상’입니다.
        </p>
      </> : null}
    </section>
  );
}

function hasActivity(row: UsageRow): boolean {
  return Object.values(row.activities).some((metric) => metric.count > 0 || (metric.grades ?? 0) > 0);
}

function UserRows({ row, now, isOpen, detail, detailError, onToggle, catalog }: {
  row: UsageRow; now: Date; catalog: UsageActivityCatalog; isOpen: boolean; detail: UsageDetail | null; detailError: string; onToggle: () => void;
}) {
  return <>
    <tr className={row.lastAt ? "" : "is-idle"}>
      <td><button className="admin-usage-name" onClick={onToggle} aria-expanded={isOpen}>
        {isOpen ? "▾" : "▸"} {row.email || row.id}
      </button>{row.isAdmin ? <span className="tag is-ok">관리자</span> : null}
        {!row.hasAccess ? <span className="tag">승인 대기</span> : null}</td>
      <td>{row.lastAt ? <>{since(row.lastAt, now)}<When at={row.lastAt} /></> : NO_RECORD}</td>
      <ActionCells catalog={catalog} activities={row.activities} />
    </tr>
    {isOpen ? <tr className="admin-usage-detail"><td colSpan={2 + catalog.activityGroups.length}>
      {detailError ? <p className="notice is-error">{detailError}</p> : null}
      {!detail && !detailError ? <p className="notice">불러오는 중…</p> : null}
      {detail ? <>
        <p className="admin-summary">전체 기간 · 시각은 한국 시간 · 현재 저장된 개인 예습 대화 {row.previews}개 · 예습 프롬프트 {detail.user.previewPrompt ? <q>{detail.user.previewPrompt}</q> : "기본 문구"}</p>
        {detail.lectures.length ? <LectureTable detail={detail} /> : <p className="notice">아직 강의별 활동 기록이 없습니다.</p>}
      </> : null}
    </td></tr> : null}
  </>;
}

/** Column labels, action names, units and future actions all come from the API. */
function ActionCells({ catalog, activities, files, detail = false }: {
  catalog: UsageActivityCatalog; activities: Record<string, UsageActivityMetric>;
  files?: UsageFileRequest[]; detail?: boolean;
}) {
  return <>{catalog.activityGroups.map((group) => {
    const definitions = catalog.activityCatalog.filter((action) => action.group === group.key
      && ((activities[action.key]?.count ?? 0) > 0 || (activities[action.key]?.grades ?? 0) > 0));
    return <td key={group.key}>{definitions.length ? definitions.map((action) => {
      const metric = activities[action.key];
      const requests = detail && action.filePurpose ? files?.filter((file) => file.purpose === action.filePurpose) : undefined;
      return requests ? requests.map((request) => <div className={`usage-action usage-${request.purpose}`} key={`${action.key}/${request.kind}`}>
        <b>{action.label}</b><div>{fileLabel(request.kind)} · {request.count}회</div>
        <When at={request.lastAt} firstAt={request.firstAt} />
      </div>) : <div className="usage-action" key={action.key}>
        {action.label} <b>{metric.count}{detail ? action.detailUnit : action.summaryUnit}</b>
        {detail && metric.grades ? <small>평가 {metric.grades}회</small> : null}
        {detail ? <When at={metric.lastAt} /> : null}
      </div>;
    }) : NO_RECORD}</td>;
  })}</>;
}

function LectureTable({ detail }: { detail: UsageDetail }) {
  return <table className="admin-table usage-lectures">
    <thead><tr><th>강의</th>{detail.activityGroups.map((group) => <th key={group.key}>{group.label}</th>)}</tr></thead>
    <tbody>{detail.lectures.map((row) => <tr key={`${row.subject}/${row.runId}`}>
      <td>{row.title || row.runId}<small>{row.subject} · {row.date ?? row.runId}</small></td>
      <ActionCells catalog={detail} activities={row.activities} files={row.fileRequests} detail />
    </tr>)}</tbody>
  </table>;
}

function fileLabel(kind: string): string {
  return FILES[kind] ?? (kind.startsWith("bank_") ? "복습 카드 Anki덱" : kind);
}

function When({ at, firstAt }: { at: string | null; firstAt?: string }) {
  if (!at) return null;
  return <small className="usage-time"><time dateTime={at} title={`${firstAt ? `첫 요청 ${fullStamp(firstAt)} / 마지막 ` : ""}${fullStamp(at)} (한국 시간)`}>
    {new Date(at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit", hour12: false })}
  </time></small>;
}

function fullStamp(at: string): string {
  return new Date(at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul", hour12: false });
}

function dateOnly(at: string | null): string {
  return at ? new Date(at).toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" }) : "아직 없음";
}

function dateSpan(from: string | null, to: string | null): string {
  if (!from) return "전체 기간";
  return `${dateOnly(from)}부터 ${to ? `${dateOnly(to)} 직전까지` : "지금까지"}`;
}

function since(at: string, now: Date): string {
  const hours = (now.getTime() - new Date(at).getTime()) / 3_600_000;
  if (hours < 1) return "방금";
  if (hours < 24) return `${Math.floor(hours)}시간 전`;
  if (hours < 24 * 14) return `${Math.floor(hours / 24)}일 전`;
  return dateOnly(at);
}
