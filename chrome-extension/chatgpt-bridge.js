// ChatGPT 새 대화에 작년 필기를 붙이고 프롬프트를 채운다.
//
// **전송은 누르지 않는다.** 무엇이 들어갔는지 사람이 보고 직접 보낸다 — 남의
// 계정으로 대화를 만드는 일이라 마지막 한 번은 사람의 손이어야 한다.

function escapeHtml(value) {
  return String(value).replace(
    /[&<>'"]/g,
    (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character],
  );
}

function createOverlay(payload) {
  const shared = payload.mode === "shared";
  const root = document.createElement("aside");
  root.id = "studyez-bridge";
  root.innerHTML = `
    <style>
      #studyez-bridge { position: fixed; right: 20px; bottom: 20px; z-index: 2147483647; width: min(360px, calc(100vw - 40px)); padding: 16px; border: 1px solid #e4e6ea; border-radius: 14px; color: #16181d; background: #fff; box-shadow: 0 18px 50px rgba(16, 18, 29, .22); font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", sans-serif; }
      #studyez-bridge h2 { margin: 0 0 5px; font-size: 15px; font-weight: 650; }
      #studyez-bridge p { margin: 0 0 10px; color: #878d97; font-size: 12px; }
      #studyez-bridge .studyez-disclosure { padding: 10px; border: 1px solid #dfe4f5; border-radius: 9px; color: #414754; background: #f5f7ff; }
      #studyez-bridge .studyez-consent { display: flex; align-items: flex-start; margin: 0 0 12px; gap: 8px; color: #30343b; font-size: 12px; cursor: pointer; }
      #studyez-bridge .studyez-consent input { width: 16px; height: 16px; margin: 1px 0 0; accent-color: #3e63dd; }
      #studyez-bridge a { color: #3155c6; }
      #studyez-bridge ul { max-height: 120px; margin: 0 0 12px; padding: 9px 9px 9px 26px; overflow: auto; border-radius: 9px; background: #f6f7f9; }
      #studyez-bridge li { margin: 3px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      #studyez-bridge .studyez-actions { display: flex; justify-content: flex-end; gap: 7px; }
      #studyez-bridge button { min-height: 34px; padding: 0 12px; border: 1px solid #e4e6ea; border-radius: 8px; color: #565b64; background: #fff; font: inherit; font-weight: 650; cursor: pointer; }
      #studyez-bridge button[data-action="confirm"] { border-color: #3e63dd; color: #fff; background: #3e63dd; }
      #studyez-bridge button:disabled { opacity: .55; cursor: not-allowed; }
      #studyez-bridge .studyez-status { min-height: 18px; margin-top: 9px; color: #3a5bc7; font-size: 11px; }
      #studyez-bridge .studyez-status.is-error { color: #9a3412; }
    </style>
    <h2>Study_EZ 예습 자료</h2>
    <p>ChatGPT에 넣을 필기와 프롬프트입니다. 전송은 직접 눌러야 합니다.</p>
    <p class="studyez-disclosure">
      동의하면 선택한 PDF와 프롬프트를 ChatGPT에 넣습니다. 확장은 대화 완성과 링크를 확인하려고 현재
      ChatGPT 로그인 토큰을 메모리에서 잠깐 사용하지만, 토큰을 저장하거나 StudyEZ로 보내지 않습니다.
      ${shared ? "이 모드는 링크를 가진 누구나 볼 수 있는 공개 공유 링크를 만들고 StudyEZ 강의에 저장합니다." : "이 모드는 내 계정에서만 열리는 대화 주소를 StudyEZ 강의에 저장합니다."}
      <a href="https://study-ez-open.pages.dev/privacy" target="_blank" rel="noreferrer">개인정보처리방침</a>
    </p>
    <ul>${payload.files
      .map((file) => `<li title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</li>`)
      .join("")}</ul>
    <label class="studyez-consent">
      <input type="checkbox" data-action="consent">
      <span>위의 데이터 처리와 ${shared ? "공개 공유 링크 생성" : "개인 대화 주소 저장"}에 동의합니다.</span>
    </label>
    <div class="studyez-actions">
      <button type="button" data-action="cancel">취소</button>
      <button type="button" data-action="confirm" disabled>동의하고 자료 ${payload.files.length}개 넣기</button>
    </div>
    <div class="studyez-status" role="status"></div>
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
function fetchFile(file, status) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    const port = chrome.runtime.connect({ name: "studyez-file-stream" });
    port.onMessage.addListener((message) => {
      if (message.fileId !== file.id) return;
      if (message.type === "FILE_START") status.textContent = `${file.filename} 받는 중…`;
      if (message.type === "FILE_CHUNK") chunks.push(base64ToBytes(message.chunk));
      if (message.type === "FILE_ERROR") {
        port.disconnect();
        reject(new Error(message.error));
      }
      if (message.type === "FILE_END") {
        port.disconnect();
        resolve(new File(chunks, file.filename, { type: "application/pdf" }));
      }
    });
    port.postMessage({ type: "DOWNLOAD_FILE", fileId: file.id, filename: file.filename, downloadUrl: file.downloadUrl });
  });
}

function visible(element) {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
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

async function findFileInput() {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const inputs = [...document.querySelectorAll('input[type="file"]')];
    const input =
      inputs.find((candidate) => !candidate.disabled && (candidate.accept || "").toLowerCase().includes("pdf")) ||
      inputs.find((candidate) => !candidate.disabled);
    if (input) return input;
    if (attempt === 4 || attempt === 10) revealFileInput();
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error("ChatGPT의 파일 첨부 입력창을 찾지 못했습니다. 화면이 바뀌었을 수 있습니다.");
}

async function attachFiles(files) {
  const input = await findFileInput();
  const transfer = new DataTransfer();
  files.forEach((file) => transfer.items.add(file));
  input.files = transfer.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

/** 입력창은 textarea일 때도 contenteditable(ProseMirror)일 때도 있다. */
function fillPrompt(prompt) {
  const textarea = [...document.querySelectorAll("textarea")].find(visible);
  if (textarea) {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    setter?.call(textarea, prompt);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    return;
  }
  const editor = [...document.querySelectorAll('[contenteditable="true"]')].find(visible);
  if (!editor) throw new Error("ChatGPT의 프롬프트 입력창을 찾지 못했습니다. 화면이 바뀌었을 수 있습니다.");
  editor.focus();
  document.execCommand("selectAll", false);
  document.execCommand("insertText", false, prompt);
  editor.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
}

function requestPayload() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "STUDYEZ_GET_PAYLOAD" }, (response) => {
      resolve(chrome.runtime.lastError || !response?.ok ? null : response.payload || null);
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

  const overlay = createOverlay(payload);
  const status = overlay.querySelector(".studyez-status");
  const confirm = overlay.querySelector('[data-action="confirm"]');
  const consent = overlay.querySelector('[data-action="consent"]');
  overlay.querySelector('[data-action="cancel"]').addEventListener("click", () => overlay.remove());
  consent.addEventListener("change", () => {
    confirm.disabled = !consent.checked;
  });

  confirm.addEventListener("click", async () => {
    confirm.disabled = true;
    consent.disabled = true;
    status.classList.remove("is-error");
    try {
      const files = [];
      for (const file of payload.files) files.push(await fetchFile(file, status));
      status.textContent = "자료를 첨부하고 프롬프트를 넣는 중…";
      await attachFiles(files);
      fillPrompt(payload.prompt);
      status.textContent = "넣었습니다. 확인한 뒤 전송 버튼을 눌러 주세요.";
      setTimeout(() => overlay.remove(), 5000);
    } catch (error) {
      status.classList.add("is-error");
      status.textContent = error instanceof Error ? error.message : String(error);
      consent.disabled = false;
      confirm.disabled = !consent.checked;
    }
  });
}

void initialize();
