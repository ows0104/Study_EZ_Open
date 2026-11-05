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
  // `<html>`에 그대로 붙는다. 어느 빌드가 실려 있는지 개발자 도구에서 보인다 —
  // 소스를 고쳐도 `chrome://extensions`에서 새로고침하지 않으면 옛것이 돈다.
  VERSION: "1.3.23",

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
    /**
     * 웹앱 → 확장: 기본 링크를 지금 연다. 어느 강의인지 기억해 둬라.
     *
     * 공유 페이지에서 이어 물으면 AI 서비스가 그 시점까지를 복사해 **내 계정에 새
     * 대화를 만든다.** 그것이 사실상 그 사람의 개인 예습인데, 확장이 연 탭이
     * 아니라서 지금까지는 놓쳤다.
     */
    watchShare: "STUDYEZ_WATCH_SHARE",
    /**
     * 확장 → 웹앱: Quiz Bank 를 만든 ChatGPT 답 **본문**(2026-10-04). 관리자만 쓰는 갈래다 —
     * 링크가 아니라 마크다운 원문이 가고, 웹앱이 서버에 저장한다.
     */
    bankReady: "STUDYEZ_BANK_READY",
    /** 웹앱 → 확장: 그 본문을 저장했다. 저장 전에는 지우지 않는다(linkSaved 와 같은 규칙). */
    bankSaved: "STUDYEZ_BANK_SAVED",
  },

  /**
   * 저장할 수 있는 링크 종류. Study_EZ의 `preview` 표가 두 칸을 따로 들고 있는
   * 것과 1:1로 맞는다.
   *
   *   <provider>        → conversation_url  (만든 계정에서만 열린다)
   *   <provider>_share  → share_url         (서비스 정책에 따라 공유되는 기본 링크)
   */
  LINK_KINDS: ["chatgpt", "chatgpt_share", "gemini", "gemini_share", "claude", "claude_share", "chatgpt_review", "gemini_review", "claude_review", "chatgpt_bank", "chatgpt_bank_share"],
};
