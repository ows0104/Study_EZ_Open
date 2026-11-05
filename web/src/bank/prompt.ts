import template from "../../../content/prompts/bank/bankPrompt.md?raw";
import lectureScopes from "../../../content/prompts/bank/lectureScopes.json";
import fileDelivery from "../../../content/prompts/bank/fileDelivery.md?raw";
import textDelivery from "../../../content/prompts/bank/textDelivery.md?raw";
import type { BankSource } from "../types/bank";
import type { LectureDetail } from "../types/lectures";

/**
 * Quiz Bank 를 만드는 ChatGPT 프롬프트. **정본은 `bankPrompt.md` 하나다**(2026-10-04 관리자 —
 * 「이제부터 우리 프로젝트가 정본」). 머리의 `<!-- -->` 는 판 번호와 변경 기록이라 보내지 않는다.
 *
 * 프롬프트를 고치면 push 만으로 나간다 — 서버를 다시 배포할 일이 없다.
 */
const HEADER = /^\s*<!--([\s\S]*?)-->\s*/;
type LectureScope = { title: string; sourcePrefix: string; instruction: string; outputMode?: "markdown_file" };

export const BANK_PROMPT_VERSION = /Version:\s*(\S+)/.exec(HEADER.exec(template)?.[1] ?? "")?.[1] ?? "unknown";

const KIND_LABEL: Record<BankSource["kind"], string> = {
  notes_current: "강의자료(필기 포함)",
  jokbo: "족보",
};

/** 첨부 순서(S1·S2)는 서버가 정한 `bankSources` 순서다 — 러너도 같은 ID 로 출처를 읽는다. */
type PromptLecture=Pick<LectureDetail,'title'|'runId'|'subject'|'bankExamDate'>;
export function renderBankPrompt(detail: PromptLecture, sources: BankSource[], sourceTemplate = template,
  sourceScopes: readonly LectureScope[] = lectureScopes as LectureScope[],
  deliveries = { file: fileDelivery, text: textDelivery }) {
  const scope = sourceScopes.find(scope => scope.title === detail.title && sources.some(
    source => source.kind === "notes_current" && source.filename.startsWith(scope.sourcePrefix)));
  const version = /Version:\s*(\S+)/.exec(HEADER.exec(sourceTemplate)?.[1] ?? "")?.[1] ?? "unknown";
  const deliveryValues: Record<string, string> = { run_id: detail.runId || sources
    .filter(source => source.kind === "notes_current")
    .map(source => /^\[([^\]]+)\]/.exec(source.filename)?.[1]).find(Boolean) || "",
    subject: detail.subject || "약리학", prompt_version: version };
  const fill: Record<string, string> = {
    title: detail.title,
    lecture_scope: scope?.instruction ?? "",
    delivery_instructions: deliveries.file
      .replace(/\{\{(run_id|subject|prompt_version)\}\}/g, (_, key: string) => deliveryValues[key]),
    exam_date: detail.bankExamDate || "미정",
    weighting: "강의슬라이드 > 족보 > 필기",
    sources: sources.map((s) => `  - ${s.id} | ${KIND_LABEL[s.kind]} | ${s.filename}`).join("\n"),
    output: "전체 확정본을 실제 UTF-8 .md 파일 하나로 제공한다.",
  };
  return sourceTemplate
    .replace(/\r\n/g, "\n")
    .replace(HEADER, "")
    .replace(/^\{\{lecture_scope\}\}\n(?:\n)?/m, () => fill.lecture_scope ? `${fill.lecture_scope}\n\n` : "")
    .replace(/\{\{(title|exam_date|weighting|sources|output|lecture_scope|delivery_instructions)\}\}/g, (_, key: string) => fill[key]);
}

/** 전송 시점의 정본을 읽는다. 페이지를 오래 열어 둔 경우에도 번들에 든 구버전으로 전송하지 않는다. */
export async function loadLatestBankPrompt(detail: PromptLecture, sources: BankSource[]) {
  const response = await fetch(`/bank-prompt.json?t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("최신 출제 프롬프트를 불러오지 못했습니다. 다시 시도하세요.");
  const latest = await response.json();
  if (latest.lectureScopes !== undefined && (!Array.isArray(latest.lectureScopes)
      || latest.lectureScopes.some((scope: LectureScope | null) => !scope
        || typeof scope.title !== "string" || !scope.title.trim()
        || typeof scope.sourcePrefix !== "string" || !scope.sourcePrefix.trim()
        || typeof scope.instruction !== "string" || !scope.instruction.trim()
        || (scope.outputMode !== undefined && scope.outputMode !== "markdown_file")))) {
    throw new Error("최신 강의별 출제 범위가 올바르지 않습니다. 전송을 중단했습니다.");
  }
  if (typeof latest.template !== "string" || typeof latest.version !== "string"
      || /Version:\s*(\S+)/.exec(latest.template)?.[1] !== latest.version
      || !latest.template.includes("STUDYEZ_BANK_COMPLETE")) {
    throw new Error("출제 프롬프트 파일이 올바르지 않습니다. 전송을 중단했습니다.");
  }
  if (latest.deliveries !== undefined && (typeof latest.deliveries?.file !== "string" || typeof latest.deliveries?.text !== "string")) {
    throw new Error("최신 파일 전달 지침이 올바르지 않습니다. 전송을 중단했습니다.");
  }
  const scopes: LectureScope[] = latest.lectureScopes ?? lectureScopes;
  return { prompt: renderBankPrompt(detail, sources, latest.template, scopes, latest.deliveries), version: latest.version, fileOutput: true };
}
