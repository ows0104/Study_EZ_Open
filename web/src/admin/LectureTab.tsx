import { useMemo, useState } from "react";
import { api } from "../api";
import {
  checklistItems,
  previewProviderLabels,
  previewProviders,
  type AdminOverview,
  type AdminRow,
  type ChecklistItem,
  type PreviewProvider,
} from "../types";
import { CourseAliases } from "./CourseAliases";
import { isUnconfirmed, isUnmatched, pending } from "./rows";
import { lectureHref } from "../links";

/** 관리자가 채우는 다섯 칸. 순서가 곧 하는 순서다 — 앞 셋이 예습, 뒤 둘이 복습. */
const checklistLabels: Record<ChecklistItem, string> = {
  notes_prev: "25필기",
  preview: "예습링크",
  pre_apkg: "Pre덱",
  notes_current: "26강의록",
  main_apkg: "Main덱",
};

type Candidate = {
  id: string;
  startTime: string;
  slot: number | null;
  title: string;
  details: string;
  professor: string;
  category: string;
};

type Filter = "all" | "checklist" | "match" | "no-preview";

/** 이 편에 사람이 할 일이 남았나. 과목 블록의 머리와 거르기가 같은 셈을 쓴다. */
function todo(row: AdminRow) {
  return pending(row).length > 0 || isUnmatched(row) || isUnconfirmed(row);
}

/**
 * **강의 관리.** 어느 시간의 강의인가 · 자료가 다 올라왔는가 · 과목 이름 잇기.
 *
 * **과목으로 묶고 최신 과목이 위다**(2026-09-04 관리자 지시 — "이전 블록이 다
 * 보여서 불편하다"). 한 학기 300편이 한 줄로 서 있으면 오늘 손볼 과목을 찾는 데
 * 스크롤을 쓴다. 블록은 접힌 채로 서고 **맨 위 하나만 펴 둔다** — 접힌 머리에도
 * 편 수와 남은 일 수가 적혀 있어서, 접혀 있다고 아무것도 안 보이지는 않는다.
 *
 * 「최신 과목」은 그 과목의 **가장 최근 강의 날짜**로 센다. 과목 이름의 가나다나
 * 시간표 순서로 세면 이번 주에 도는 과목이 아래로 내려간다.
 */
export function LectureTab({ overview, onChanged }: { overview: AdminOverview; onChanged: () => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [closed, setClosed] = useState<Set<string>>(new Set());

  const groups = useMemo(() => {
    const rows = overview.lectures.filter((row) => {
      if (filter === "checklist") return pending(row).length > 0;
      if (filter === "match") return isUnmatched(row) || isUnconfirmed(row);
      if (filter === "no-preview") return !row.preview?.shareUrl;
      return true;
    });
    const bySubject = new Map<string, AdminRow[]>();
    for (const row of rows) {
      const list = bySubject.get(row.subject);
      if (list) list.push(row);
      else bySubject.set(row.subject, [row]);
    }
    return [...bySubject.entries()]
      .map(([subject, list]) => ({
        subject,
        // 블록 안에서도 최신이 위다.
        rows: [...list].sort((a, b) => b.date.localeCompare(a.date)),
        latest: list.reduce((best, row) => (row.date > best ? row.date : best), ""),
        todo: list.filter(todo).length,
      }))
      .sort((a, b) => b.latest.localeCompare(a.latest));
  }, [overview, filter]);

  return (
    <>
      <div className="admin-filters" role="group" aria-label="거르기">
        {(
          [
            ["all", "전체"],
            ["checklist", "체크 남음"],
            ["match", "매칭 확인 필요"],
            ["no-preview", "예습 링크 없음"],
          ] as const
        ).map(([key, label]) => (
          <button key={key} className={filter === key ? "is-active" : ""} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      {groups.map((group, index) => (
        <SubjectBlock
          key={group.subject}
          subject={group.subject}
          rows={group.rows}
          todoCount={group.todo}
          // 거르고 나면 남은 것이 곧 볼 것이라 다 편다. 접어 두면 거른 사람이
          // 머리글만 보게 된다. 안 거를 때는 맨 위 과목 하나만.
          open={filter !== "all" || (!closed.has(group.subject) && index === 0)}
          onToggle={(next) =>
            setClosed((current) => {
              const copy = new Set(current);
              if (next) copy.delete(group.subject);
              else copy.add(group.subject);
              return copy;
            })
          }
          onChanged={onChanged}
        />
      ))}
      {!groups.length ? <p className="notice">해당하는 강의가 없습니다.</p> : null}

      <CourseAliases overview={overview} onChanged={onChanged} />
    </>
  );
}

function SubjectBlock({
  subject,
  rows,
  todoCount,
  open,
  onToggle,
  onChanged,
}: {
  subject: string;
  rows: AdminRow[];
  todoCount: number;
  open: boolean;
  onToggle: (open: boolean) => void;
  onChanged: () => void;
}) {
  return (
    <details className="admin-group" open={open} onToggle={(event) => onToggle(event.currentTarget.open)}>
      <summary>
        <span className="admin-group-name">{subject}</span>
        <small>
          {rows.length}편 · {rows[0]?.date ?? ""}
        </small>
        {/* 접힌 블록도 「여기 볼 것이 있다」는 말은 한다. 0이면 안 그린다. */}
        {todoCount ? <span className="admin-tab-count">{todoCount}</span> : null}
      </summary>
      <div className="admin-group-body">
        {rows.map((row) => (
          <LectureRow key={`${row.subject}/${row.runId}`} row={row} onChanged={onChanged} />
        ))}
      </div>
    </details>
  );
}

/**
 * 한 편. **표가 아니라 칸이다.**
 *
 * 네 칸짜리 표에 입력 상자가 줄마다 셋씩 서 있어서 화면이 서식지처럼 보였다
 * (2026-09-04 관리자 — "UI가 비직관적이고 안 예쁘다"). 평소에 보이는 것은
 * **사실뿐**이고, 고치는 자리는 누를 때 열린다.
 */
function LectureRow({ row, onChanged }: { row: AdminRow; onChanged: () => void }) {
  const base = `/api/admin/lectures/${encodeURIComponent(row.subject)}/${encodeURIComponent(row.runId)}`;
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [editing, setEditing] = useState(false);
  const [share, setShare] = useState(row.preview?.shareUrl ?? "");
  const [conversation, setConversation] = useState(row.preview?.conversationUrl ?? "");
  const [previewProvider, setPreviewProvider] = useState<PreviewProvider>(row.preview?.provider ?? "chatgpt");
  const [saving, setSaving] = useState(false);
  const [waiving, setWaiving] = useState<ChecklistItem | null>(null);

  async function setMatch(timetableEventId: string | null) {
    await api(`${base}/match`, {
      method: "PUT",
      body: JSON.stringify({ timetableEventId, confirmed: true }),
    });
    setCandidates(null);
    onChanged();
  }

  async function setWaived(item: ChecklistItem, waived: boolean) {
    setWaiving(item);
    try {
      await api(`${base}/waive`, { method: "PUT", body: JSON.stringify({ item, waived }) });
      onChanged();
    } finally {
      setWaiving(null);
    }
  }

  async function savePreview() {
    setSaving(true);
    try {
      await api(`${base}/preview`, {
        method: "PUT",
        body: JSON.stringify({ provider: previewProvider, shareUrl: share, conversationUrl: conversation }),
      });
      setEditing(false);
      onChanged();
    } finally {
      setSaving(false);
    }
  }

  const matched = Boolean(row.match.timetableEventId);
  const event = (row.match.eventDetails || row.match.eventTitle || "").split("\n")[0];

  return (
    <article className={`lecture-card${matched ? "" : " is-unmatched"}`}>
      <div className="lecture-card-head">
        <a href={lectureHref(row)} target="_blank" rel="noreferrer">
          {row.title}
        </a>
        <small>
          {row.date} · {row.runId}
          {row.author ? ` · ${row.author}${row.version ? `v${row.version}` : ""}` : ""}
        </small>
      </div>

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

      <div className="lecture-card-facts">
        {/* 시간표 매칭. 붙은 편은 **어디에 붙었는지**가 먼저고, 버튼은 그 뒤다. */}
        <span className="lecture-fact">
          {matched ? (
            <span className={row.match.confirmed ? "tag is-ok" : "tag"}>
              {row.match.confirmed ? "확인함" : "자동 매칭"}
            </span>
          ) : (
            <span className="tag is-warn">시간표에 못 붙음</span>
          )}
          {matched && event ? <small>{event}</small> : null}
        </span>

        {/* 예습 링크. 있으면 **여는 자리**, 없으면 넣는 자리. */}
        <span className="lecture-fact">
          {row.preview?.shareUrl ? (
            <a className="tag is-ok" href={row.preview.shareUrl} target="_blank" rel="noreferrer">
              {previewProviderLabels[row.preview.provider]} 링크 ↗
            </a>
          ) : (
            <span className="tag">예습 링크 없음</span>
          )}
        </span>

        <span className="lecture-card-actions">
          {matched && !row.match.confirmed ? (
            <button onClick={() => setMatch(row.match.timetableEventId)}>맞음</button>
          ) : null}
          <button
            className="is-quiet"
            onClick={async () => {
              if (candidates) return setCandidates(null);
              setCandidates(await api<Candidate[]>(`/api/admin/timetable-events?date=${row.date}`));
            }}
          >
            {candidates ? "시간표 닫기" : matched ? "시간표 바꾸기" : "시간표 고르기"}
          </button>
          <button className="is-quiet" onClick={() => setEditing(!editing)}>
            {editing ? "링크 닫기" : row.preview?.shareUrl ? "링크 고치기" : "링크 넣기"}
          </button>
        </span>
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

      {editing ? (
        <div className="lecture-preview">
          <select value={previewProvider} onChange={(event) => setPreviewProvider(event.target.value as PreviewProvider)}>
            {previewProviders.map((item) => (
              <option value={item} key={item}>
                {previewProviderLabels[item]}
              </option>
            ))}
          </select>
          <input value={share} placeholder="공개 공유 링크" onChange={(event) => setShare(event.target.value)} />
          <input
            value={conversation}
            placeholder="개인 대화 링크 (관리자만)"
            onChange={(event) => setConversation(event.target.value)}
          />
          <button disabled={saving} onClick={savePreview}>
            {saving ? "저장 중…" : "저장"}
          </button>
        </div>
      ) : null}
    </article>
  );
}
