import type { LectureDetail } from "../types/lectures";
import { PROMPT_TOKENS, renderLecturePrompt } from "./previewPrompt";

export const DEFAULT_REVIEW_PROMPT = [
  "{파일명}",
  "오늘 들은 강의를 복습하고 싶어. 첨부한 올해 강의록을 바탕으로 핵심 개념과 흐름을 정리하고, 헷갈리기 쉬운 개념의 차이를 설명해줘. 중요한 내용은 강의록의 해당 페이지와 연결해줘. 족보가 있으면 출제되는 개념을 확인하는 데 참고해줘. 마지막에는 내가 이해했는지 확인할 짧은 질문을 하나씩 물어봐줘.",
].join("\n");

export const REVIEW_PROMPT_TOKENS = PROMPT_TOKENS.map((item) =>
  item.token === "{파일명}" ? { ...item, label: "붙이는 올해 강의록 파일명" } : item
);

export function renderReviewPrompt(template: string, detail: LectureDetail) {
  return renderLecturePrompt(template, detail, "notes_current");
}
