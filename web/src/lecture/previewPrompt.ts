import type { LectureDetail } from "../types/lectures";

/**
 * 개인 링크를 처음 열 때 채워지는 프롬프트.
 *
 * **사람마다 고쳐 쓴다.** 저장된 것이 있으면 그것을, 없으면 이것을 쓴다. 이건
 * 규칙이 아니라 고쳐 쓰기 전의 출발점이다.
 *
 * 문구는 기본 링크와 같다(2026-08-22 관리자 지시). 전에는 여기에 예습 정리의
 * 형식까지 열 줄 넘게 적혀 있었는데, 그러면 고쳐 쓸 사람은 지울 것부터 읽어야
 * 하고 안 고칠 사람은 자기가 무엇을 물었는지 모르는 채로 대화를 연다.
 *
 * 무엇을 요구하면 좋은 예습 대화가 되는지는
 * `.claude/skills/prequiz/references/preview-rules.md` §0.1에 있다. 고쳐 쓸
 * 사람이 참고할 자리다.
 */
export const DEFAULT_PREVIEW_PROMPT = [
  "{파일명}",
  "강의의 큰 흐름과 낯선 용어를 이해하는 데 필요한 만큼만 간략히 설명해줘. 미리 알아둘 핵심은 왜 필요한지 수업 내용과 연결하고, 세부 설명은 수업에 남겨둬. 족보는 중요한 개념과 출제 스타일을 판단하는 데 참고해줘.",
].join("\n");

/**
 * 기본 링크의 프롬프트. **고정이다.**
 *
 * 반 전체가 하나의 대화를 읽으므로 무엇을 물었는지도 하나여야 한다. 사람마다
 * 다르게 물은 결과를 공통 링크로 돌리면 그 링크가 무엇인지 아무도 모른다.
 * 고쳐 쓰는 것은 개인 링크 쪽이다.
 *
 * 지금은 개인 링크의 기본값과 문구가 같지만 같아야 하는 것은 아니다 — 이쪽은
 * 고정이고 저쪽은 출발점이라 각자 움직인다.
 */
export const SHARED_PREVIEW_PROMPT = DEFAULT_PREVIEW_PROMPT;

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
  const prompt = template
    .replace(/\{파일명\}|\{강의\}|\{과목\}|\{교수\}|\{날짜\}/g, (token) => values[token] ?? "")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
  return prompt;
}
