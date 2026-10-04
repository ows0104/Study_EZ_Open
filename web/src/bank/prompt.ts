import template from "./bankPrompt.md?raw";
import type { BankSource, LectureDetail } from "../types";

/**
 * Quiz Bank 를 만드는 ChatGPT 프롬프트. **정본은 `bankPrompt.md` 하나다**(2026-10-04 관리자 —
 * 「이제부터 우리 프로젝트가 정본」). 머리의 `<!-- -->` 는 판 번호와 변경 기록이라 보내지 않는다.
 *
 * 프롬프트를 고치면 push 만으로 나간다 — 서버를 다시 배포할 일이 없다.
 */
const HEADER = /^\s*<!--([\s\S]*?)-->\s*/;

export const BANK_PROMPT_VERSION = /Version:\s*(\S+)/.exec(HEADER.exec(template)?.[1] ?? "")?.[1] ?? "unknown";

const KIND_LABEL: Record<BankSource["kind"], string> = {
  notes_current: "강의자료(필기 포함)",
  jokbo: "족보",
};

/** 첨부 순서(S1·S2)는 서버가 정한 `bankSources` 순서다 — 러너도 같은 ID 로 출처를 읽는다. */
export function renderBankPrompt(detail: LectureDetail, sources: BankSource[]) {
  const fill: Record<string, string> = {
    title: detail.title,
    exam_date: detail.bankExamDate || "미정",
    weighting: "강의슬라이드 > 족보 > 필기",
    sources: sources.map((s) => `  - ${s.id} | ${KIND_LABEL[s.kind]} | ${s.filename}`).join("\n"),
    output: "이 응답 본문에 바로 쓴다.",
  };
  return template
    .replace(/\r\n/g, "\n")
    .replace(HEADER, "")
    .replace(/\{\{(title|exam_date|weighting|sources|output)\}\}/g, (_, key: string) => fill[key]);
}
