import type { LectureDetail } from "../types/lectures";
import { PROMPT_TOKENS, renderLecturePrompt } from "./previewPrompt";
import { professorsFromNotesFilename, reviewProfessorGuidance } from "./reviewProfessor";

export const DEFAULT_REVIEW_PROMPT = [
  "{파일명}",
  "오늘 들은 강의를 복습하고 싶어. 첨부한 올해 필기와 족보를 바탕으로 큰 흐름을 설명해줘.",
].join("\n");

export const REVIEW_PROMPT_TOKENS = PROMPT_TOKENS.map((item) =>
  item.token === "{파일명}" ? { ...item, label: "붙이는 올해 강의록 파일명" } : item
);

export function renderReviewPrompt(template: string, detail: LectureDetail) {
  const filename = detail.files.find(file => file.kind === "notes_current")?.filename;
  if (!filename) return renderLecturePrompt(template, detail, "notes_current");
  const names = professorsFromNotesFilename(filename);
  const prompt = renderLecturePrompt(template, { ...detail, professors: names }, "notes_current");
  return `${prompt}\n\n${reviewProfessorGuidance(filename)}`;
}
