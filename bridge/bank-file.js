/* Shared file-transport validation. This checks completeness, not medical correctness. */
(function (root) {
  "use strict";
  const MAX_BYTES = 8_000_000;
  const MAX_CHARS = 2_000_000;
  const MARK = "STUDYEZ_BANK_COMPLETE";
  const fail = message => { throw new Error(message); };
  function required(target) {
    const version = /^(\d+)\.(\d+)$/.exec(target?.promptVersion || "");
    if (!version) return false;
    const [major, minor] = version.slice(1).map(Number);
    return major > 1 || (major === 1 && minor >= 78)
      || (major === 1 && minor >= 76 && target.subject === "약리학"
        && ["261006_02", "261006_03"].includes(target.runId));
  }
  function lectureTarget(lectureId, promptVersion) {
    const match = /^studyez:bank:(v?1\.\d+(?:\.\d+)?):([^/]+\/[^/]+)$/.exec(lectureId || "");
    const [subject, runId] = (match ? match[2] : lectureId || "").split("/");
    return { subject, runId, promptVersion: promptVersion || match?.[1] || undefined };
  }
  function inspect(raw, target, filename) {
    if (typeof raw !== "string" || raw.length < 200 || raw.length > MAX_CHARS) fail("문제은행 파일의 길이가 올바르지 않습니다.");
    if (typeof filename !== "string" || /[\\/\x00-\x1f]/.test(filename) || !filename.endsWith(".md") || !filename.includes(target.runId)) fail("선택한 강의 ID가 포함된 .md 파일을 사용하세요.");
    const text = raw.replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
    const header = /^<!-- STUDYEZ_BANK_FILE (\{[^\n]+\}) -->\n/.exec(text);
    if (!header) fail("파일 첫 줄의 STUDYEZ_BANK_FILE 정보를 확인하세요.");
    let info;
    try { info = JSON.parse(header[1]); } catch { fail("문제은행 파일 정보가 올바른 JSON이 아닙니다."); }
    if (info.schema_version !== 1 || info.run_id !== target.runId || info.subject !== target.subject) fail("파일의 강의 ID·과목이 선택한 강의와 다릅니다.");
    if (!/^\d+\.\d+$/.test(info.prompt_version || "")) fail("파일의 프롬프트 버전이 없습니다.");
    if (target.promptVersion && info.prompt_version !== target.promptVersion) fail("파일이 요청한 프롬프트 버전과 다릅니다.");
    if (!text.trimEnd().endsWith(MARK) || (text.match(/^STUDYEZ_BANK_COMPLETE[ \t]*$/gm) || []).length !== 1) fail("파일 끝의 완료 표식이 없거나 중복됐습니다.");
    const body = text.slice(header[0].length).trimEnd().slice(0, -MARK.length);
    const headings = [...body.matchAll(/^### (Q\d+|CF\d+)(?:[ \t]*\|([^\n]+))?[ \t]*$/gm)];
    const ids = headings.filter(m => m[1].startsWith("Q")).map(m => m[1]);
    const conflicts = headings.filter(m => m[1].startsWith("CF")).map(m => m[1]);
    if (!Number.isInteger(info.question_count) || !ids.length || info.question_count !== ids.length
        || JSON.stringify(info.question_ids) !== JSON.stringify(ids) || new Set(ids).size !== ids.length
        || ids.some((id, i) => id !== `Q${String(i + 1).padStart(3, "0")}`)) fail("전체 문항 수·ID 목록이 실제 파일과 다르거나 문항이 누락·중복됐습니다.");
    if (JSON.stringify(info.conflict_ids) !== JSON.stringify(conflicts) || new Set(conflicts).size !== conflicts.length) fail("출처 충돌 ID 목록이 실제 파일과 다릅니다.");
    const usedConflicts = new Set();
    const fieldsOf = block => {
      const matches = [...block.matchAll(/^(문제|정답|출처|출제근거|근거|심화|해설|충돌|보기|왼쪽|오른쪽|항목):[ \t]*(.*)$/gm)];
      const fields = {};
      matches.forEach((m, i) => {
        if (Object.hasOwn(fields, m[1])) fail(`중복 필드: ${m[1]}`);
        fields[m[1]] = block.slice(m.index + m[1].length + 1, matches[i + 1]?.index ?? block.length).trim();
      });
      return fields;
    };
    const parse = value => { try { return JSON.parse((value || "").replace(/^`(.*)`$/s, "$1")); } catch { fail("파일의 정답·해설·근거 JSON이 올바르지 않습니다."); } };
    const entries = value => {
      const rows = [...(value || "").matchAll(/^\s*([A-Z]+|\d+)\.\s+(.+)$/gm)].map(m => m[1]);
      if (!rows.length || new Set(rows).size !== rows.length) fail("보기 항목이 없거나 ID가 중복됐습니다.");
      return rows;
    };
    headings.forEach((h, i) => {
      if (!h[1].startsWith("Q")) return;
      const f = fieldsOf(body.slice(h.index + h[0].length, headings[i + 1]?.index ?? body.length));
      const format = (h[2] || "").split("|")[0].trim();
      if (!["basic", "list", "ox", "cloze", "mcq", "multi_select", "matching", "sequence"].includes(format)) fail(`${h[1]}의 문항 형식이 없습니다.`);
      if (!["문제", "출처", "출제근거", "근거"].every(key => f[key]) || !["true", "false"].includes(f["심화"])) fail(`${h[1]}의 필수 필드가 빠졌습니다.`);
      const evidence = parse(f["근거"]);
      if (!evidence || typeof evidence !== "object" || Array.isArray(evidence)) fail(`${h[1]}의 근거 객체가 없습니다.`);
      if (f["해설"] && typeof parse(f["해설"]) !== "string") fail("해설은 JSON 문자열이어야 합니다.");
      if (f["충돌"]) { if (!conflicts.includes(f["충돌"])) fail("정의되지 않은 충돌 ID를 참조했습니다."); usedConflicts.add(f["충돌"]); }
      if (format === "cloze") {
        if (f["정답"] || !/(?<!\{)\{[^{}\n]+\}(?!\})/.test(f["문제"])) fail(`${h[1]}의 빈칸 또는 정답 형식을 확인하세요.`);
        return;
      }
      const answers = parse(f["정답"]);
      if (!Array.isArray(answers) || !answers.length || answers.some(a => typeof a !== "string" || !a.trim())) fail(`${h[1]}의 정답 배열이 없습니다.`);
      if (format === "basic" && answers.length !== 1) fail("단답형의 정답 단위를 확인하세요.");
      if (format === "ox" && (answers.length !== 1 || !["O", "X"].includes(answers[0]) || !f["해설"])) fail("OX 정답과 해설을 확인하세요.");
      if (["mcq", "multi_select", "sequence"].includes(format)) {
        const options = entries(f[format === "sequence" ? "항목" : "보기"]);
        if (new Set(answers).size !== answers.length || answers.some(id => !options.includes(id))
            || (format === "mcq" && answers.length !== 1) || (format === "sequence" && answers.length !== options.length)) fail(`${h[1]}의 정답이 실제 보기·순서 항목과 맞지 않습니다.`);
      }
      if (format === "matching") {
        const left = entries(f["왼쪽"]), right = entries(f["오른쪽"]);
        const pairs = answers.map(a => /^(\d+)-([A-Z]+)$/.exec(a));
        if (pairs.some(p => !p || !left.includes(p[1]) || !right.includes(p[2])) || answers.length !== left.length
            || new Set(pairs.map(p => p[1])).size !== left.length) fail(`${h[1]}의 정답 짝이 실제 항목과 맞지 않습니다.`);
      }
    });
    if (usedConflicts.size !== conflicts.length) fail("문항에서 사용하지 않은 출처 충돌 기록이 있습니다.");
    return info;
  }
  async function describe(raw, target, filename) {
    const info = inspect(raw, target, filename);
    const bytes = new TextEncoder().encode(raw);
    if (bytes.byteLength > MAX_BYTES) fail("문제은행 파일이 너무 큽니다.");
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return { raw, info, responseFile: { filename, byteLength: bytes.byteLength,
      sha256: [...new Uint8Array(digest)].map(v => v.toString(16).padStart(2, "0")).join("") } };
  }
  async function readFile(file, target) {
    if (!file || file.size > MAX_BYTES) fail("8MB 이하의 .md 파일을 선택하세요.");
    const bytes = await file.arrayBuffer();
    const raw = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes);
    return describe(raw, target, file.name);
  }
  root.StudyEZBankFile = { inspect, describe, readFile, lectureTarget, required, MAX_BYTES };
})(globalThis);
