import type { LectureDetail, PreviewSource } from "../types/lectures";

export function professorTags(value?: PreviewSource | null) {
  if (!value) return [];
  return [value.changed ? "교수 변경" : "", value.newProfessor ? "신규 교수" : "",
    value.status === "needs_review" ? "확인 필요" : ""].filter(Boolean);
}

export function professorDescription(value: PreviewSource) {
  return [
    `${value.baselineYear}년 ${value.baselineProfessors.join(", ") || "담당 미상"} → ${value.year}년 ${value.currentProfessors.join(", ") || "담당 미상"}`,
    `올해 담당: ${value.currentSource === "notes" ? "올해 필기 기준" : "시간표 기준·잠정"}`,
    value.selected ? `예습: ${value.selected.year}년 · ${value.selected.professors.join(", ") || "담당 미상"}` : "예습 필기 확인 필요",
    value.reason,
    `보유 자료 기준 · 검색 ${value.year - 5}~${value.year - 1}년`,
    value.coverage.missing.length ? `미보유: ${value.coverage.missing.join(", ")}년` : "",
    value.coverage.failed.length ? `읽기 실패: ${value.coverage.failed.join(", ")}년` : "",
    value.coverage.incomplete.length ? `일부 파일 확인 필요: ${value.coverage.incomplete.join(", ")}년` : "",
  ].filter(Boolean).join("\n");
}

export function ProfessorBadges({ values, compact = false }: { values: (PreviewSource | null | undefined)[]; compact?: boolean }) {
  let tags = [...new Set(values.flatMap(professorTags))];
  if (compact && tags.length > 1) tags = [tags.includes("신규 교수") ? "신규 교수" : tags[0]];
  if (!tags.length) return null;
  return <span className="professor-badges">{tags.map(tag => <span className={`professor-badge ${tag === "신규 교수" ? "is-new" : ""}`} key={tag}>{tag}</span>)}</span>;
}

/** Label the actual attachment even while a newly selected file is still pending. */
export function previewNotesLabel(detail: LectureDetail) {
  const file = detail.files.find(f => f.kind === "notes_prev");
  const selected = detail.previewSource?.selected;
  const year = selected?.filename === file?.filename ? selected?.year
    : file?.filename.match(/\[(\d{2})\d{4}_/)?.[1];
  return year ? `${String(year).length === 2 ? `20${year}` : year}년 예습 필기` : "예습 필기";
}

export function ProfessorInfo({ value }: { value?: PreviewSource | null }) {
  if (!value) return null;
  return <div className="professor-info">
    <ProfessorBadges values={[value]} />
    <p>{value.baselineYear}년 {value.baselineProfessors.join(", ") || "담당 미상"}
      {" → "}{value.year}년 {value.currentProfessors.join(", ") || "담당 미상"}
      <small>{value.currentSource === "notes" ? "올해 필기 기준" : "시간표 기준 · 잠정"}</small></p>
    <p>{value.selected ? `${value.selected.year}년 예습 필기 · ${value.selected.professors.join(", ") || "담당 미상"}` : "예습 필기 확인 필요"}
      <small>{value.reason}</small></p>
    <small>보유한 {value.year - 5}~{value.year - 1}년 동일 강의 필기 기준
      {value.coverage.missing.length ? ` · ${value.coverage.missing.join(", ")}년 미보유` : ""}
      {value.coverage.incomplete.length ? ` · ${value.coverage.incomplete.join(", ")}년 일부 파일 확인 필요` : ""}
      {value.coverage.failed.length ? ` · ${value.coverage.failed.join(", ")}년 읽기 실패` : ""}</small>
    {value.newProfessor ? <small>‘신규 교수’는 보유 자료에서 같은 교수님의 필기를 찾지 못했다는 뜻입니다.</small> : null}
    {value.conversationNeedsReview ? <p role="status">예습 자료가 바뀌었습니다. 기존 대화는 이전 자료 기준이므로 확인이 필요합니다.</p> : null}
    {value.attachmentNeedsReview ? <p role="status">선택한 예습 필기를 준비 중입니다. 첨부가 갱신되면 새 예습을 시작할 수 있습니다.</p> : null}
  </div>;
}

/**
 * 교수 이름 옆 작은 표시(2026-11-05 사용자 지시).
 *   작년과 같은 교수 → 없음
 *   작년과 다르지만 보유한 최근 5년 자료에 같은 교수 필기가 있음 → 그 해 두 자리(「23」, 흐린 회색)
 *   최근 5년 담당 기록 없음(`newProfessor`) → 「N」(빨강)
 * 확인 필요(`needs_review`)라도 작년과 다르고 같은 교수 필기가 없으면 N이다. 자세한 근거는 칸의 title·패널이 말한다.
 */
export function professorNote(values: (PreviewSource | null | undefined)[]): string | null {
  for (const value of values) {
    if (!value) continue;
    // 같은 교수 필기를 최근 5년에서 찾았고 그게 작년이 아니면 그 해.
    if (value.changed && value.selected?.match === "same" && value.selected.year !== value.year - 1) {
      return String(value.selected.year).slice(-2);
    }
    // 최근 5년에 같은 교수 필기가 없으면 N. 러너는 작년 대응을 확정하지 못하면 newProfessor를 비우고
    // needs_review로 두므로(runner/preview_sources.py), 상태와 무관하게 「작년과 다름 + 같은 교수 필기 없음」으로 판정한다
    // (2026-11-07 사용자 지적: 교수가 바뀐 강의의 N이 사라졌다).
    if (value.newProfessor || (value.changed && value.selected?.match !== "same")) return "N";
  }
  return null;
}

export function ProfTag({ values }: { values: (PreviewSource | null | undefined)[] }) {
  const note = professorNote(values);
  if (!note) return null;
  const isNew = note === "N";
  const text = isNew ? "작년과 다른 교수 · 보유한 최근 5년 자료에 담당 기록 없음" : `작년과 다른 교수 · 20${note}년에 담당`;
  return <span className={`prof-tag${isNew ? " is-new" : ""}`} title={text} aria-label={text}>{note}</span>;
}

/**
 * 학생 패널에 남기는 출처 변경 안내(web/CLAUDE.md 계약: 원본 선택과 실제 첨부가 다르면
 * 새 예습 시작을 보류하고 기존 링크는 출처 변경 안내와 함께 보존한다). 자세한 출처는 관리자 접힘의 ProfessorInfo.
 */
export function PreviewSourceNotice({ value }: { value?: PreviewSource | null }) {
  if (!value?.conversationNeedsReview && !value?.attachmentNeedsReview) return null;
  return <div className="preview-source-notice">
    {value.conversationNeedsReview ? <p role="status">예습 자료가 바뀌었습니다. 기존 대화는 이전 자료 기준이므로 확인이 필요합니다.</p> : null}
    {value.attachmentNeedsReview ? <p role="status">선택한 예습 필기를 준비 중입니다. 첨부가 갱신되면 새 예습을 시작할 수 있습니다.</p> : null}
  </div>;
}
