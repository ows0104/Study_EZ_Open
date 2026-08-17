// 웹앱 ↔ 확장 메시지 계약.
//
// 확장은 웹앱 번들을 import할 수 없으므로 같은 값을 양쪽에 둔다. 값의 정의는
// `web/src/bridge/protocol.ts`이고 이 파일은 그 사본이다. 한쪽만 고치면 조용히
// 끊기므로, 고칠 때는 둘을 같이 고친다.

globalThis.STUDYEZ_PROTOCOL = {
  /** 웹앱이 보내는 메시지의 출처. */
  WEBAPP_SOURCE: "studyez-webapp",
  /** 확장이 보내는 메시지의 출처. */
  EXTENSION_SOURCE: "studyez-ai-extension",
  /** 확장이 설치되면 `<html>`에 붙는 표시. 설치 여부 판정에 쓴다. */
  READY_ATTRIBUTE: "data-studyez-ai-extension",
  VERSION: "0.1.0",

  MESSAGES: {
    /** 웹앱 → 확장: 이 자료로 예습 대화를 열어 달라. */
    openPreview: "STUDYEZ_OPEN_PREVIEW",
    /** 확장 → 웹앱: 열기 요청 처리 결과. */
    openPreviewResult: "STUDYEZ_OPEN_PREVIEW_RESULT",
    /** 확장 → 웹앱: 만들어진 대화·공유 링크. */
    linkReady: "STUDYEZ_PREVIEW_LINK_READY",
    /** 웹앱 → 확장: 링크를 저장했다. 저장 전에는 지우지 않는다. */
    linkSaved: "STUDYEZ_PREVIEW_LINK_SAVED",
    /** 웹앱 → 확장: 이 탭으로 갈 링크가 남아 있으면 달라. */
    checkPending: "STUDYEZ_CHECK_PENDING_LINKS",
  },

  /**
   * 저장할 수 있는 링크 종류. Study_EZ의 `preview` 표가 두 칸을 따로 들고 있는
   * 것과 1:1로 맞는다.
   *
   *   chatgpt        → conversation_url  (만든 계정에서만 열린다)
   *   chatgpt_share  → share_url         (링크를 가진 누구나. Pre-Quiz의 재료)
   */
  LINK_KINDS: ["chatgpt", "chatgpt_share"],
};
