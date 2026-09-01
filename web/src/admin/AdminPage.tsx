import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import {
  checklistItems,
  previewProviderLabels,
  previewProviders,
  type AdminOverview,
  type AdminRow,
  type AppUser,
  type ChecklistItem,
  type JobBoard,
  type PreviewProvider,
  type RunnerBeat,
} from "../types";
import { jobMoving, jobOpen, progressLine } from "../jobProgress";
import { lectureHref } from "../links";

/** 관리자가 채우는 다섯 칸. 순서가 곧 하는 순서다 — 앞 셋이 예습, 뒤 둘이 복습. */
const checklistLabels: Record<ChecklistItem, string> = {
  notes_prev: "25필기",
  preview: "예습링크",
  pre_apkg: "Pre덱",
  notes_current: "26강의록",
  main_apkg: "Main덱",
};

/**
 * 러너가 이 시간 안에 안 보이면 안 붙은 것으로 친다.
 *
 * 러너는 15초마다 서버에 물어보므로 2분은 넉넉하다. 넉넉하게 잡는 이유는 —
 * 짧게 잡으면 노트북이 잠깐 버벅인 것을 "꺼졌다"고 말하고, 그런 경고는 곧
 * 아무도 안 본다.
 */
const RUNNER_STALE_MS = 120_000;

function runnerAlive(runner: RunnerBeat | null | undefined): boolean {
  if (!runner?.lastSeen) return false;
  return Date.now() - new Date(runner.lastSeen).getTime() < RUNNER_STALE_MS;
}

/**
 * 지금 무엇이 도는가. **표보다 먼저 선다.**
 *
 * 「지금 어떤 걸 하고 있고, 돌린 지 몇 분째이고, 어느 단계까지 왔고, 예상 시간은
 * 얼마인지」를 보려면 그 전에는 표를 훑어야 했다(2026-09-01 관리자 지시). 도는
 * 것도 기다리는 것도 없으면 아무것도 안 그린다.
 */
function RunnerBoard({ board }: { board: JobBoard | null }) {
  if (!board) return null;
  const { running, waiting, held } = board;
  if (!running.length && !waiting.length && !held.length) return null;
  return (
    <section className="runner-board">
      <h2>
        지금 도는 것 {running.length}/{board.maxRunning}
        {waiting.length ? ` · 기다리는 것 ${waiting.length}` : ""}
        {held.length ? ` · 상한에 걸린 것 ${held.length}` : ""}
        {` · 오늘 자동 ${board.autoUsedToday}/${board.autoDailyCap}편`}
      </h2>

      {running.map((job) => (
        <div key={job.id} className="runner-job">
          <span>
            <strong>
              {job.subject}/{job.runId}
            </strong>{" "}
            {job.kind === "main" ? "Main-Quiz" : "Pre-Quiz"}
            {job.origin === "auto" ? " · 자동" : ""}
            <small> {job.worker}</small>
            <br />
            <small>{progressLine(job)}</small>
            {/* 시간으로 그린다. 단계 수로 그리면 「② 카드」 하나가 편의 절반이라
                막대가 절반에서 오래 멈춰 선다. 남은 시간을 모르면 안 그린다. */}
            {job.etaSeconds > 0 ? (
              <span className="runner-bar">
                <span
                  style={{
                    width: `${Math.min(99, Math.round((job.elapsedSeconds / (job.elapsedSeconds + job.etaSeconds)) * 100))}%`,
                  }}
                />
              </span>
            ) : null}
          </span>
        </div>
      ))}

      {waiting.map((job, index) => (
        <div key={job.id} className="runner-job">
          <span>
            <strong>
              {job.subject}/{job.runId}
            </strong>{" "}
            {job.kind === "main" ? "Main-Quiz" : "Pre-Quiz"}
            <small> · 차례 {index + 1}번째{job.origin === "auto" ? " · 자동" : ""}</small>
          </span>
        </div>
      ))}

      {held.map((job) => (
        <div key={job.id} className="runner-job">
          <span>
            <strong>
              {job.subject}/{job.runId}
            </strong>{" "}
            {job.kind === "main" ? "Main-Quiz" : "Pre-Quiz"}
            <br />
            {/* 상한에 걸린 줄은 **왜 안 만드는지**를 그대로 적는다. 누르는 자리는
                캘린더의 그 덱 칸이다 — 여기서 또 누르게 하면 같은 버튼이 둘이 된다. */}
            <small>{job.stage || "오늘 자동 상한을 넘어 기다리는 중"}</small>
          </span>
        </div>
      ))}
    </section>
  );
}

/** 아직 관리자 몫으로 남은 칸. `waived`는 닫은 것이므로 남은 것이 아니다. */
function pending(row: AdminRow) {
  return checklistItems.filter((item) => row.checklist[item] === "todo");
}

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
 * 관리자 화면. 매칭 확인 · 업로드 현황 · 예습 링크 입력.
 *
 * 학기당 300편 안쪽이라 통째로 그린다. 페이지를 나누면 "어디가 비어 있는가"를
 * 한눈에 보는 목적이 흐려진다.
 */
export function AdminPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [board, setBoard] = useState<JobBoard | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "pending" | "unmatched" | "flagged" | "no-preview">("all");

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

  useEffect(load, [load]);

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

  const rows = useMemo(() => {
    const all = overview?.lectures ?? [];
    // 밀린 것만 보는 갈래. 여기가 비면 그 주는 끝난 것이다.
    if (filter === "pending") return all.filter((row) => pending(row).length > 0);
    if (filter === "unmatched") return all.filter((row) => !row.match.timetableEventId || !row.match.confirmed);
    if (filter === "flagged")
      return all.filter((row) => Object.values(row.runMeta).some((meta) => meta.reviewFlagged > 0));
    if (filter === "no-preview") return all.filter((row) => !row.preview?.shareUrl);
    return all;
  }, [overview, filter]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!overview) return <p className="notice">불러오는 중…</p>;

  const unmatched = overview.lectures.filter((row) => !row.match.timetableEventId).length;
  const unconfirmed = overview.lectures.filter((row) => row.match.timetableEventId && !row.match.confirmed).length;
  const flagged = overview.lectures.filter((row) =>
    Object.values(row.runMeta).some((meta) => meta.reviewFlagged > 0),
  ).length;
  const incomplete = overview.lectures.filter((row) => pending(row).length > 0).length;
  const queued = overview.lectures.filter((row) => jobOpen(row.prequizJob)).length;

  return (
    <div className="admin">
      <h1>관리</h1>
      <p className="admin-summary">
        강의 {overview.lectures.length}편 · 체크 남은 것 <strong>{incomplete}</strong> · 시간표에 못 붙은 것{" "}
        <strong>{unmatched}</strong> · 확인 안 한 매칭 <strong>{unconfirmed}</strong> · 검토 표시 있는 덱{" "}
        <strong>{flagged}</strong>
        {" · "}
        러너{" "}
        <strong>{runnerAlive(overview.runner) ? (overview.runner?.busy ? "만드는 중" : "대기") : "안 붙음"}</strong>
      </p>

      <RunnerBoard board={board} />

      {queued > 0 && !runnerAlive(overview.runner) ? (
        <p className="notice is-error">
          덱 일감 {queued}개가 기다리는데 <strong>러너가 안 붙어 있습니다.</strong> 만드는 것은
          노트북이 합니다 — 거기서 <code>python -m studyez agent</code>를 띄우면 이어서 집어 갑니다.
        </p>
      ) : null}

      <div className="admin-filters" role="group" aria-label="거르기">
        {(
          [
            ["all", "전체"],
            ["pending", "체크 남음"],
            ["unmatched", "매칭 확인 필요"],
            ["flagged", "검토 표시"],
            ["no-preview", "예습 링크 없음"],
          ] as const
        ).map(([key, label]) => (
          <button key={key} className={filter === key ? "is-active" : ""} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      <table className="admin-table">
        <thead>
          <tr>
            <th>강의</th>
            <th>시간표 매칭</th>
            <th>체크리스트</th>
            <th>예습 링크</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <AdminLectureRow key={`${row.subject}/${row.runId}`} row={row} onChanged={load} />
          ))}
        </tbody>
      </table>
      {!rows.length ? <p className="notice">해당하는 강의가 없습니다.</p> : null}

      <CourseAliases overview={overview} onChanged={load} />
      <Users />
    </div>
  );
}

/**
 * 계정 승인.
 *
 * 가입은 누구나 하지만 승인 전에는 아무것도 안 보인다. Supabase에 메일 주소를
 * 넣은 사람과 이 학년 학생이 같지 않기 때문이고, 그 판단은 사람이 한다.
 */
function Users() {
  const [users, setUsers] = useState<AppUser[] | null>(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    api<AppUser[]>("/api/admin/users").then(setUsers);
  }, []);

  useEffect(load, [load]);

  if (!users) return null;
  const waiting = users.filter((row) => !row.isApproved).length;

  async function setApproval(row: AppUser, isApproved: boolean) {
    setBusy(row.id);
    try {
      await api(`/api/admin/users/${row.id}/approval`, {
        method: "PUT",
        body: JSON.stringify({ isApproved }),
      });
      load();
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="admin-users">
      <h2>계정 {waiting ? `— 승인 대기 ${waiting}명` : ""}</h2>
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

function AdminLectureRow({ row, onChanged }: { row: AdminRow; onChanged: () => void }) {
  const base = `/api/admin/lectures/${encodeURIComponent(row.subject)}/${encodeURIComponent(row.runId)}`;
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [share, setShare] = useState(row.preview?.shareUrl ?? "");
  const [conversation, setConversation] = useState(row.preview?.conversationUrl ?? "");
  const [previewProvider, setPreviewProvider] = useState<PreviewProvider>(row.preview?.provider ?? "chatgpt");
  const [saving, setSaving] = useState(false);
  const [waiving, setWaiving] = useState<ChecklistItem | null>(null);

  const flagged = Object.entries(row.runMeta).filter(([, meta]) => meta.reviewFlagged > 0);

  async function setWaived(item: ChecklistItem, waived: boolean) {
    setWaiving(item);
    try {
      await api(`${base}/waive`, { method: "PUT", body: JSON.stringify({ item, waived }) });
      onChanged();
    } finally {
      setWaiving(null);
    }
  }

  async function setMatch(timetableEventId: string | null) {
    await api(`${base}/match`, {
      method: "PUT",
      body: JSON.stringify({ timetableEventId, confirmed: true }),
    });
    onChanged();
  }

  async function savePreview() {
    setSaving(true);
    try {
      await api(`${base}/preview`, {
        method: "PUT",
        body: JSON.stringify({ provider: previewProvider, shareUrl: share, conversationUrl: conversation }),
      });
      onChanged();
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr className={row.match.timetableEventId ? "" : "is-unmatched"}>
      <td>
        <a href={lectureHref(row)} target="_blank" rel="noreferrer">
          {row.title}
        </a>
        <small>
          {row.subject} · {row.runId} · {row.date}
          {row.author ? ` · ${row.author}${row.version ? `v${row.version}` : ""}` : ""}
        </small>
      </td>

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

      <td>
        {/* 다섯 칸을 하는 순서대로 세운다. 안 한 것이 눈에 띄어야 하므로 색은
            남은 칸이 가져간다 — 끝낸 칸을 칠하면 다 한 강의가 제일 시끄러워지고
            정작 밀린 강의가 묻힌다.

            누르면 "해당 없음"으로 닫거나 되돌린다. 신설 강의에는 작년 필기가
            없고, 그런 칸을 영영 미완으로 두면 화면 전체가 미완이 된다. */}
        <ul className="checklist">
          {checklistItems.map((item) => {
            const state = row.checklist[item];
            return (
              <li key={item} className={`is-${state}`}>
                <button
                  type="button"
                  disabled={state === "done" || waiving !== null}
                  title={
                    state === "done"
                      ? "올라와 있음"
                      : state === "waived"
                        ? "해당 없음으로 닫음 — 눌러서 되돌리기"
                        : "눌러서 해당 없음으로 닫기"
                  }
                  onClick={() => setWaived(item, state !== "waived")}
                >
                  {checklistLabels[item]}
                </button>
              </li>
            );
          })}
        </ul>
        <ul className="uploads">
          <li className={row.has.media ? "is-on" : ""}>슬라이드</li>
          <li className={row.preItemCount ? "is-on" : ""}>문항 {row.preItemCount}</li>
        </ul>
        {/* 검토 표시가 남은 덱은 사람이 카드 뒷면 경고 박스를 보기 전까지
            배포해서는 안 된다. 목록에서 바로 보이게 둔다. */}
        {flagged.map(([kind, meta]) => (
          <span className="tag is-warn" key={kind}>
            {kind} 검토 {meta.reviewFlagged}
            {meta.slidesUnused ? ` · 미사용 슬라이드 ${meta.slidesUnused}` : ""}
          </span>
        ))}
      </td>

      <td>
        <select value={previewProvider} onChange={(event) => setPreviewProvider(event.target.value as PreviewProvider)}>
          {previewProviders.map((item) => <option value={item} key={item}>{previewProviderLabels[item]}</option>)}
        </select>
        <input
          value={share}
          placeholder="공개 공유 링크"
          onChange={(event) => setShare(event.target.value)}
        />
        <input
          value={conversation}
          placeholder="개인 대화 링크 (관리자만)"
          onChange={(event) => setConversation(event.target.value)}
        />
        <button disabled={saving} onClick={savePreview}>
          {saving ? "저장 중…" : "저장"}
        </button>
      </td>
    </tr>
  );
}

/**
 * 시간표의 과목 이름과 필기 폴더 이름을 잇는다.
 *
 * 시간표는 "질병의 병리학적 이해"라 쓰고 폴더는 "병리학"이다. 어느 쪽도
 * 상대를 유추할 수 없어서 사람이 한 번 이어 준다.
 */
function CourseAliases({ overview, onChanged }: { overview: AdminOverview; onChanged: () => void }) {
  const [draft, setDraft] = useState<Record<string, string>>(() =>
    Object.fromEntries(overview.courseAliases.map((alias) => [alias.courseKey, alias.subject])),
  );
  const [saving, setSaving] = useState(false);

  return (
    <section className="admin-aliases">
      <h2>과목 이름 잇기</h2>
      <p className="admin-summary">
        이어 두면 한 교시에 여러 과목이 열릴 때 매칭이 확실해집니다. 비우고 저장하면 연결이 지워집니다.
      </p>
      <table className="admin-table">
        <thead>
          <tr>
            <th>시간표</th>
            <th>필기 폴더</th>
          </tr>
        </thead>
        <tbody>
          {overview.timetableCourses.map((course) => (
            <tr key={course.courseKey}>
              <td>
                {course.course}
                <small>{course.sessions}회</small>
              </td>
              <td>
                <input
                  list="studyez-subjects"
                  value={draft[course.courseKey] ?? ""}
                  placeholder="예: 병리학"
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, [course.courseKey]: event.target.value }))
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <datalist id="studyez-subjects">
        {overview.subjects.map((subject) => (
          <option key={subject} value={subject} />
        ))}
      </datalist>
      <button
        disabled={saving}
        onClick={async () => {
          setSaving(true);
          try {
            const labels = new Map(overview.timetableCourses.map((course) => [course.courseKey, course.course]));
            await api("/api/admin/course-aliases", {
              method: "PUT",
              body: JSON.stringify(
                Object.entries(draft).map(([courseKey, subject]) => ({
                  courseKey,
                  course: labels.get(courseKey) ?? "",
                  subject: subject.trim(),
                })),
              ),
            });
            onChanged();
          } finally {
            setSaving(false);
          }
        }}
      >
        {saving ? "저장 중…" : "저장"}
      </button>
    </section>
  );
}
