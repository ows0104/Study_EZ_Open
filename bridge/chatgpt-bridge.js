// 선택한 AI 새 대화에 작년 필기를 붙이고 프롬프트를 채운다.
//
// 자동 첨부·전송에 동의한 모드만 실행한다. 첨부 준비를 확인할 수 없으면 멈추고,
// 전송 클릭은 한 번만 한다. 전송 여부가 불명확해도 자동 재시도하지 않는다.

function escapeHtml(value) {
  return String(value).replace(
    /[&<>'"]/g,
    (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character],
  );
}

function createOverlay(payload, remembered) {
  const automatic = payload.autoSend === true;
  const inputLabel = automatic ? "자동 첨부·전송" : "자료 첨부·프롬프트 입력";
  const shared = payload.mode === "shared";
  // Quiz Bank(관리자): 필기 PDF 와 족보 조각을 붙이고, 답이 끝나면 그 **본문**을 강의에 저장한다.
  const bank = payload.mode === "bank";
  const providerLabel = { chatgpt: "ChatGPT", gemini: "Gemini", claude: "Claude" }[payload.provider] || "AI";
  const modeLabel = bank ? "Quiz Bank 답 저장" : shared ? "공개 공유 링크" : "개인 대화 링크";
  const title = bank ? "Study EZ Quiz Bank" : payload.mode === "review" ? "Study EZ 복습 자료" : "Study EZ 예습 자료";
  const fileList = payload.files
    .map((file) => `<li title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</li>`)
    .join("");
  const disclosure = `
    <p class="studyez-disclosure">
      동의하면 선택한 자료 내용과 프롬프트를 ${providerLabel}에 ${automatic ? "첨부하고 자동 전송합니다" : "입력합니다. 전송 버튼은 직접 눌러 주세요"}.
      동의는 같은 서비스·모드·입력 방식별로 기억합니다. ×로 중지할 수 있습니다. 확장은 답변 완료 상태와 링크를
      확인합니다. ChatGPT 기본 링크·Quiz Bank 모드에서는 로그인 토큰을 메모리에서 잠깐 사용하지만, 토큰을
      저장하거나 Study EZ로 보내지 않습니다.
      ${bank ? "이 모드는 답변이 끝나면 그 답변 본문을 Study EZ 강의에 저장합니다. 공유 링크는 만들지 않습니다." : shared ? "이 모드는 링크를 가진 누구나 볼 수 있는 공개 공유 링크를 만들고 Study EZ 강의에 저장합니다." : "이 모드는 내 계정에서만 열리는 대화 주소를 Study EZ 강의에 저장합니다."}
      <a href="https://studyez.kr/privacy" target="_blank" rel="noreferrer">개인정보처리방침</a>
    </p>`;
  const root = document.createElement("aside");
  root.id = "studyez-bridge";
  if (remembered) root.className = "is-remembered";
  root.innerHTML = `
    <style>
      #studyez-bridge { position: fixed; right: 20px; bottom: 20px; z-index: 2147483647; box-sizing: border-box; width: min(360px, calc(100vw - 40px)); max-height: calc(100vh - 40px); padding: 16px; overflow: auto; border: 1px solid #e4e6ea; border-radius: 14px; color: #16181d; background: #fff; box-shadow: 0 18px 50px rgba(16, 18, 29, .22); font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", sans-serif; }
      #studyez-bridge.is-remembered { width: min(320px, calc(100vw - 40px)); padding: 14px; box-shadow: 0 10px 32px rgba(16, 18, 29, .14); }
      #studyez-bridge h2 { margin: 0 0 5px; padding-right: 26px; font-size: 15px; font-weight: 650; }
      #studyez-bridge p { margin: 0 0 10px; color: #878d97; font-size: 12px; }
      #studyez-bridge .studyez-disclosure { padding: 10px; border: 1px solid #dfe4f5; border-radius: 9px; color: #414754; background: #f5f7ff; }
      #studyez-bridge .studyez-consent { display: flex; align-items: flex-start; margin: 0 0 12px; gap: 8px; color: #30343b; font-size: 12px; cursor: pointer; }
      #studyez-bridge input[data-action="consent"] { all: revert !important; appearance: auto !important; -webkit-appearance: checkbox !important; display: inline-block !important; position: static !important; flex: 0 0 18px !important; width: 18px !important; height: 18px !important; margin: 1px 0 0 !important; opacity: 1 !important; accent-color: #3e63dd !important; cursor: pointer !important; }
      #studyez-bridge .studyez-consent-help { color: #3155c6; font-size: 12px; font-weight: 600; }
      #studyez-bridge .studyez-consent-state { margin: 7px 0 0; color: #878d97; font-size: 10px; font-weight: 400; }
      #studyez-bridge .studyez-remembered { margin: 0 0 12px; color: #30343b; font-size: 12px; }
      #studyez-bridge .studyez-remembered button { min-height: 0; padding: 0; border: 0; color: #3155c6; background: none; font: inherit; font-weight: 400; text-decoration: underline; cursor: pointer; }
      #studyez-bridge .studyez-file-line { margin: 0 0 10px; overflow: hidden; color: #30343b; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
      #studyez-bridge details { margin-top: 8px; color: #5d6470; font-size: 12px; }
      #studyez-bridge summary { display: list-item; width: max-content; max-width: 100%; color: #878d97; font-size: 11px; cursor: pointer; }
      #studyez-bridge details .studyez-disclosure { margin-top: 8px; }
      #studyez-bridge details ul { margin-bottom: 8px; }
      #studyez-bridge a { color: #3155c6; text-decoration: underline !important; text-underline-offset: 3px; }
      #studyez-bridge ul { max-height: 120px; margin: 0 0 12px; padding: 9px 9px 9px 26px; overflow: auto; border-radius: 9px; background: #f6f7f9; }
      #studyez-bridge li { margin: 3px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      #studyez-bridge .studyez-actions { display: flex; align-items: center; gap: 8px; }
      #studyez-bridge button { min-height: 34px; padding: 0 12px; border: 1px solid #e4e6ea; border-radius: 8px; color: #565b64; background: #fff; font: inherit; font-weight: 650; cursor: pointer; }
      #studyez-bridge button[data-action="confirm"] { flex: none; border-color: #3e63dd; color: #fff; background: #3e63dd; }
      #studyez-bridge button[data-action="cancel"] { position: absolute; top: 10px; right: 10px; width: 26px; min-height: 26px; height: 26px; padding: 0; border: 0; border-radius: 6px; color: #878d97; background: none; font-size: 18px; font-weight: 400; line-height: 1; }
      #studyez-bridge button[data-action="cancel"]:hover { color: #30343b; background: #f2f3f5; }
      #studyez-bridge button:disabled { opacity: .55; cursor: not-allowed; }
      #studyez-bridge .studyez-status { flex: 1; min-width: 0; color: #3a5bc7; font-size: 11px; }
      #studyez-bridge .studyez-status.is-error { color: #9a3412; }
    </style>
    <button type="button" data-action="cancel" aria-label="자동 진행 중지" title="자동 진행 중지">×</button>
    ${
      remembered
        ? `<h2>${title}</h2>
    <p class="studyez-file-line" title="${escapeHtml(payload.files.map((file) => file.filename).join(", "))}">자료 ${payload.files.length}개 · ${modeLabel} · ${escapeHtml(payload.files[0]?.filename || "자료")}</p>`
        : `<h2>${title}</h2>
    <p>${providerLabel} ${automatic ? "자동입력 · 전송까지 진행" : "수동입력 · 직접 전송"}에 사용할 자료와 프롬프트입니다.</p>
    ${disclosure}
    <ul>${fileList}</ul>`
    }
    ${remembered ? "" : `
    <label class="studyez-consent">
      <input type="checkbox" data-action="consent">
      <span>${inputLabel}과 ${bank ? "답변 본문 저장" : shared ? "공개 공유 링크 생성" : "개인 대화 주소 저장"}에 동의합니다.</span>
    </label>
    <p class="studyez-consent-help">체크박스를 선택한 뒤 아래 버튼을 눌러 주세요.</p>`}
    <div class="studyez-actions">
      <div class="studyez-status" role="status"></div>
      <button type="button" data-action="confirm"${remembered && automatic ? " hidden" : remembered ? "" : " disabled"}>${automatic ? "동의하고 자동 시작" : remembered ? "자료·프롬프트 넣기" : "동의하고 입력"}</button>
    </div>
    ${
      remembered
        ? `<p class="studyez-consent-state">동의 완료</p>
    <details>
      <summary>첨부 자료와 개인정보 처리 자세히</summary>
      ${disclosure}
      <ul>${fileList}</ul>
      <p class="studyez-remembered">이 모드에 이미 동의했습니다. <button type="button" data-action="revoke">동의 해제</button></p>
    </details>`
        : ""
    }
  `;
  document.body.append(root);
  return root;
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

/** 자료는 배경이 받아 조각으로 넘겨준다. 콘텐츠 스크립트는 R2에 직접 못 간다. */
function fetchFile(file, status, signal) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    const port = chrome.runtime.connect({ name: "studyez-file-stream" });
    let settled = false;
    const timer = setTimeout(() => finish(new Error("자료 다운로드 시간이 초과되었습니다. Study EZ에서 새 대화로 시작해 주세요.")), 120000);
    const abort = () => finish(new Error("자동 진행을 중지했습니다."));
    function finish(error, result) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      port.disconnect();
      if (error) reject(error);
      else resolve(result);
    }
    signal.addEventListener("abort", abort, { once: true });
    port.onDisconnect.addListener(() => finish(new Error("자료 다운로드 연결이 끊겼습니다. Study EZ에서 새 대화로 시작해 주세요.")));
    port.onMessage.addListener((message) => {
      if (settled) return;
      if (message.fileId !== file.id) return;
      if (message.type === "FILE_START") status.textContent = `${file.filename} 받는 중…`;
      if (message.type === "FILE_CHUNK") chunks.push(base64ToBytes(message.chunk));
      if (message.type === "FILE_ERROR") {
        finish(new Error(message.error));
      }
      if (message.type === "FILE_END") {
        // 족보 조각은 마크다운이다(Quiz Bank). 형식을 안 주면 PDF 로 붙는다.
        const type = file.contentType || (/\.md$/i.test(file.filename) ? "text/markdown" : "application/pdf");
        finish(null, new File(chunks, file.filename, { type }));
      }
    });
    if (signal.aborted) abort();
    else port.postMessage({ type: "DOWNLOAD_FILE", fileId: file.id, filename: file.filename, downloadUrl: file.downloadUrl });
  });
}

function visible(element) {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function requestGeminiFileCapture() {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: "STUDYEZ_PREPARE_GEMINI_FILE_INPUT" }, (response) => {
      const error = chrome.runtime.lastError?.message || response?.error;
      if (error || !response?.ok) reject(new Error(error || "Gemini 파일 입력을 준비하지 못했습니다."));
      else resolve();
    });
  });
}

async function prepareGeminiFileInput() {
  await requestGeminiFileCapture();
  const toolsButton = document.querySelector('button[aria-label="업로드 및 도구"]')
    || [...document.querySelectorAll("button")].find((button) => visible(button) && /(add files|upload and tools)/i.test(button.getAttribute("aria-label") || ""));
  if (!toolsButton) throw new Error("Gemini의 파일 추가 버튼을 찾지 못했습니다. 화면이 바뀌었을 수 있습니다.");
  toolsButton.click();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const uploadButton = document.querySelector('[data-test-id="local-images-files-uploader-button"]')
      || [...document.querySelectorAll('[role="menuitem"]')].find((item) => /(파일 업로드|upload files)/i.test(`${item.getAttribute("aria-label") || ""} ${item.textContent || ""}`));
    if (uploadButton) {
      uploadButton.click();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Gemini의 파일 업로드 메뉴를 찾지 못했습니다. 화면이 바뀌었을 수 있습니다.");
}

/** 첨부 입력이 메뉴 안에 숨어 있을 때 그 메뉴를 연다. */
function revealFileInput() {
  const pattern = /(upload|attach|file|첨부|업로드|파일)/i;
  const candidate = [...document.querySelectorAll('button, [role="button"], [role="menuitem"]')].find((button) => {
    const label = `${button.getAttribute("aria-label") || ""} ${button.getAttribute("title") || ""} ${button.textContent || ""}`;
    return visible(button) && !button.disabled && pattern.test(label);
  });
  candidate?.click();
}

async function findFileInput(provider) {
  if (provider === "gemini") await prepareGeminiFileInput();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const inputs = [...document.querySelectorAll('input[type="file"]')];
    const input =
      inputs.find((candidate) => !candidate.disabled && (candidate.accept || "").toLowerCase().includes("pdf")) ||
      inputs.find((candidate) => !candidate.disabled && !(candidate.accept || "").trim());
    if (input) return input;
    if (attempt === 4 || attempt === 10) revealFileInput();
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error("AI 서비스의 파일 첨부 입력창을 찾지 못했습니다. 화면이 바뀌었을 수 있습니다.");
}

async function attachFiles(files, provider, active) {
  const input = await findFileInput(provider);
  active();
  const transfer = new DataTransfer();
  files.forEach((file) => transfer.items.add(file));
  input.files = transfer.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

/** 입력창은 textarea일 때도 contenteditable(ProseMirror)일 때도 있다. */
function fillPrompt(prompt, editor) {
  if (editor.tagName === "TEXTAREA") {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    setter?.call(editor, prompt);
    editor.dispatchEvent(new Event("input", { bubbles: true }));
    return;
  }
  editor.focus();
  document.execCommand("selectAll", false);
  document.execCommand("insertText", false, prompt);
  editor.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const normalized = (value) => String(value || "").replace(/\r\n/g, "\n").replace(/\u00a0/g, " ").trim();

/** innerText는 <p> 사이에 CSS 문단 간격을 반영한 \n\n을 넣는다.
 * 입력한 줄바꿈은 블록 경계 하나당 \n 하나로 읽고, 빈 문단은 그대로 보존한다.
 * textContent만 쓰면 문단 경계가 사라져 서로 다른 프롬프트가 같아질 수 있다.
 */
function editorNodeText(node) {
  if (node.nodeType === 3) return node.nodeValue || "";
  if (node.nodeType !== 1) return "";
  if (node.tagName === "BR") return node.classList.contains("ProseMirror-trailingBreak") ? "" : "\n";
  const children = [...node.childNodes];
  if (children.length === 1 && children[0].nodeName === "BR") return "";
  const block = (child) => /^(P|DIV|LI|PRE|BLOCKQUOTE|H[1-6])$/.test(child.nodeName);
  return children.map((child, index) => {
    const separator = index > 0 && (block(child) || block(children[index - 1])) ? "\n" : "";
    return separator + editorNodeText(child);
  }).join("");
}

const editorText = (editor) => normalized(editor.value ?? editorNodeText(editor));

function promptUnchanged(provider, prompt) {
  // React/ProseMirror가 입력창 DOM을 교체할 수 있으므로 예전 요소를 붙잡지 않는다.
  const current = findEditor(provider);
  return Boolean(current && editorText(current) === normalized(prompt));
}

function findEditor(provider) {
  const selectors = {
    chatgpt: '#prompt-textarea, textarea[data-id="root"], [data-chatgpt-composer] [data-composer-markdown][contenteditable="true"]',
    gemini: 'rich-textarea [contenteditable="true"], textarea',
    claude: '[contenteditable="true"].ProseMirror, textarea',
  };
  const candidates = [...document.querySelectorAll(selectors[provider])].filter(visible);
  // 입력창이 모호하면 다른 검색창이나 대화에 쓰지 않는다.
  return candidates.length === 1 ? candidates[0] : null;
}

function sendButton(root, provider) {
  const known = {
    chatgpt: 'button[data-testid="send-button"]',
    gemini: 'button.send-button',
    claude: 'button[data-testid="send-button"]',
  };
  const candidates = [...root.querySelectorAll("button")].filter((button) => {
    if (!visible(button) || button.closest("#studyez-bridge")) return false;
    const label = `${button.getAttribute("aria-label") || button.getAttribute("title") || button.textContent || ""}`.trim();
    // Gemini 등은 생성 중에도 같은 버튼 클래스를 쓴다.
    if (/(stop|cancel|중지|취소)/i.test(label)) return false;
    return button.matches(known[provider]) || /^(send(?: message| prompt)?|메시지 (?:보내기|전송)|프롬프트 (?:보내기|전송)|보내기|전송|제출)(?:\s*\([^)]*\))?$/i.test(label);
  });
  return candidates.length === 1 ? candidates[0] : null;
}

function composerRoot(editor, provider) {
  // 업로드 상태와 파일명은 입력창 주변에서만 읽는다. 과거 대화나 확인 카드의
  // 파일명을 업로드 성공으로 오인하지 않도록 body까지 확장하지 않는다.
  const form = editor.closest("form");
  if (form) return form;
  let root = editor.parentElement;
  for (let depth = 0; root && root !== document.body && depth < 8; depth += 1, root = root.parentElement) {
    if (sendButton(root, provider)) return root;
  }
  return null;
}

function attachmentStatus(root, files) {
  const copy = root.cloneNode(true);
  copy.querySelectorAll('textarea, [contenteditable], #studyez-bridge').forEach((node) => node.remove());
  const labels = [copy.textContent, ...[...copy.querySelectorAll("[title], [aria-label]")]
    .flatMap((node) => [node.getAttribute("title"), node.getAttribute("aria-label")])].join("\n");
  const busy = [...root.querySelectorAll('[role="progressbar"], progress, [aria-busy="true"], .animate-spin, [data-state="uploading"]')].some(visible)
    || /(?:uploading|processing file|업로드 중|업로드하는 중|파일 처리 중)/i.test(labels);
  const failed = /(?:upload failed|failed to upload|error uploading|unsupported file|file too large|업로드 실패|업로드할 수 없|지원하지 않는 파일|파일이 너무)/i.test(labels);
  return { ready: files.every((file) => labels.includes(file.filename)) && !busy, failed };
}

/** 준비 상태가 안정적으로 유지될 때만 클릭한다. 타임아웃/불명확한 전송은 재시도하지 않는다. */
async function autoSend(payload, status, active, dependencies = {}) {
  const sleep = dependencies.sleep || pause;
  const now = dependencies.now || Date.now;
  const getEditor = dependencies.findEditor || findEditor;
  const getRoot = dependencies.composerRoot || composerRoot;
  const getButton = dependencies.sendButton || sendButton;
  const getAttachments = dependencies.attachmentStatus || attachmentStatus;
  let readySince = null;
  const deadline = now() + 120000;
  while (now() < deadline) {
    active();
    const editor = getEditor(payload.provider);
    if (!editor || editorText(editor) !== normalized(payload.prompt)) {
      throw new Error("입력 내용이 바뀌었거나 이미 전송되었습니다. 중복 전송을 막기 위해 자동 진행을 멈췄습니다.");
    }
    const root = getRoot(editor, payload.provider);
    const attachment = root && getAttachments(root, payload.files);
    if (attachment?.failed) throw new Error("파일 업로드에 실패했습니다. AI 화면에서 첨부 상태를 확인해 주세요.");
    const button = root && getButton(root, payload.provider);
    if (attachment?.ready && button && !button.disabled && button.getAttribute("aria-disabled") !== "true") {
      if (readySince === null) readySince = now();
      if (now() - readySince >= 1500) {
        active();
        button.click(); // 이 실행에서 유일한 전송 시도. 이후에는 확인만 한다.
        status.textContent = "전송 확인 중…";
        const confirmationDeadline = now() + 15000;
        while (now() < confirmationDeadline) {
          await sleep(250);
          // 전송 후에는 URL이 새 대화 주소로 바뀌는 것이 정상이다.
          const current = getEditor(payload.provider);
          if (current && !editorText(current)) return;
        }
        throw new Error("전송 버튼을 눌렀지만 접수 여부를 확인하지 못했습니다. 자동으로 다시 보내지 않습니다. AI 화면을 확인해 주세요.");
      }
    } else readySince = null;
    status.textContent = "파일 업로드 완료와 전송 준비를 확인하는 중… (×로 중지)";
    await sleep(250);
  }
  throw new Error("2분 안에 모든 파일의 업로드 완료를 확인하지 못했습니다. 첨부 상태를 확인한 뒤 직접 전송해 주세요.");
}

function requestPayload() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "STUDYEZ_GET_PAYLOAD" }, (response) => {
      resolve(chrome.runtime.lastError || !response?.ok ? null : response.payload || null);
    });
  });
}

/**
 * 동의는 모드별로 한 번만 받는다. 두 모드가 내놓는 것이 다르기 때문이다 —
 * `shared`는 링크를 가진 누구나 볼 수 있는 공개 링크를 만든다. 개인 모드에
 * 동의한 것으로 그것까지 동의한 셈 칠 수 없다.
 */
const CONSENT_KEY = "studyez-consent:";
// 이전 동의는 수동 전송용이다. 자동 전송에 대한 동의는 별도로 받는다.
const AUTO_CONSENT_VERSION = "auto-v1:";

function consentScopeFor(payload) {
  return `${payload.autoSend === true ? AUTO_CONSENT_VERSION : "manual-v1:"}${payload.provider}:${payload.mode}`;
}

async function finishInput(payload, status, active, send = autoSend) {
  if (payload.autoSend === true) {
    await send(payload, status, active);
    status.textContent = "전송했습니다. 답변이 끝나면 결과를 Study EZ에 저장합니다.";
  } else {
    status.textContent = "자료와 프롬프트를 넣었습니다. 확인·수정한 뒤 직접 전송해 주세요.";
  }
}

function readConsent(mode) {
  return new Promise((resolve) => {
    chrome.storage.local.get(`${CONSENT_KEY}${mode}`, (stored) => {
      resolve(!chrome.runtime.lastError && stored?.[`${CONSENT_KEY}${mode}`] === true);
    });
  });
}

async function initialize() {
  // 새 탭이 뜨는 것과 배경이 자료를 넣어 두는 것에 순서 보장이 없다. 잠깐 기다린다.
  let payload = null;
  for (let attempt = 0; attempt < 40 && !payload; attempt += 1) {
    payload = await requestPayload();
    if (!payload) await new Promise((resolve) => setTimeout(resolve, 250));
  }
  if (!payload) return;

  const mode = ["shared", "bank", "review"].includes(payload.mode) ? payload.mode : "personal";
  const provider = ["chatgpt", "gemini", "claude"].includes(payload.provider) ? payload.provider : "chatgpt";
  payload.provider = provider;
  payload.mode = mode;
  const automatic = payload.autoSend === true;
  const consentScope = consentScopeFor(payload);
  const consentKey = `${CONSENT_KEY}${consentScope}`;

  function mount(remembered) {
    const overlay = createOverlay(payload, remembered);
    const status = overlay.querySelector(".studyez-status");
    const confirm = overlay.querySelector('[data-action="confirm"]');
    const consent = overlay.querySelector('[data-action="consent"]');
    let cancelled = false;
    let started = false;
    const downloads = new AbortController();
    const startUrl = location.href;
    const active = () => {
      if (cancelled || !overlay.isConnected) throw new Error("자동 진행을 중지했습니다.");
      if (location.href !== startUrl) throw new Error("대화 화면이 바뀌어 자동 진행을 중지했습니다.");
    };
    overlay.querySelector('[data-action="cancel"]').addEventListener("click", () => {
      cancelled = true;
      downloads.abort();
      overlay.remove();
    });
    consent?.addEventListener("change", () => {
      confirm.disabled = !consent.checked;
    });
    // 기억한 동의를 되돌릴 자리. 이것이 없으면 확장 저장소를 통째로 지우는 수밖에 없다.
    overlay.querySelector('[data-action="revoke"]')?.addEventListener("click", async () => {
      cancelled = true;
      downloads.abort();
      try {
        await chrome.storage.local.remove(consentKey);
      } catch {
        status.classList.add("is-error");
        status.textContent = "자동 진행은 중지했지만 동의 해제를 저장하지 못했습니다. 동의 해제를 다시 눌러 주세요.";
        return;
      }
      status.textContent = "자동 진행을 중지하고 동의를 해제했습니다. 다시 실행하려면 Study EZ에서 새 대화로 시작해 주세요.";
      if (consent) consent.checked = false;
      confirm.hidden = true;
      overlay.querySelector('[data-action="revoke"]').disabled = true;
    });

    async function start() {
      if (started || (!remembered && !consent?.checked)) return;
      started = true;
      confirm.disabled = true;
      // 동의는 누른 그 순간에 남긴다. 첨부가 실패해도 사람이 동의한 것은 사실이다.
      // 못 남기는 것은 다음에 한 번 더 묻는다는 뜻일 뿐이라 전송을 막지 않는다.
      if (!remembered) await chrome.storage.local.set({ [consentKey]: true }).catch(() => {});
      if (consent) consent.disabled = true;
      status.classList.remove("is-error");
      try {
        // 기억된 동의로 시작해도 취소/동의 해제를 누를 시간을 준다.
        if (remembered && automatic) {
          status.textContent = "3초 후 자동으로 첨부·전송합니다. (×로 중지)";
          await pause(3000);
        }
        active();
        const files = [];
        for (const file of payload.files) {
          files.push(await fetchFile(file, status, downloads.signal));
          active();
        }
        let editor = null;
        for (let attempt = 0; attempt < 60 && !editor; attempt += 1) {
          active();
          editor = findEditor(provider);
          if (!editor) await pause(500);
        }
        if (!editor) throw new Error("입력창을 찾지 못했습니다. AI 서비스 로그인과 화면을 확인해 주세요.");
        if (editorText(editor)) throw new Error("입력창에 작성 중인 내용이 있어 자동 진행을 멈췄습니다. 새 대화로 다시 시작해 주세요.");
        status.textContent = "자료를 첨부하고 프롬프트를 넣는 중…";
        // 먼저 입력한다. 파일 입력을 찾는 동안 사용자가 전송/이동했으면 덮어쓰지 않는다.
        fillPrompt(payload.prompt, editor);
        active();
        await attachFiles(files, provider, () => {
          active();
          if (!promptUnchanged(provider, payload.prompt)) {
            throw new Error("입력 내용이 바뀌어 자동 첨부·전송을 중지했습니다.");
          }
        });
        active();
        confirm.hidden = true;
        await finishInput(payload, status, active);
        setTimeout(() => overlay.remove(), 5000);
      } catch (error) {
        if (cancelled) return;
        status.classList.add("is-error");
        status.textContent = error instanceof Error ? error.message : String(error);
        // 일부 첨부/전송이 성공했을 수 있으므로 같은 요청에 재시도 버튼을 주지 않는다.
        confirm.hidden = true;
      }
    }
    confirm.addEventListener("click", () => void start());
    if (remembered && automatic) void start();
  }

  mount(await readConsent(consentScope));
}

void initialize();
