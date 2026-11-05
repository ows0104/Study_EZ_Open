// Study_EZ가 연 대화의 링크를 웹앱에 돌려준다. 두 가지다.
//
// **대화 주소(`/c/<id>`)** 는 개인 링크다. 만든 계정에서만 열리므로 반 친구에게
// 주면 죽은 링크다. **공유 주소(`/share/<id>`)** 는 가진 사람 누구나 열 수 있고,
// `runner preview`가 읽어 Pre-Quiz의 재료로 쓰는 것도 이쪽이다. 공유는 기본
// 링크 또는 관리자 문제은행을 만들 때 낸다(`shared`·`bank`).
//
// **둘 다 확인한 뒤에만 낸다.** 주소가 생긴 것은 성공이 아니다 — 공유는 비공개
// 초안일 수 있고(§`isPubliclyReadable`), 대화는 주소창에 `/c/…`가 떠 있어도
// 실제로는 안 만들어져 있을 수 있다(§`publish`).
//
// 공유는 만든 시점의 스냅숏이라, 답이 다 나오기를 기다렸다가 처음 만들고 이후
// 턴마다 다시 낸다. 같은 대화를 다시 공개하면 share id가 그대로라 저장된 주소는
// 안 바뀌고 내용만 따라온다.
//
// Quiz Bank도 공유·개인 주소를 각각 낸다. 본문·CLI 검증과 무관하게 링크를 보관한다.

const LOG = "[Study_EZ preview]";
const POLL_INTERVAL_MS = 4000;

let watch = null; // { lectureId, mode }
let publishing = false;
/** 처음으로 존재를 확인한 대화. 이 탭은 그 대화만 따라간다. */
let bound = "";
let lastConversationUrl = "";
let lastShareUrl = "";
let lastBankAnswer = "";
let lastBankFile = null;
let lastBankFileNode = "";
let lastSavedBankFileHash = "";
let lastSharedNode = "";
let contextInvalidated = false;
let turnObserver = null;
let pollTimer = null;
let retryAfter = 0;
let failures = 0;

function invalidateShareContext() {
  if (contextInvalidated) return;
  contextInvalidated = true;
  turnObserver?.disconnect();
  if (pollTimer !== null) window.clearInterval(pollTimer);
  console.info(LOG, "확장 연결이 끊겼습니다. 확장을 다시 로드한 뒤 이 대화 탭을 새로고침해 주세요.");
}

function shareContextAvailable() {
  try {
    if (!contextInvalidated && chrome.runtime?.id) return true;
  } catch {}
  invalidateShareContext();
  return false;
}

function sendShareMessage(message, done = () => {}) {
  if (!shareContextAvailable()) return false;
  try {
    chrome.runtime.sendMessage(message, (response) => {
      let error = "";
      try {
        error = chrome.runtime.lastError?.message || "";
      } catch (failure) {
        error = failure?.message || String(failure);
      }
      if (/extension context invalidated/i.test(error)) invalidateShareContext();
      done(error ? null : response);
    });
    return true;
  } catch (error) {
    if (/extension context invalidated/i.test(error?.message || "")) invalidateShareContext();
    done(null);
    return false;
  }
}

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

/** Markdown code fences are presentation wrappers, not an unfinished bank. */
function completedBankAnswer(answer) {
  const raw = typeof answer === "string" ? answer : "";
  if (raw.trimEnd().endsWith("STUDYEZ_BANK_COMPLETE")) return raw;
  let fence = null;
  let wrapped = false;
  const lines = [];
  for (const line of raw.split("\n")) {
    const match = /^ {0,3}(`{3,}|~{3,})(markdown|md)?[ \t\r]*$/i.exec(line);
    if (match && !fence) {
      fence = match[1];
      wrapped = true;
    } else if (fence && match && !match[2] && match[1][0] === fence[0] && match[1].length >= fence.length) {
      fence = null;
    } else {
      lines.push(line);
    }
  }
  const unwrapped = lines.join("\n").trim();
  return wrapped && !fence && /^### Q\d+\s*\|/m.test(unwrapped)
    && unwrapped.endsWith("STUDYEZ_BANK_COMPLETE") ? unwrapped : raw;
}

function bankFileTarget() {
  return globalThis.StudyEZBankFile.lectureTarget(watch?.lectureId, watch?.promptVersion);
}

function fileMode() {
  return globalThis.StudyEZBankFile.required(bankFileTarget());
}

async function deliverBankFile(result, manualFile = false) {
  const url = `https://chatgpt.com/c/${conversationId()}`;
  return new Promise(resolve => {
    if (!sendShareMessage({ type: "STUDYEZ_BANK_ANSWER", raw: result.raw, responseFile: result.responseFile, manualFile, url },
      response => resolve(response?.ok === true))) resolve(false);
  });
}

function offerBankFile(message) {
  if (document.getElementById("studyez-bank-file")) return;
  const panel = document.createElement("div");
  panel.id = "studyez-bank-file";
  panel.style.cssText = "position:fixed;bottom:18px;right:18px;z-index:2147483647;background:#fff;color:#18212f;border:1px solid #aaa;border-radius:10px;padding:12px;max-width:360px;font:14px sans-serif;box-shadow:0 2px 15px #0003";
  const label = document.createElement("label");
  label.textContent = "Study EZ · 완성된 문제은행 파일 전달 ";
  const input = document.createElement("input"); input.type = "file"; input.accept = ".json,application/json,.md,text/markdown";
  const status = document.createElement("p"); status.textContent = message;
  input.addEventListener("change", async () => {
    const file = input.files?.[0]; if (!file) return;
    input.disabled = true;
    try {
      const result = await globalThis.StudyEZBankFile.readFile(file, bankFileTarget());
      if (!(await deliverBankFile(result, true))) throw new Error("전달 확인을 받지 못했습니다. Study EZ 탭을 열고 다시 선택하세요.");
      lastBankAnswer = result.raw;
      status.textContent = `${result.info.question_count}문항 파일을 확인해 전달했습니다. 사이트의 저장·검수 상태를 확인하세요.`;
    } catch (error) { status.textContent = error.message; }
    finally { input.disabled = false; input.value = ""; }
  });
  const close = document.createElement("button"); close.textContent = "닫기";
  close.addEventListener("click", () => panel.remove());
  label.appendChild(input); panel.append(label, status, close); document.body.appendChild(panel);
}

/** Use only real download links exposed by this reply; never invent a sandbox API. */
async function collectBankFile(answer) {
  const target = bankFileTarget();
  const filename = globalThis.StudyEZBankFile.filenameFor(target);
  const links = [...answer.matchAll(/\[[^\]]*\]\(([^\s)]+)\)/g)].map(m => m[1]);
  const linked = links.find(value => {
    try { return decodeURIComponent(value.split(/[?#]/)[0]).endsWith('/' + filename); } catch { return false; }
  });
  const candidates = [linked, ...[...document.querySelectorAll('a[href]')]
    .filter(a => (a.textContent || '').includes(filename)).map(a => a.href)];
  for (const value of candidates) {
    if (!value) continue;
    let url; try { url = new URL(value, location.href); } catch { continue; }
    if (url.protocol !== 'https:' || url.origin !== 'https://chatgpt.com'
        || !url.pathname.startsWith('/backend-api/')) continue;
    try {
      const response = await fetch(url.href, { credentials: 'include', cache: 'no-store', redirect: 'error' });
      if (!response.ok) continue;
      const length = Number(response.headers.get('content-length') || 0);
      if (length > globalThis.StudyEZBankFile.MAX_BYTES) throw new Error('파일이 너무 큽니다.');
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.byteLength > globalThis.StudyEZBankFile.MAX_BYTES) throw new Error('파일이 너무 큽니다.');
      const raw = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
      return await globalThis.StudyEZBankFile.describe(raw, target, filename);
    } catch (error) { console.info(LOG, '파일 직접 회수 대기:', error.message); }
  }
  const downloaded = await new Promise(resolve => {
    if (!sendShareMessage({type:'STUDYEZ_BANK_DOWNLOAD_FILE'},response => resolve(response?.ok && typeof response.raw === 'string' ? response : null))) resolve(null);
  });
  if (downloaded) return globalThis.StudyEZBankFile.describe(downloaded.raw,target,downloaded.filename);
  offerBankFile('문제은행 파일의 자동 다운로드를 재시도하고 있습니다. 파일이 준비되면 검수에 전달합니다. 직접 선택할 수도 있습니다.');
  return null;
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

function buttonByLabel(pattern, root = document) {
  const button = [...root.querySelectorAll('button, [role="button"], [role="menuitem"]')].find((candidate) => {
    const labels = [candidate.getAttribute("aria-label") || "", candidate.getAttribute("title") || "", candidate.textContent || ""];
    return visible(candidate) && !candidate.disabled && candidate.getAttribute("aria-disabled") !== "true" && labels.some((label) => pattern.test(label.trim()));
  });
  return button;
}

function clickByLabel(pattern, root = document) {
  const button = buttonByLabel(pattern, root);
  button?.click();
  return Boolean(button);
}

function normalizedShareUrl(value) {
  try {
    const url = new URL(value.trim(), "https://chatgpt.com");
    if (url.origin !== "https://chatgpt.com" || url.username || url.password) return "";
    if (!/^\/share\/(?:e\/)?[A-Za-z0-9_-]+\/?$/.test(url.pathname)) return "";
    return `${url.origin}${url.pathname.replace(/\/$/, "")}`;
  } catch {
    return "";
  }
}

function shareDialog() {
  return [...document.querySelectorAll('[role="dialog"], [aria-modal="true"]')]
    .find((dialog) => visible(dialog) && /(share|공유)/i.test(`${dialog.getAttribute("aria-label") || ""} ${dialog.innerText || ""}`));
}

function shareUrlOnScreen(root = shareDialog()) {
  if (!root) return "";
  for (const field of root.querySelectorAll("input, textarea, a[href]")) {
    const value = field.value || field.getAttribute("href") || "";
    const url = normalizedShareUrl(value);
    if (url) return url;
  }
  const matches = (root.innerText || "").match(/https:\/\/chatgpt\.com\/share\/(?:e\/)?[A-Za-z0-9_-]+/g) || [];
  return matches.map(normalizedShareUrl).find(Boolean) || "";
}

// 백엔드 계약이 바뀌었을 때의 대비책: 사람이 하듯 공유 대화상자를 몬다. 느리고
// 화면 구조에 묶여 있으므로 API 경로가 실패했을 때만 돈다.
async function publishViaDialog(conversation = conversationId(), token = "") {
  if (!shareDialog()) {
    const header = document.querySelector("header");
    if (!(header && clickByLabel(/(share|공유)/i, header)) && !clickByLabel(/^(\s*)(share|공유)(\s*)$/i)) {
      throw new Error("공유 버튼을 찾지 못했습니다.");
    }
  }
  const clicked = new Set();
  let actionStarted = false;
  let actionAttempt = -1;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (!shareContextAvailable()) throw new Error("Extension context invalidated.");
    if (conversationId() !== conversation) throw new Error("공유 중 대화가 바뀌었습니다.");
    await new Promise((resolve) => setTimeout(resolve, 250));
    if (conversationId() !== conversation) throw new Error("공유 중 대화가 바뀌었습니다.");
    const dialog = shareDialog();
    if (!dialog) continue;
    // 기존 링크가 보여도 업데이트 버튼이 있으면 먼저 새 답까지 공유한다.
    const update = buttonByLabel(/(update(?: (?:public )?link)?|링크 업데이트|업데이트)/i, dialog);
    const action = update || buttonByLabel(/(create (?:public )?link|copy link|^copy$|링크 만들기|링크 생성|(?:공유 )?링크 복사|^복사$)/i, dialog);
    const actionKind = update ? "update" : "create-or-copy";
    if (action && !clicked.has(actionKind)) {
      clicked.add(actionKind);
      action.click();
      actionStarted = true;
      actionAttempt = attempt;
      continue;
    }
    if (actionStarted && attempt - actionAttempt < 4) continue;
    const onScreen = shareUrlOnScreen(dialog);
    if (onScreen) return onScreen;
    // 복사 버튼만 있고 주소가 DOM에 없는 화면도 있다. 클립보드 대신
    // 이 대화 id와 정확히 일치하는 공유 기록을 읽는다.
    if (actionStarted && token && attempt % 8 === 7) {
      const recovered = normalizedShareUrl(await existingShareUrl(conversation, token));
      if (conversationId() !== conversation) throw new Error("공유 중 대화가 바뀌었습니다.");
      if (recovered) return recovered;
    }
  }
  throw new Error("공유 대화상자에서 링크를 읽지 못했습니다.");
}

function sendLink(type, url) {
  return sendShareMessage({ type, url });
}

/**
 * 공유 주소를 확인하고 내보낸다.
 *
 * **확인 안 된 주소는 내보내지 않는다.** 화면에서 긁어 온 주소가 아직 비공개
 * 초안일 수 있고, 그것이 반의 기본 링크로 저장되면 만든 사람 말고는 아무도
 * 못 연다.
 */
async function settleShare(url) {
  url = normalizedShareUrl(url || "");
  if (!url) throw new Error("유효한 공유 주소를 읽지 못했습니다.");
  if (!(await isPubliclyReadable(url))) {
    console.error(LOG, "공개되지 않은 주소라 저장하지 않습니다:", url);
    lastSharedNode = "";
    throw new Error("공유 주소의 공개 여부를 확인하지 못했습니다.");
  }
  // share id는 다시 내도 그대로다. 웹앱에 알릴 것은 처음 하나뿐이고 이후 턴은
  // 같은 주소가 보여 주는 내용만 갱신된다.
  if (url && url !== lastShareUrl) {
    if (!sendLink("STUDYEZ_SHARE_LINK", url)) return "pending";
    lastShareUrl = url;
    console.info(LOG, "공유 링크를 저장했습니다:", url);
  }
  return "published";
}

/** "settled": 새로 낼 것이 없다. "published": 새 스냅숏을 냈다. "pending": 아직 생성 중. */
async function publish() {
  if (!shareContextAvailable()) return "settled";
  if (Date.now() < retryAfter) return "pending";
  const conversation = conversationId();
  if (!watch || publishing || !conversation) return "settled";
  // 한 번 확인한 대화만 따라간다. 같은 탭에서 옛 대화로 건너뛰어도 그것이 이
  // 강의의 예습이 되지는 않는다.
  if (bound && bound !== conversation) return "settled";
  // 생성 중에는 상태 API를 반복해서 읽지 않는다. UI는 확인을 미루는 신호만
  // 주고, 저장 허용은 아래 finished_successfully/end_turn 검사로 결정한다.
  if (buttonByLabel(/^(?:stop generating|stop|중지|생성 중지)$/i)) return "pending";
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
      // 이 실패도 바깥 재시도 간격을 적용한다. 여기서 pending으로 삼키면
      // 429 응답에도 4초마다 같은 요청을 보내 한도가 풀리지 않는다.
      if (!["shared", "bank"].includes(watch.mode)) throw error;
      lastSharedNode = "";
      const result = await settleShare(await publishViaDialog(conversation, token));
      if (result === "published") {
        failures = 0;
        retryAfter = 0;
      }
      return result;
    }
    if (!state.finished || !state.currentNode) return "pending";
    bound = conversation;

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
    // 공유 생성 실패와 무관하게 완성된 문항을 먼저 러너에 전달한다.
    const needsFile = watch.mode === 'bank' && fileMode();
    const bankFile = needsFile ? (lastBankFileNode === state.currentNode && lastBankFile
      ? lastBankFile : await collectBankFile(state.answer)) : null;
    if (needsFile && !bankFile) return 'pending';
    if (bankFile) { lastBankFile = bankFile; lastBankFileNode = state.currentNode; }
    if (bankFile && bankFile.raw !== lastBankAnswer) {
      if (!(await deliverBankFile(bankFile))) return "pending";
      lastBankAnswer = bankFile.raw;
    }
    // A background storage receipt is not a server receipt. Only publish links
    // after Study EZ confirms the file, so the runner cannot ingest share prose.
    if (needsFile && lastSavedBankFileHash !== bankFile.responseFile.sha256) return 'pending';
    const bankAnswer = completedBankAnswer(state.answer);
    if (watch.mode === "bank" && !fileMode() && bankAnswer.trimEnd().endsWith("STUDYEZ_BANK_COMPLETE")
        && bankAnswer.length >= 200 && bankAnswer.length <= 2_000_000
        && bankAnswer !== lastBankAnswer) {
      const stored = await new Promise((resolve) => {
        if (!sendShareMessage({ type: "STUDYEZ_BANK_ANSWER", raw: bankAnswer, url },
            (response) => resolve(response?.ok === true))) resolve(false);
      });
      if (!stored) return "pending";
      lastBankAnswer = bankAnswer;
    }
    if (url !== lastConversationUrl) {
      if (!sendLink("STUDYEZ_CONVERSATION_LINK", url)) return "pending";
      lastConversationUrl = url;
      console.info(LOG, "대화 주소를 저장했습니다:", url);
    }

    if (!["shared", "bank"].includes(watch.mode)) return "published";
    if (state.currentNode === lastSharedNode) return "settled";
    try {
      const shareUrl = await publishViaApi(conversation, token, state);
      const result = await settleShare(shareUrl);
      if (result === "published") {
        lastSharedNode = state.currentNode;
        failures = 0;
        retryAfter = 0;
      }
      return result;
    } catch (error) {
      console.info(LOG, "백엔드 공유 실패, 대화상자로 재시도합니다:", error);
      lastSharedNode = "";
      const result = await settleShare(await publishViaDialog(conversation, token));
      if (result === "published") {
        lastSharedNode = state.currentNode;
        failures = 0;
        retryAfter = 0;
      }
      return result;
    }
  } catch (error) {
    if (contextInvalidated) return "settled";
    failures += 1;
    retryAfter = Date.now() + Math.min(120_000, 30_000 * 2 ** Math.min(failures - 1, 2));
    console.warn(LOG, "예습 링크를 만들지 못했습니다:", error);
    return "pending";
  } finally {
    publishing = false;
  }
}

// 정지 버튼이 자기 턴보다 오래 남아 있을 때가 있어서 그것으로는 판단하지 않는다.
// DOM 변화는 "뭔가 움직였으니 볼 만하다"까지만 말하고, 낼 턴이 있는지는 대화의
// end_turn이 정한다.
function watchForCompletedTurns() {
  let revision = 1;
  let checkedRevision = 0;
  turnObserver = new MutationObserver(() => {
    revision += 1;
  });
  turnObserver.observe(document.body, { childList: true, subtree: true });

  pollTimer = window.setInterval(async () => {
    if (!shareContextAvailable() || revision === checkedRevision || publishing || document.hidden) return;
    const startedRevision = revision;
    if ((await publish()) !== "pending") checkedRevision = startedRevision;
  }, POLL_INTERVAL_MS);
}

function startWatching(lectureId, mode, promptVersion = "") {
  if (watch) return;
  watch = { lectureId, promptVersion, mode: ["shared", "bank", "review"].includes(mode) ? mode : "personal" };
  console.info(LOG, `이 대화의 링크를 자동으로 저장합니다 (${watch.mode}).`);
  watchForCompletedTurns();
}

async function initialize() {
  if (!shareContextAvailable()) return;
  // 배경은 탭을 열 때 감시를 건다 — 사람이 확인 카드를 보고 전송을 누르기까지
  // 걸리는 시간이라 폴링으로 기다리기엔 길다. 그래서 밀어 준다.
  chrome.runtime.onMessage.addListener((message) => {
    if (!contextInvalidated && message?.type === 'STUDYEZ_BANK_FILE_SAVED'
        && message.sha256 === lastBankFile?.responseFile?.sha256
        && message.filename === lastBankFile?.responseFile?.filename) {
      lastSavedBankFileHash = message.sha256;
    }
    if (!contextInvalidated && message?.type === "STUDYEZ_WATCH_READY" && typeof message.lectureId === "string") {
      startWatching(message.lectureId, message.mode, message.promptVersion || "");
    }
    return false;
  });

  // 이 스크립트가 듣기 전에 걸린 감시를 위한 경로. 새로고침·복원된 탭과, 기본
  // 링크 페이지에서 이어 물어 갈라져 나온 대화가 그렇다.
  for (let attempt = 0; attempt < 10 && !watch; attempt += 1) {
    const existing = await new Promise((resolve) => {
      if (!sendShareMessage({ type: "STUDYEZ_GET_WATCH" }, (response) => resolve(response?.ok ? response : null))) resolve(null);
    });
    if (contextInvalidated) return;
    if (existing) return startWatching(existing.lectureId, existing.mode, existing.promptVersion || "");
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

void initialize().catch((error) => {
  if (/extension context invalidated/i.test(error?.message || "")) invalidateShareContext();
  else console.warn(LOG, "링크 감시를 시작하지 못했습니다:", error);
});
