// Study_EZ가 연 대화의 링크를 웹앱에 돌려준다. 두 가지다.
//
// **대화 주소(`/c/<id>`)** 는 개인 링크다. 만든 계정에서만 열리므로 반 친구에게
// 주면 죽은 링크다. **공유 주소(`/share/<id>`)** 는 가진 사람 누구나 열 수 있고,
// `runner preview`가 읽어 Pre-Quiz의 재료로 쓰는 것도 이쪽이다. 공유는 기본
// 링크를 만들 때만 낸다(`mode === "shared"`).
//
// **둘 다 확인한 뒤에만 낸다.** 주소가 생긴 것은 성공이 아니다 — 공유는 비공개
// 초안일 수 있고(§`isPubliclyReadable`), 대화는 주소창에 `/c/…`가 떠 있어도
// 실제로는 안 만들어져 있을 수 있다(§`publish`).
//
// 공유는 만든 시점의 스냅숏이라, 답이 다 나오기를 기다렸다가 처음 만들고 이후
// 턴마다 다시 낸다. 같은 대화를 다시 공개하면 share id가 그대로라 저장된 주소는
// 안 바뀌고 내용만 따라온다.
//
// **Quiz Bank(`mode === "bank"`, 2026-10-04)는 링크가 아니라 답 본문을 낸다.** 관리자가
// 캘린더에서 연 대화다. 답이 끝나고 완료 표시가 있으면 마크다운 원문을 배경에 넘기고,
// 웹앱이 서버에 저장한다. 공유도 대화 주소 저장도 하지 않는다.

const LOG = "[Study_EZ preview]";
const POLL_INTERVAL_MS = 4000;

let watch = null; // { lectureId, mode }
let publishing = false;
/** 처음으로 존재를 확인한 대화. 이 탭은 그 대화만 따라간다. */
let bound = "";
let lastConversationUrl = "";
let lastShareUrl = "";
let lastSharedNode = "";
let lastBankNode = "";
const BANK_MARK = "STUDYEZ_BANK_COMPLETE";

function conversationId() {
  const match = /^\/(?:g\/[^/]+\/)?c\/([A-Za-z0-9_:-]+)/.exec(location.pathname);
  return match ? match[1] : "";
}

// ChatGPT의 백엔드는 쿠키만으로는 안 받는다. 만료된 토큰을 다시 집으려고
// 공유할 때마다 새로 읽는다.
async function accessToken() {
  const response = await fetch("/api/auth/session", { credentials: "include" });
  if (!response.ok) throw new Error(`세션을 읽지 못했습니다 (HTTP ${response.status}).`);
  const session = await response.json();
  if (!session?.accessToken) throw new Error("로그인 세션에 토큰이 없습니다.");
  return session.accessToken;
}

function api(path, token, init = {}) {
  return fetch(`/backend-api${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(init.headers || {}) },
  });
}

// 정지 버튼은 답이 다 그려진 뒤에도 잠깐 남는다. 그래서 화면이 아니라 대화 자신의
// 턴 상태로 판단한다 — 생성 중에 공유하면 반쯤 쓰다 만 답이 굳는다.
async function conversationState(conversation, token) {
  const response = await api(`/conversation/${conversation}`, token);
  if (!response.ok) throw new Error(`대화를 읽지 못했습니다 (HTTP ${response.status}).`);
  const body = await response.json();
  const message = body?.mapping?.[body?.current_node]?.message;
  return {
    currentNode: body?.current_node || "",
    finished:
      message?.author?.role === "assistant" &&
      message?.status === "finished_successfully" &&
      message?.end_turn === true,
    answer: answerText(body),
  };
}

/**
 * 마지막 사람 말 뒤의 답 전부. 「계속 생성」으로 이어 붙은 답이 여러 메시지일 수 있어
 * 현재 마디에서 사람 말까지 거슬러 올라가며 모은다. 도구 호출(recipient 가 all 이 아닌 것)과
 * 생각 과정(content_type 이 text 가 아닌 것)은 뺀다.
 */
function answerText(body) {
  const parts = [];
  let node = body?.mapping?.[body?.current_node];
  for (let hops = 0; node && hops < 200; hops += 1) {
    const message = node.message;
    if (message?.author?.role === "user") break;
    const content = message?.content;
    if (
      message?.author?.role === "assistant" &&
      (message.recipient ?? "all") === "all" &&
      ["text", "multimodal_text"].includes(content?.content_type)
    ) {
      const text = (content.parts || []).filter((part) => typeof part === "string").join("");
      if (text) parts.unshift(text);
    }
    node = node.parent ? body.mapping[node.parent] : null;
  }
  return parts.join("\n\n");
}

/** 이미 만들어 둔 공유가 있는지. 생성이 실패로 보고됐지만 실제로는 됐을 때의 복구로도 쓴다. */
async function existingShareUrl(conversation, token) {
  const response = await api("/shared_conversations?order=created&limit=50", token);
  if (!response.ok) return "";
  const body = await response.json();
  const items = Array.isArray(body?.items) ? body.items : [];
  const match = items.find((item) => item?.conversation_id === conversation);
  if (!match) return "";
  return match.share_url || (match.id ? `https://chatgpt.com/share/${match.id}` : "");
}

/**
 * 정말 남이 열 수 있는가.
 *
 * `/share/create`는 **비공개 초안**을 만든다. 공개로 바꾸는 것은 그다음 PATCH인데,
 * 그게 안 먹어도 주소는 멀쩡히 생긴다 — 만든 사람은 자기 초안이라 열리고 남은
 * 404를 본다. 실제로 그렇게 나갔다.
 *
 * 그래서 주소가 생긴 것으로 끝내지 않고 쿠키 없이 한 번 받아 본다. 같은 출처라
 * 요청은 나가고, 공개가 아니면 404가 돌아온다.
 */
async function isPubliclyReadable(url) {
  try {
    const response = await fetch(url, { credentials: "omit", redirect: "follow" });
    return response.ok;
  } catch (error) {
    console.warn(LOG, "공개 여부를 확인하지 못했습니다:", error);
    return false;
  }
}

async function publishViaApi(conversation, token, state) {
  const created = await api("/share/create", token, {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversation, current_node_id: state.currentNode, is_anonymous: true }),
  });
  if (!created.ok) {
    const recovered = await existingShareUrl(conversation, token);
    if (recovered) return recovered;
    throw new Error(`공유 생성에 실패했습니다 (HTTP ${created.status}).`);
  }
  const draft = await created.json();
  const shareId = draft?.share_id || draft?.id;
  if (!shareId) throw new Error("공유 응답에 share id가 없습니다.");

  // create는 비공개 초안까지만 만든다. 링크를 가진 사람이 열 수 있게 하는 것은
  // 이 호출이다. 검색 노출(is_discoverable)은 끈다 — 링크 밖으로는 안 나간다.
  //
  // current_node_id를 여기서 다시 보내는 이유: 이미 공유된 대화면 create가 기존
  // 공유를 그대로 돌려주므로, 스냅숏을 새 턴까지 미는 것은 이 호출뿐이다.
  const url = draft?.share_url || `https://chatgpt.com/share/${shareId}`;

  // 한 번 실패하면 다시 시도한다. PATCH가 안 먹는 이유가 일시적일 수 있고,
  // 여기서 포기하면 반 전체가 열지 못하는 링크가 나간다.
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const published = await api(`/share/${shareId}`, token, {
      method: "PATCH",
      body: JSON.stringify({
        share_id: shareId,
        current_node_id: state.currentNode,
        highlighted_message_id: draft?.highlighted_message_id ?? null,
        title: draft?.title ?? null,
        is_public: true,
        is_visible: true,
        is_anonymous: true,
        is_discoverable: false,
      }),
    });
    if (!published.ok) {
      console.warn(LOG, `공개 전환 ${attempt}차 실패 (HTTP ${published.status})`);
      continue;
    }
    if (await isPubliclyReadable(url)) return url;
    console.warn(LOG, `공개 전환은 200인데 ${attempt}차 확인에서 아직 안 열립니다:`, url);
  }
  throw new Error("공유를 공개로 바꾸지 못했습니다. 만든 계정에서만 열리는 주소입니다.");
}

function visible(element) {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function clickByLabel(pattern, root = document) {
  const button = [...root.querySelectorAll('button, [role="button"], [role="menuitem"]')].find((candidate) => {
    const label = `${candidate.getAttribute("aria-label") || ""} ${candidate.getAttribute("title") || ""} ${candidate.textContent || ""}`;
    return visible(candidate) && !candidate.disabled && pattern.test(label);
  });
  button?.click();
  return Boolean(button);
}

function shareUrlOnScreen() {
  const fromInput = [...document.querySelectorAll("input, textarea")]
    .map((field) => field.value || "")
    .find((value) => /^https:\/\/chatgpt\.com\/share\//.test(value.trim()));
  if (fromInput) return fromInput.trim();
  const fromText = /https:\/\/chatgpt\.com\/share\/[A-Za-z0-9_/:-]+/.exec(document.body.innerText || "");
  return fromText ? fromText[0] : "";
}

// 백엔드 계약이 바뀌었을 때의 대비책: 사람이 하듯 공유 대화상자를 몬다. 느리고
// 화면 구조에 묶여 있으므로 API 경로가 실패했을 때만 돈다.
async function publishViaDialog() {
  if (!clickByLabel(/(share|공유)/i)) throw new Error("공유 버튼을 찾지 못했습니다.");
  for (let attempt = 0; attempt < 40; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 250));
    const dialog = document.querySelector('[role="dialog"]');
    if (!dialog) continue;
    const onScreen = shareUrlOnScreen();
    if (onScreen) return onScreen;
    clickByLabel(/(create link|create public link|링크 만들기|링크 생성|공유 링크 복사)/i, dialog);
  }
  throw new Error("공유 대화상자에서 링크를 읽지 못했습니다.");
}

function sendLink(type, url) {
  chrome.runtime.sendMessage({ type, url }, () => void chrome.runtime.lastError);
}

/**
 * 공유 주소를 확인하고 내보낸다.
 *
 * **확인 안 된 주소는 내보내지 않는다.** 화면에서 긁어 온 주소가 아직 비공개
 * 초안일 수 있고, 그것이 반의 기본 링크로 저장되면 만든 사람 말고는 아무도
 * 못 연다.
 */
async function settleShare(url) {
  if (url && !(await isPubliclyReadable(url))) {
    console.error(LOG, "공개되지 않은 주소라 저장하지 않습니다:", url);
    lastSharedNode = "";
    return "settled";
  }
  // share id는 다시 내도 그대로다. 웹앱에 알릴 것은 처음 하나뿐이고 이후 턴은
  // 같은 주소가 보여 주는 내용만 갱신된다.
  if (url && url !== lastShareUrl) {
    lastShareUrl = url;
    sendLink("STUDYEZ_SHARE_LINK", url);
    console.info(LOG, "공유 링크를 저장했습니다:", url);
  }
  return "published";
}

/** "settled": 새로 낼 것이 없다. "published": 새 스냅숏을 냈다. "pending": 아직 생성 중. */
async function publish() {
  const conversation = conversationId();
  if (!watch || publishing || !conversation) return "settled";
  // 한 번 확인한 대화만 따라간다. 같은 탭에서 옛 대화로 건너뛰어도 그것이 이
  // 강의의 예습이 되지는 않는다.
  if (bound && bound !== conversation) return "settled";
  publishing = true;
  try {
    let token = "";
    let state = null;
    try {
      token = await accessToken();
      state = await conversationState(conversation, token);
    } catch (error) {
      console.info(LOG, "대화 상태를 읽지 못했습니다:", error);
      // 공유에는 백엔드 계약이 바뀌었을 때의 대비책이 있다. 대화 주소는 읽어
      // 낸 것 자체가 저장 조건이므로 다음 차례에 다시 본다.
      if (watch.mode !== "shared") return "pending";
      lastSharedNode = "";
      return await settleShare(await publishViaDialog());
    }
    if (!state.finished || !state.currentNode) return "pending";
    bound = conversation;

    if (watch.mode === "bank") {
      if (state.currentNode === lastBankNode) return "settled";
      // 끝났는데 완료 표시가 없으면 잘린 답이다. 내지 않는다 — 「계속 생성」을 누르면
      // 화면이 움직이고 다시 여기로 온다.
      if (!state.answer.includes(BANK_MARK)) {
        console.info(LOG, "답이 끝났지만 완료 표시가 없습니다. 이어서 생성되기를 기다립니다.");
        return "settled";
      }
      lastBankNode = state.currentNode;
      chrome.runtime.sendMessage(
        { type: "STUDYEZ_BANK_ANSWER", raw: state.answer, url: `https://chatgpt.com/c/${conversation}` },
        () => void chrome.runtime.lastError,
      );
      console.info(LOG, `Quiz Bank 답 본문을 넘겼습니다 (${state.answer.length}자).`);
      return "published";
    }

    // **대화 주소는 여기서 처음 낸다.**
    //
    // 주소창에 `/c/<id>`가 뜬 것은 그 대화가 있다는 뜻이 아니다. 보내기 전에도
    // 뜨고, 못 보내면 그 id로는 아무것도 안 남는다. 그렇게 저장된 주소를 나중에
    // 열면 대화가 아니라 **빈 ChatGPT 창**이 뜬다. 실제로 그렇게 나갔다.
    //
    // 그래서 주소를 읽는 것으로 끝내지 않고 이 계정으로 대화를 한 번 받아 본
    // 뒤에 낸다. 위의 `conversationState`가 그 확인이다 — 답이 하나 끝나 있는
    // 대화만 여기까지 온다.
    const url = `https://chatgpt.com/c/${conversation}`;
    if (url !== lastConversationUrl) {
      lastConversationUrl = url;
      sendLink("STUDYEZ_CONVERSATION_LINK", url);
      console.info(LOG, "대화 주소를 저장했습니다:", url);
    }

    if (watch.mode !== "shared") return "published";
    if (state.currentNode === lastSharedNode) return "settled";
    try {
      const shareUrl = await publishViaApi(conversation, token, state);
      lastSharedNode = state.currentNode;
      return await settleShare(shareUrl);
    } catch (error) {
      console.info(LOG, "백엔드 공유 실패, 대화상자로 재시도합니다:", error);
      lastSharedNode = "";
      return await settleShare(await publishViaDialog());
    }
  } catch (error) {
    console.warn(LOG, "예습 링크를 만들지 못했습니다:", error);
    return "settled";
  } finally {
    publishing = false;
  }
}

// 정지 버튼이 자기 턴보다 오래 남아 있을 때가 있어서 그것으로는 판단하지 않는다.
// DOM 변화는 "뭔가 움직였으니 볼 만하다"까지만 말하고, 낼 턴이 있는지는 대화의
// end_turn이 정한다.
function watchForCompletedTurns() {
  let dirty = true;
  new MutationObserver(() => {
    dirty = true;
  }).observe(document.body, { childList: true, subtree: true });

  window.setInterval(async () => {
    if (!dirty || publishing || document.hidden) return;
    if ((await publish()) !== "pending") dirty = false;
  }, POLL_INTERVAL_MS);
}

function startWatching(lectureId, mode) {
  if (watch) return;
  watch = { lectureId, mode: ["shared", "bank"].includes(mode) ? mode : "personal" };
  console.info(LOG, `이 대화의 링크를 자동으로 저장합니다 (${watch.mode}).`);
  watchForCompletedTurns();
}

async function initialize() {
  // 배경은 탭을 열 때 감시를 건다 — 사람이 확인 카드를 보고 전송을 누르기까지
  // 걸리는 시간이라 폴링으로 기다리기엔 길다. 그래서 밀어 준다.
  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "STUDYEZ_WATCH_READY" && typeof message.lectureId === "string") {
      startWatching(message.lectureId, message.mode);
    }
    return false;
  });

  // 이 스크립트가 듣기 전에 걸린 감시를 위한 경로. 새로고침·복원된 탭과, 기본
  // 링크 페이지에서 이어 물어 갈라져 나온 대화가 그렇다.
  for (let attempt = 0; attempt < 10 && !watch; attempt += 1) {
    const existing = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "STUDYEZ_GET_WATCH" }, (response) => {
        resolve(chrome.runtime.lastError || !response?.ok ? null : response);
      });
    });
    if (existing) return startWatching(existing.lectureId, existing.mode);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

void initialize();
