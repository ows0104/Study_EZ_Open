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
