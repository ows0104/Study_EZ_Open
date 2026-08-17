import type { LectureDetail } from "../types";

/**
 * 예습 대화를 시작하는 프롬프트.
 *
 * **사람마다 고쳐 쓴다.** 저장된 것이 있으면 그것을, 없으면 아래 기본값을 쓴다.
 * 기본값 문구는 지어낸 것이 아니라
 * `.claude/skills/prequiz/references/preview-rules.md` §0.1이 "좋은 예습 대화"라고
 * 적어 둔 것을 그대로 요구하는 것이다. 그 대화가 나중에 Pre-Quiz의 본체가 되므로,
 * 여기서 무엇을 요구하느냐가 곧 퀴즈의 재료를 정한다.
 *
 *   · 뼈대만 (지엽적인 수치·예외는 뺀다 → §1)
 *   · 헷갈리는 것은 비교 표로 (§0.1이 "표로 묶어 준 지점일수록 좋은 문항 자리")
 *   · 강의 중 집중해 들을 것 (틀린 문항 = 청취 목표라는 §0의 관점)
 *   · 자료 밖 지식은 표시 (대화와 강의록이 어긋나면 강의록이 이긴다 → §0.1)
 *
 * 고쳐 쓸 때 이 근거가 같이 사라지므로, 화면에 규칙 문서를 가리키는 줄을 둔다.
 */
export const DEFAULT_PREVIEW_PROMPT = [
  "첨부한 자료는 의과대학 {과목} 강의 「{강의}」의 작년 강의 필기입니다.",
  "",
  "이 강의를 듣기 직전에 읽을 예습 정리를 만들어 주세요. 목적은 시험 대비가 아니라 그날 강의를 따라갈 수 있게 하는 것입니다. 5~10분 안에 읽을 분량이면 됩니다.",
  "",
  "이렇게 써 주세요.",
  "1. 먼저 이 강의가 무엇에 관한 것인지 한 문단, 그리고 다루는 항목을 한눈에 보는 표 하나.",
  "2. 그다음 개념을 강의 순서대로. 이걸 모르면 강의를 못 따라가는 뼈대만 남기고, 지엽적인 수치나 예외는 빼 주세요.",
  "3. 서로 헷갈리는 것(비슷한 질환·기전·용어)은 반드시 비교 표로 묶어 주세요.",
  "4. 마지막에 '강의 중 특히 집중해서 들을 것' 5가지.",
  "",
  "첨부 자료에 없는 내용은 넣지 마세요. 꼭 필요해서 넣는다면 자료 밖 지식이라고 표시해 주세요.",
].join("\n");

/**
 * 기본 링크의 프롬프트. **고정이다.**
 *
 * 반 전체가 하나의 대화를 읽으므로 무엇을 물었는지도 하나여야 한다. 사람마다
 * 다르게 물은 결과를 공통 링크로 돌리면 그 링크가 무엇인지 아무도 모른다.
 * 고쳐 쓰는 것은 개인 링크 쪽이다.
 */
export const SHARED_PREVIEW_PROMPT = ["{파일명}", "수업 전 예습용으로 설명해줘."].join("\n");

/**
 * 자리표시자.
 *
 * 고쳐 쓴 프롬프트도 강의마다 제 이름을 달고 나가야 하므로, 값을 박아 넣지 않고
 * 이 토큰을 남겨 둔다. 편집 화면이 이 목록을 그대로 보여 준다.
 */
export const PROMPT_TOKENS = [
  { token: "{파일명}", label: "붙이는 작년 필기 파일명", sample: "[250818_01]급성 염증의 병태 생리(고재문)_고명재 v2.pdf" },
  { token: "{강의}", label: "강의 제목", sample: "급성 염증의 병태 생리" },
  { token: "{과목}", label: "과목", sample: "질병의 병리학적 이해" },
  { token: "{교수}", label: "담당 교수", sample: "고재문" },
  { token: "{날짜}", label: "강의 날짜", sample: "2026-08-14" },
] as const;

/** 강의 제목에 붙은 담당 교수 괄호를 뗀다 — 프롬프트에서는 교수를 따로 부른다. */
function cleanTitle(title: string) {
  return title.replace(/\s*\([^()]*\)\s*$/, "").trim() || title;
}

/**
 * 템플릿에 이 강의의 값을 채운다. 채울 것이 없는 토큰은 지운다.
 *
 * `{파일명}`은 붙여 보내는 작년 필기의 이름 그대로다. 쪼갠 값들(`{강의}`·`{교수}`)로
 * 다시 조립하면 정보가 샌다 — 파일명에는 원래 run id와 필기자·판수까지 들어
 * 있는데 파싱하면 거기서 떨어져 나간다. 파일이 없을 때만 조립한 이름으로 떨어진다.
 */
export function renderPreviewPrompt(template: string, detail: LectureDetail) {
  const notesPrev = detail.files.find((file) => file.kind === "notes_prev");
  const values: Record<string, string> = {
    "{파일명}": notesPrev?.filename || `[${detail.date}] ${detail.title}`,
    "{강의}": cleanTitle(detail.title),
    "{과목}": detail.course || detail.subject,
    "{교수}": detail.professors.join(", "),
    "{날짜}": detail.date,
  };
  return template
    .replace(/\{파일명\}|\{강의\}|\{과목\}|\{교수\}|\{날짜\}/g, (token) => values[token] ?? "")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
}
