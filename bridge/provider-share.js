// Gemini와 Claude의 개인 대화 주소 및 공개 공유 주소를 Study EZ로 돌려준다.
// ChatGPT는 완료 상태와 공유 API가 달라 `chatgpt-share.js`가 따로 맡는다.

(() => {
  const LOG = "[Study_EZ preview]";
  const POLL_INTERVAL_MS = 3000;
  const provider = location.origin === "https://gemini.google.com" ? "gemini"
    : location.origin === "https://claude.ai" ? "claude" : "";
  if (!provider) return;

  let watch = null;
  let publishing = false;
  let dirty = true;
  let boundConversation = "";
  let lastConversationUrl = "";
  let lastShareUrl = "";

  function visible(element) {
    if (!element) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function conversationUrl() {
    if (provider === "gemini" && /^\/app\/[A-Za-z0-9_-]+/.test(location.pathname)) return location.href.split(/[?#]/)[0];
    if (provider === "claude" && /^\/chat\/[A-Za-z0-9-]+/.test(location.pathname)) return location.href.split(/[?#]/)[0];
    return "";
  }

  function buttonLabel(button) {
    return `${button.getAttribute("aria-label") || ""} ${button.getAttribute("title") || ""} ${button.textContent || ""}`.trim();
  }

  function clickByLabel(pattern, root = document, exact = false) {
    const button = [...root.querySelectorAll('button, [role="button"], [role="menuitem"], gem-icon-button')].find((candidate) => {
      const label = buttonLabel(candidate);
      return visible(candidate) && !candidate.disabled && (exact ? pattern.test(label.trim()) : pattern.test(label));
    });
    button?.click();
    return Boolean(button);
  }

  function responseFinished() {
    const stop = [...document.querySelectorAll('button, [role="button"]')].some((button) =>
      visible(button) && /(stop|cancel response|stop generating|응답 중지|생성 중지)/i.test(buttonLabel(button))
    );
    if (stop) return false;
    if (provider === "gemini") {
      const responses = [...document.querySelectorAll("model-response")];
      const last = responses.at(-1);
      return Boolean(last?.querySelector(".response-footer.complete") && last.querySelector("message-content"));
    }
    const userTurns = document.querySelectorAll('[data-testid="user-message"]').length;
    const assistantTurns = document.querySelectorAll(".font-claude-response").length;
    return userTurns > 0 && assistantTurns >= userTurns;
  }

  function shareUrlOnScreen(root = document) {
    const candidates = [
      ...[...root.querySelectorAll("a[href]")].map((item) => item.href || ""),
      ...[...root.querySelectorAll("input, textarea")].map((item) => item.value || ""),
      root.body?.innerText || root.textContent || "",
    ];
    const pattern = provider === "claude"
      ? /https:\/\/claude\.ai\/share\/[A-Za-z0-9-]+/
      : /https:\/\/(?:g\.co\/gemini\/share|gemini\.google\.com\/share)\/[A-Za-z0-9_-]+/;
    for (const candidate of candidates) {
      const match = pattern.exec(candidate);
      if (match) return match[0];
    }
    return "";
  }

  function verifyShare(url) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "STUDYEZ_VERIFY_SHARE_LINK", url }, (response) => {
        resolve(chrome.runtime.lastError || !response?.ok ? "" : response.url || url);
      });
    });
  }

  async function publishClaudeShare() {
    if (!clickByLabel(/^(share|공유)$/i) && !document.querySelector('[role="dialog"]')) {
      throw new Error("Claude의 공유 버튼을 찾지 못했습니다.");
    }
    for (let attempt = 0; attempt < 50; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      const dialog = document.querySelector('[role="dialog"]');
      if (!dialog) continue;
      const existing = shareUrlOnScreen(dialog);
      if (existing) return existing;
      if (attempt < 8) clickByLabel(/(create public link|공개 링크 생성)/i, dialog);
      if (attempt >= 3) clickByLabel(/^(create share link|공유 링크 생성|share)$/i, dialog, true);
    }
    throw new Error("Claude 공유 대화상자에서 공개 링크를 읽지 못했습니다.");
  }

  async function publishGeminiShare() {
    const response = [...document.querySelectorAll("model-response")].at(-1);
    if (!response) throw new Error("Gemini의 완성된 답변을 찾지 못했습니다.");
    const shareButton = [...response.querySelectorAll('button, [role="button"], gem-icon-button')].find((button) =>
      visible(button) && /(share|공유)/i.test(buttonLabel(button))
    );
    if (!shareButton) {
      throw new Error("Gemini가 이 대화에 공개 공유 버튼을 제공하지 않습니다.");
    }
    shareButton.click();
    for (let attempt = 0; attempt < 50; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 200));
      const existing = shareUrlOnScreen();
      if (existing) return existing;
      clickByLabel(/(share conversation|create public link|대화 공유|공개 링크 만들기|공개 링크 생성)/i);
    }
    throw new Error("Gemini 공유 화면에서 공개 링크를 읽지 못했습니다.");
  }

  function sendLink(type, url) {
    chrome.runtime.sendMessage({ type, url }, () => void chrome.runtime.lastError);
  }

  async function publish() {
    const conversation = conversationUrl();
    if (!watch || publishing || !conversation) return "settled";
    if (boundConversation && boundConversation !== conversation) return "settled";
    if (!responseFinished()) return "pending";
    boundConversation = conversation;
    publishing = true;
    try {
      if (conversation !== lastConversationUrl) {
        lastConversationUrl = conversation;
        sendLink("STUDYEZ_CONVERSATION_LINK", conversation);
        console.info(LOG, `${provider} 개인 대화 주소를 저장했습니다:`, conversation);
      }
      if (watch.mode !== "shared" || lastShareUrl) return "published";
      const candidate = provider === "claude" ? await publishClaudeShare() : await publishGeminiShare();
      const verified = await verifyShare(candidate);
      if (!verified) throw new Error("로그인 없이 공개 링크를 열 수 없습니다.");
      lastShareUrl = verified;
      sendLink("STUDYEZ_SHARE_LINK", verified);
      console.info(LOG, `${provider} 공개 공유 주소를 저장했습니다:`, verified);
      return "published";
    } catch (error) {
      console.warn(LOG, `${provider} 예습 링크를 만들지 못했습니다:`, error);
      return "settled";
    } finally {
      publishing = false;
    }
  }

  function startWatching(lectureId, watchedProvider, mode) {
    if (watch || watchedProvider !== provider) return;
    watch = { lectureId, mode: ["shared", "review"].includes(mode) ? mode : "personal" };
    new MutationObserver(() => { dirty = true; }).observe(document.body, { childList: true, subtree: true });
    window.setInterval(async () => {
      if (!dirty || publishing || document.hidden) return;
      if ((await publish()) !== "pending") dirty = false;
    }, POLL_INTERVAL_MS);
    console.info(LOG, `${provider} 대화 링크를 자동으로 저장합니다 (${watch.mode}).`);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "STUDYEZ_WATCH_READY") startWatching(message.lectureId, message.provider, message.mode);
    return false;
  });

  void (async () => {
    for (let attempt = 0; attempt < 10 && !watch; attempt += 1) {
      const existing = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ type: "STUDYEZ_GET_WATCH" }, (response) => {
          resolve(chrome.runtime.lastError || !response?.ok ? null : response);
        });
      });
      if (existing) return startWatching(existing.lectureId, existing.provider, existing.mode);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  })();
})();
