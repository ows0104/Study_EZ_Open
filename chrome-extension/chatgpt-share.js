// Study_EZ가 연 대화의 공유 링크를 만들고 갱신한다.
//
// 배경이 잡아 두는 대화 주소(`/c/<id>`)는 **만든 계정에서만 열린다.** 같은 반
// 친구가 그 링크를 받으면 죽은 링크다. 공유 링크는 가진 사람 누구나 열 수 있고,
// `studyez preview`가 읽어 Pre-Quiz의 재료로 쓰는 것도 이쪽이다.
//
// 공유는 만든 시점의 스냅숏이라, 답이 다 나오기를 기다렸다가 처음 만들고 이후
// 턴마다 다시 낸다. 같은 대화를 다시 공개하면 share id가 그대로라 저장된 주소는
// 안 바뀌고 내용만 따라온다.

const LOG = "[Study_EZ share]";
const POLL_INTERVAL_MS = 4000;

let watch = null; // { lectureId }
let publishing = false;
let lastPublished = "";
let lastSharedNode = "";

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
  };
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
  if (!published.ok) throw new Error(`공유 공개에 실패했습니다 (HTTP ${published.status}).`);
  return draft?.share_url || `https://chatgpt.com/share/${shareId}`;
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

/** "settled": 새로 낼 것이 없다. "published": 새 스냅숏을 냈다. "pending": 아직 생성 중. */
async function publish() {
  const conversation = conversationId();
  if (!watch || publishing || !conversation) return "settled";
  publishing = true;
  try {
    let url = "";
    try {
      const token = await accessToken();
      const state = await conversationState(conversation, token);
      if (!state.finished || !state.currentNode) return "pending";
      if (state.currentNode === lastSharedNode) return "settled";
      url = await publishViaApi(conversation, token, state);
      lastSharedNode = state.currentNode;
    } catch (error) {
      console.info(LOG, "백엔드 공유 실패, 대화상자로 재시도합니다:", error);
      url = await publishViaDialog();
    }
    // share id는 다시 내도 그대로다. 웹앱에 알릴 것은 처음 하나뿐이고 이후 턴은
    // 같은 주소가 보여 주는 내용만 갱신된다.
    if (url && url !== lastPublished) {
      lastPublished = url;
      chrome.runtime.sendMessage({ type: "STUDYEZ_SHARE_LINK", url }, () => void chrome.runtime.lastError);
      console.info(LOG, "공유 링크를 저장했습니다:", url);
    }
    return "published";
  } catch (error) {
    console.warn(LOG, "공유 링크를 만들지 못했습니다:", error);
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

function startWatching(lectureId) {
  if (watch) return;
  watch = { lectureId };
  console.info(LOG, "이 대화의 공유 링크를 자동으로 저장합니다.");
  watchForCompletedTurns();
}

async function initialize() {
  // 배경은 대화 주소가 처음 생길 때 감시를 건다 — 사람이 확인 카드를 보고 전송을
  // 누르기까지 걸리는 시간이라 폴링으로 기다리기엔 길다. 그래서 밀어 준다.
  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "STUDYEZ_SHARE_WATCH_READY" && typeof message.lectureId === "string") {
      startWatching(message.lectureId);
    }
    return false;
  });

  // 이 스크립트가 듣기 전에 걸린 감시를 위한 경로. 새로고침·복원된 탭이 그렇다.
  for (let attempt = 0; attempt < 10 && !watch; attempt += 1) {
    const existing = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "STUDYEZ_GET_SHARE_WATCH" }, (response) => {
        resolve(chrome.runtime.lastError || !response?.ok ? null : response.lectureId);
      });
    });
    if (existing) return startWatching(existing);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

void initialize();
