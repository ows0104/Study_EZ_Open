/* Runs briefly in the page's MAIN world after an authorized bank download request.
 * Capture the bytes produced by the real download control; never infer a file API.
 * This function must be self-contained because executeScript serializes it. */
async function captureBankDownload(target, expectedConversation, timeoutMs = 12000) {
  const conversation = /^\/(?:g\/[^/]+\/)?c\/([A-Za-z0-9_:-]+)/.exec(location.pathname)?.[1];
  if (!conversation || conversation !== expectedConversation
      || !/^[\w-]+$/.test(target.runId || "") || !target.subject
      || target.filename !== `study-ez-${target.runId}-bank.md`) {
    return { error: "파일을 받을 대화·강의가 일치하지 않습니다." };
  }
  const filename = target.filename;
  const labels = ["파일 다운로드", "Download file", "다운로드", "Download"];
  const visible = node => node && !node.disabled && node.getBoundingClientRect().width > 0;
  const preview = [...document.querySelectorAll('button[aria-label]')].find(button =>
    (button.getAttribute('aria-label') || '').startsWith(filename + ' ')
    || (button.getAttribute('aria-label') || '').endsWith(' ' + filename));
  let control = null;
  for (let parent = preview?.parentElement, depth = 0; parent && depth < 4; parent = parent.parentElement, depth++) {
    const buttons = [...parent.querySelectorAll('button')].filter(button =>
      labels.includes(button.getAttribute('aria-label') || '') && visible(button));
    if (buttons.length === 1) { control = buttons[0]; break; }
  }
  if (!control) {
    control = [...document.querySelectorAll('a[href]')].find(link => {
      const href = link.getAttribute('href') || '';
      try { return decodeURIComponent(href.split(/[?#]/)[0]).endsWith('/' + filename) && visible(link); }
      catch { return false; }
    });
  }
  if (!control) return { error: "이 강의의 실제 MD 다운로드 버튼이 아직 없습니다." };
  return new Promise(resolve => {
    const original = URL.createObjectURL;
    const anchorPrototype = typeof HTMLAnchorElement === 'function' ? HTMLAnchorElement.prototype : null;
    const originalClick = anchorPrototype?.click;
    let settled = false;
    const finish = value => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (URL.createObjectURL === capture) URL.createObjectURL = original;
      if (anchorPrototype?.click === captureClick) anchorPrototype.click = originalClick;
      resolve(value);
    };
    const receive = async blob => {
      if (!blob || typeof blob.arrayBuffer !== 'function' || blob.size < 200 || blob.size > 8_000_000) return;
      try {
        const raw = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(await blob.arrayBuffer());
        const header = /^<!-- STUDYEZ_BANK_FILE (\{[^\n]+\}) -->\r?\n/.exec(raw.replace(/^\uFEFF/, ''));
        if (!header) return;
        const info = JSON.parse(header[1]);
        if (info.run_id !== target.runId || info.subject !== target.subject
            || target.promptVersion && info.prompt_version !== target.promptVersion
            || !raw.trimEnd().endsWith('STUDYEZ_BANK_COMPLETE')) return;
        const current = /^\/(?:g\/[^/]+\/)?c\/([A-Za-z0-9_:-]+)/.exec(location.pathname)?.[1];
        if (current !== expectedConversation) { finish({error:'다운로드 중 대화가 변경됐습니다.'}); return; }
        finish({raw, filename});
      } catch {} // Ignore unrelated blobs; their contents never leave the page.
    };
    function capture(blob) {
      const url = Reflect.apply(original, URL, [blob]);
      void receive(blob);
      return url;
    }
    function captureClick(...args) {
      if ((this.href || '').startsWith('blob:')) {
        void fetch(this.href).then(response => response.blob()).then(receive).catch(() => {});
      }
      return Reflect.apply(originalClick, this, args);
    }
    const timer = setTimeout(() => finish({error:'실제 MD 다운로드 데이터를 기다리는 중입니다.'}), timeoutMs);
    URL.createObjectURL = capture;
    if (originalClick) anchorPrototype.click = captureClick;
    try {
      const href = control.getAttribute('href') || '';
      if (href.startsWith('blob:')) {
        void fetch(href).then(response => response.blob()).then(receive).catch(() => {});
      } else {
        control.click();
      }
    } catch (error) { finish({error:error.message}); }
  });
}
