import template from "./bankPrompt.md?raw";
import lectureScopes from "./lectureScopes.json";
import type { BankSource } from "../types/bank";
import type { LectureDetail } from "../types/lectures";

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
export function renderBankPrompt(detail: LectureDetail, sources: BankSource[], sourceTemplate = template) {
  const fill: Record<string, string> = {
    title: detail.title,
    lecture_scope: lectureScopes.find((scope) => scope.title === detail.title && sources.some(
      (source) => source.kind === "notes_current" && source.filename.startsWith(scope.sourcePrefix),
    ))?.instruction ?? "별도 지정 없음. 자료의 교수 강조·출제 범위를 먼저 판단한다.",
    exam_date: detail.bankExamDate || "미정",
    weighting: "강의슬라이드 > 족보 > 필기",
    sources: sources.map((s) => `  - ${s.id} | ${KIND_LABEL[s.kind]} | ${s.filename}`).join("\n"),
    output: "이 응답 본문에 바로 쓴다.",
  };
  return sourceTemplate
    .replace(/\r\n/g, "\n")
    .replace(HEADER, "")
    .replace(/\{\{(title|exam_date|weighting|sources|output|lecture_scope)\}\}/g, (_, key: string) => fill[key]);
}

/** 전송 시점의 정본을 읽는다. 페이지를 오래 열어 둔 경우에도 번들에 든 구버전으로 전송하지 않는다. */
export async function loadLatestBankPrompt(detail: LectureDetail, sources: BankSource[]) {
  const response = await fetch(`/bank-prompt.json?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("최신 출제 프롬프트를 불러오지 못했습니다. 다시 시도하세요.");
  const latest = await response.json();
  if (typeof latest.template !== "string" || typeof latest.version !== "string"
      || /Version:\s*(\S+)/.exec(latest.template)?.[1] !== latest.version
      || !latest.template.includes("STUDYEZ_BANK_COMPLETE")) {
    throw new Error("출제 프롬프트 파일이 올바르지 않습니다. 전송을 중단했습니다.");
  }
  return { prompt: renderBankPrompt(detail, sources, latest.template), version: latest.version };
}
