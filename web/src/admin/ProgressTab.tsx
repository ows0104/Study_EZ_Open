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
import { LectureCell } from "./LectureCell";
import { flaggedRuns, pending } from "./rows";

/** 관리자가 채우는 다섯 칸. 순서가 곧 하는 순서다 — 앞 셋이 예습, 뒤 둘이 복습. */
const checklistLabels: Record<ChecklistItem, string> = {
  notes_prev: "25필기",
  preview: "예습링크",
  pre_apkg: "Pre덱",
  notes_current: "26강의록",
  main_apkg: "Main덱",
};

type Filter = "all" | "pending" | "flagged" | "no-preview";

/**
 * **자료가 다 올라왔는가**만 보는 탭.
 *
 * 시간표 매칭은 여기 없다(→ 「매칭」 탭). 한 편에 대해 묻는 것이 둘이었는데
 * ―「올라왔나」와 「어느 시간의 강의인가」― 둘을 한 줄에 붙여 놓으면 네 칸짜리
 * 표가 되고, 밀린 자료를 훑는 눈이 매칭 칸을 매번 건너뛰어야 했다.
 */
export function ProgressTab({ overview, onChanged }: { overview: AdminOverview; onChanged: () => void }) {
  const [filter, setFilter] = useState<Filter>("all");

  const rows = useMemo(() => {
    const all = overview.lectures;
    // 밀린 것만 보는 갈래. 여기가 비면 그 주는 끝난 것이다.
    if (filter === "pending") return all.filter((row) => pending(row).length > 0);
    if (filter === "flagged") return all.filter((row) => flaggedRuns(row).length > 0);
    if (filter === "no-preview") return all.filter((row) => !row.preview?.shareUrl);
    return all;
  }, [overview, filter]);

  return (
    <>
      <div className="admin-filters" role="group" aria-label="거르기">
        {(
          [
            ["all", "전체"],
            ["pending", "체크 남음"],
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
            <th>체크리스트</th>
            <th>예습 링크</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <ProgressRow key={`${row.subject}/${row.runId}`} row={row} onChanged={onChanged} />
          ))}
        </tbody>
      </table>
      {!rows.length ? <p className="notice">해당하는 강의가 없습니다.</p> : null}
    </>
  );
}

function ProgressRow({ row, onChanged }: { row: AdminRow; onChanged: () => void }) {
  const base = `/api/admin/lectures/${encodeURIComponent(row.subject)}/${encodeURIComponent(row.runId)}`;
  const [share, setShare] = useState(row.preview?.shareUrl ?? "");
  const [conversation, setConversation] = useState(row.preview?.conversationUrl ?? "");
  const [previewProvider, setPreviewProvider] = useState<PreviewProvider>(row.preview?.provider ?? "chatgpt");
  const [saving, setSaving] = useState(false);
  const [waiving, setWaiving] = useState<ChecklistItem | null>(null);

  const flagged = flaggedRuns(row);

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
    <tr>
      <LectureCell row={row} />

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
