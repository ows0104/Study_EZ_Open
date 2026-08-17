/**
 * 웹앱 ↔ 크롬 확장(Study_EZ 예습 브리지) 메시지 계약.
 *
 * 값은 여기에서만 정의하고 확장은 같은 값을 복사해 쓴다(`chrome-extension/protocol.js`).
 * 한쪽만 고치면 조용히 끊기므로 둘을 같이 고친다.
 */

/** 웹앱이 보내는 메시지의 출처. */
export const WEBAPP_SOURCE = "studyez-webapp";
/** 확장이 보내는 메시지의 출처. */
export const EXTENSION_SOURCE = "studyez-ai-extension";
/** 확장이 설치되면 `<html>`에 붙는 표시. 설치 여부 판정에 쓴다. */
export const READY_ATTRIBUTE = "data-studyez-ai-extension";

export const MESSAGES = {
  openPreview: "STUDYEZ_OPEN_PREVIEW",
  openPreviewResult: "STUDYEZ_OPEN_PREVIEW_RESULT",
  linkReady: "STUDYEZ_PREVIEW_LINK_READY",
  linkSaved: "STUDYEZ_PREVIEW_LINK_SAVED",
  checkPending: "STUDYEZ_CHECK_PENDING_LINKS",
} as const;

/**
 * 저장할 수 있는 링크 종류. `preview` 표의 두 칸과 1:1이다.
 *
 *   chatgpt        → conversation_url  (만든 계정에서만 열린다)
 *   chatgpt_share  → share_url         (링크를 가진 누구나. Pre-Quiz의 재료)
 */
export const LINK_KINDS = ["chatgpt", "chatgpt_share"] as const;
export type LinkKind = (typeof LINK_KINDS)[number];

/** 확장이 이 시간 안에 답하지 않으면 응답 없음으로 본다. */
export const PREVIEW_TIMEOUT_MS = 5000;

/**
 * 확장 내려받는 곳.
 *
 * `web/scripts/pack-extension.mjs`가 `chrome-extension/`을 묶어 `public/`에
 * 떨어뜨리고, 빌드마다 다시 만든다. 사용자는 저장소를 갖고 있지 않으므로
 * "폴더를 고르세요"라고 말할 수 없다.
 */
export const EXTENSION_DOWNLOAD_URL = "/studyez-extension.zip";
