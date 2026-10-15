import type { LinkKind } from "./protocol";
import { NATIVE_REVIEW_MIN_VERSION, versionAtLeast, type BridgeMode } from "./version";

/** 확장은 이 값을 그대로 돌려준다. 탭 새로고침 후에도 결과의 저장 위치를 알 수 있다. */
const REVIEW_REQUEST_PREFIX = "studyez:review:";
const BANK_REQUEST_PREFIX = "studyez:bank:";
const PERSONAL_KINDS = ["chatgpt", "gemini", "claude"] as const;

/** 예전 확장의 개인 대화 기능을 쓰되, 돌아온 링크를 복습에 저장할 표시를 붙인다. */
export function bridgeRequest<T extends { lectureId: string; mode: BridgeMode; promptVersion?: string }>(input: T, installed: string) {
  // Older extensions echo lectureId but discard the separate promptVersion field.
  if (input.mode === "bank") {
    if (!/^v?1\.\d+(?:\.\d+)?$/.test(input.promptVersion ?? "")) {
      throw new Error("출제 프롬프트 버전이 없습니다. 페이지를 새로고침한 뒤 다시 전송하세요.");
    }
    return { ...input, lectureId: `${BANK_REQUEST_PREFIX}${input.promptVersion}:${input.lectureId}` };
  }
  if (input.mode === "review" && !versionAtLeast(installed, NATIVE_REVIEW_MIN_VERSION)) {
    return { ...input, lectureId: REVIEW_REQUEST_PREFIX + input.lectureId, mode: "personal" as const };
  }
  return input;
}

export function bankDestination(lectureId: string) {
  if (!lectureId.startsWith(BANK_REQUEST_PREFIX)) return { lectureId, promptVersion: "" };
  const match = /^studyez:bank:(v?1\.\d+(?:\.\d+)?):([^/]+\/[^/]+)$/.exec(lectureId);
  return match ? { lectureId: match[2], promptVersion: match[1] } : null;
}

export function linkDestination(lectureId: string, kind: LinkKind) {
  if (!lectureId.startsWith(REVIEW_REQUEST_PREFIX)) return { lectureId, kind };
  // 개인 대화만 복습으로 옮긴다. 공유 결과나 잘못된 표시를 예습에 저장하지 않는다.
  if (!PERSONAL_KINDS.some((provider) => provider === kind)) return null;
  const originalId = lectureId.slice(REVIEW_REQUEST_PREFIX.length);
  if (!originalId || originalId.split("/").length !== 2 || originalId.split("/").some((part) => !part)) return null;
  return { lectureId: originalId, kind: `${kind}_review` as LinkKind };
}
