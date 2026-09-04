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
import { LectureCell } from "./LectureCell";
import { isUnconfirmed, isUnmatched, pending } from "./rows";

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

/**
 * **강의 관리.** 어느 시간의 강의인가 · 자료가 다 올라왔는가 · 과목 이름 잇기.
 *
 * 관리자 지시(2026-09-04) — "매칭 및 과목, 강의 관리". 셋은 한 편을 세팅하는
 * 같은 일의 앞뒤다: 시간표에 붙이고, 자료를 채우고, 과목 이름이 안 맞으면 잇는다.
 *
 * **덱이 몇 장인지·검토 표시가 있는지는 여기 없다**(→ 「퀴즈」 탭). 여기 남는
 * 것은 체크리스트의 `Pre덱`·`Main덱` 칸뿐이고, 그건 만들어졌나 아닌가 하나만
 * 말한다.
 */
export function LectureTab({ overview, onChanged }: { overview: AdminOverview; onChanged: () => void }) {
  const [filter, setFilter] = useState<Filter>("all");

  const rows = useMemo(() => {
    const all = overview.lectures;
    // 밀린 것만 보는 갈래. 여기가 비면 그 주는 끝난 것이다.
    if (filter === "checklist") return all.filter((row) => pending(row).length > 0);
    if (filter === "match") return all.filter((row) => isUnmatched(row) || isUnconfirmed(row));
    if (filter === "no-preview") return all.filter((row) => !row.preview?.shareUrl);
    return all;
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
            <LectureRow key={`${row.subject}/${row.runId}`} row={row} onChanged={onChanged} />
          ))}
        </tbody>
      </table>
      {!rows.length ? <p className="notice">해당하는 강의가 없습니다.</p> : null}

      <CourseAliases overview={overview} onChanged={onChanged} />
    </>
  );
}

function LectureRow({ row, onChanged }: { row: AdminRow; onChanged: () => void }) {
  const base = `/api/admin/lectures/${encodeURIComponent(row.subject)}/${encodeURIComponent(row.runId)}`;
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
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
      onChanged();
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr className={row.match.timetableEventId ? "" : "is-unmatched"}>
      <LectureCell row={row} />

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
      </td>

      <td>
        {/* 입력 칸은 셋뿐인데 열은 화면 끝까지 간다. 링크 한 줄이 그 폭을 다
            쓸 이유가 없어 여기서 끊는다. */}
        <div className="admin-preview">
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
        </div>
      </td>
    </tr>
  );
}
