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
  function jsonVersion(version) {
    const match = /^(\d+)\.(\d+)$/.exec(version || '');
    return Boolean(match && (Number(match[1]) > 1 || Number(match[1]) === 1 && Number(match[2]) >= 80));
  }
  function filenameFor(target) { return `study-ez-${target.runId}-bank.${jsonVersion(target.promptVersion) ? 'json' : 'md'}`; }
  function isJson(raw) { return typeof raw === 'string' && raw.replace(/^\uFEFF/, '').trimStart().startsWith('{'); }
  function strictJson(raw) {
    const text = raw.replace(/^\uFEFF/, '');
    let value;
    try { value = JSON.parse(text); } catch { fail('올바른 순수 JSON 파일이 필요합니다.'); }
    // JSON.parse alone silently discards duplicate keys. Inspect the valid token stream too.
    const tokens = text.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^{}\[\]:,\s]+/g) || [];
    let at = 0;
    function walk(depth = 0) {
      if (depth > 200) fail('JSON 중첩이 너무 깊습니다.');
      const token = tokens[at++];
      if (token === '{') {
        const keys = new Set();
        if (tokens[at] === '}') { at++; return; }
        do {
          const key = JSON.parse(tokens[at++]);
          if (keys.has(key)) fail('JSON 객체에 중복 키가 있습니다: ' + key);
          keys.add(key); at++; walk(depth + 1);
        } while (tokens[at++] === ',');
      } else if (token === '[') {
        if (tokens[at] === ']') { at++; return; }
        do { walk(depth + 1); } while (tokens[at++] === ',');
      } else if (token && !token.startsWith('"') && !['true', 'false', 'null'].includes(token) && !Number.isFinite(Number(token))) {
        fail('JSON에 비유한 숫자를 사용할 수 없습니다.');
      }
    }
    walk();
    return value;
  }
  function metadata(raw) {
    if (isJson(raw)) return strictJson(raw);
    const header = /^<!-- STUDYEZ_BANK_FILE (\{[^\n]+\}) -->/.exec(raw.replace(/^\uFEFF/, ''));
    if (!header) fail('파일의 관리 정보가 없습니다.');
    return JSON.parse(header[1]);
  }
  function inspectJson(raw, target, filename) {
    if (typeof raw !== 'string' || raw.length < 200 || raw.length > MAX_CHARS) fail('JSON 파일의 길이가 올바르지 않습니다.');
    if (typeof filename !== 'string' || /[\\/\x00-\x1f]/.test(filename) || !filename.endsWith('.json') || !filename.includes(target.runId)) fail('선택한 강의 ID가 포함된 .json 파일을 사용하세요.');
    const doc = strictJson(raw);
    const object = (v, required, optional = []) => {
      if (!v || typeof v !== 'object' || Array.isArray(v) || required.some(k => !Object.hasOwn(v, k))
          || Object.keys(v).some(k => !required.includes(k) && !optional.includes(k))) fail('JSON 객체의 필수·허용 필드를 확인하세요.');
    };
    const text = v => { if (typeof v !== 'string' || !v.trim()) fail('비어 있지 않은 문자열이 필요합니다.'); };
    const strings = v => { if (!Array.isArray(v)) fail('문자열 배열이 필요합니다.'); v.forEach(text); };
    const refs = v => {
      if (!Array.isArray(v) || !v.length) fail('출처가 필요합니다.');
      v.forEach(r => { object(r, ['source_id','locator']); if (typeof r.source_id !== 'string' || !/^S[1-9]\d*$/.test(r.source_id)) fail('출처 ID를 확인하세요.'); text(r.locator); });
    };
    const equal = (a,b) => JSON.stringify(a) === JSON.stringify(b);
    const unique = a => new Set(a).size === a.length;
    object(doc, ['schema_version','subject','run_id','prompt_version','complete','question_count','question_ids','conflict_ids','questions','source_conflicts'], ['generation_id']);
    if (doc.schema_version !== 2 || doc.complete !== true || !jsonVersion(doc.prompt_version)) fail('JSON schema_version=2·complete=true·프롬프트 1.80 이상이 필요합니다.');
    text(doc.subject); text(doc.run_id);
    if (doc.subject !== target.subject || doc.run_id !== target.runId) fail('파일의 강의 ID·과목이 선택한 강의와 다릅니다.');
    if (target.promptVersion && doc.prompt_version !== target.promptVersion) fail('파일이 요청한 프롬프트 버전과 다릅니다.');
    if (Object.hasOwn(doc,'generation_id') && (typeof doc.generation_id !== 'string' || !/^[a-f0-9]{32}$/.test(doc.generation_id))) fail('generation_id를 확인하세요.');
    strings(doc.question_ids); strings(doc.conflict_ids);
    if (!Array.isArray(doc.questions) || !doc.questions.length || !Array.isArray(doc.source_conflicts)) fail('문항·충돌 배열이 필요합니다.');
    const conflicts = doc.source_conflicts.map(c => {
      object(c, ['conflict_id','description','source_refs','unresolved']);
      if (typeof c.conflict_id !== 'string' || !/^CF\d{3,}$/.test(c.conflict_id) || typeof c.unresolved !== 'boolean') fail('충돌 ID·unresolved를 확인하세요.');
      text(c.description); refs(c.source_refs); return c.conflict_id;
    });
    if (!equal(doc.conflict_ids,conflicts) || !unique(conflicts)) fail('충돌 ID 목록이 다르거나 중복됐습니다.');
    const used = new Set();
    const ids = doc.questions.map(q => {
      object(q, ['question_id','format','tier','importance','advanced','item_difficulty','retrieval_direction','question','source_refs','exam_rationale','evidence'], ['answers','options','mcq_mode','explanation','conflict_id']);
      text(q.question_id); text(q.question); text(q.exam_rationale); refs(q.source_refs);
      const importance = {'Must-Know':5,Core:5,Important:4,Optional:2};
      if (!['basic','list','cloze','ox','mcq','multi_select'].includes(q.format) || typeof q.tier !== 'string'
          || !Object.hasOwn(importance,q.tier) || q.importance !== importance[q.tier] || typeof q.advanced !== 'boolean'
          || !Number.isInteger(q.item_difficulty) || q.item_difficulty < 1 || q.item_difficulty > 5
          || !['direct','reverse','mechanism','discrimination','integration','sequence','trap'].includes(q.retrieval_direction)) fail('문항 형식·중요도·심화·난이도·방향을 확인하세요.');
      if (Object.hasOwn(q,'explanation')) text(q.explanation);
      if (Object.hasOwn(q,'conflict_id')) { if (!conflicts.includes(q.conflict_id)) fail('정의되지 않은 충돌 ID입니다.'); used.add(q.conflict_id); }
      const e = q.evidence;
      object(e, ['mode','slides','reference_pages','reason','jokbo']); text(e.reason);
      if (!Array.isArray(e.slides) || !(e.mode === 'single' && e.slides.length === 1 || e.mode === 'linked' && e.slides.length >= 2 || e.mode === 'unresolved' && !e.slides.length)) fail('근거 mode·핵심 지면 수를 확인하세요.');
      const pages = e.slides.map(s => { object(s,['page','evidence']); text(s.evidence); if (!Number.isSafeInteger(s.page) || s.page <= 0) fail('PDF 쪽 번호를 확인하세요.'); return s.page; });
      if (!Array.isArray(e.reference_pages) || e.reference_pages.some(p => !Number.isSafeInteger(p) || p <= 0)
          || !unique(pages) || !unique(e.reference_pages) || e.reference_pages.some(p => pages.includes(p)) || !Array.isArray(e.jokbo)) fail('근거·참고 쪽 번호·족보 배열을 확인하세요.');
      e.jokbo.forEach(j => { object(j,['year','number']); text(j.year); text(j.number); });
      if (q.format === 'cloze') {
        const blanks = [...q.question.matchAll(/(?<!\{)\{([^{}\r\n]+)\}(?!\})/g)];
        if (Object.hasOwn(q,'answers') || !blanks.length || blanks.some(m => !m[1].trim()) || /[{}]/.test(q.question.replace(/(?<!\{)\{[^{}\r\n]+\}(?!\})/g,''))) fail('cloze 빈칸·별도 정답을 확인하세요.');
      } else {
        strings(q.answers);
        if (!q.answers.length || q.format === 'basic' && q.answers.length !== 1) fail('정답 단위 수를 확인하세요.');
        if (q.format === 'ox' && (!(equal(q.answers,['O']) || equal(q.answers,['X'])) || !q.explanation)) fail('OX 정답·필수 해설을 확인하세요.');
      }
      if (['mcq','multi_select'].includes(q.format)) {
        if (!['recall_first','comparison'].includes(q.mcq_mode) || !Array.isArray(q.options) || q.options.length < 2) fail('객관식 보기·mcq_mode가 필요합니다.');
        const optionIds = q.options.map(o => { object(o,['id','text']); text(o.text); if (typeof o.id !== 'string' || !/^[A-Z]+$/.test(o.id)) fail('보기 ID를 확인하세요.'); return o.id; });
        if (!unique(optionIds) || !unique(q.answers) || q.answers.some(a => !optionIds.includes(a)) || q.format === 'mcq' && q.answers.length !== 1) fail('정답과 보기 ID가 일치하지 않습니다.');
      } else if (Object.hasOwn(q,'options') || Object.hasOwn(q,'mcq_mode')) fail('해당하지 않는 객관식 필드가 있습니다.');
      return q.question_id;
    });
    if (!Number.isInteger(doc.question_count) || doc.question_count !== ids.length || !equal(doc.question_ids,ids)
        || ids.some((id,i) => id !== `Q${String(i+1).padStart(3,'0')}`)) fail('전체 문항 수·ID 순서·누락·중복을 확인하세요.');
    if (used.size !== conflicts.length) fail('문항에서 사용하지 않은 출처 충돌이 있습니다.');
    return doc;
  }
  function inspect(raw, target, filename) {
    if (isJson(raw) || typeof filename === 'string' && filename.endsWith('.json')) return inspectJson(raw,target,filename);
    const info = inspectMarkdown(raw,target,filename);
    if (jsonVersion(info.prompt_version)) fail('프롬프트 1.80 이상은 순수 JSON 파일이 필요합니다.');
    return info;
  }
  function inspectMarkdown(raw, target, filename) {
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
    if (!file || file.size > MAX_BYTES) fail("8MB 이하의 문제은행 JSON 파일을 선택하세요. 기존 MD도 읽을 수 있습니다.");
    const bytes = await file.arrayBuffer();
    const raw = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes);
    return describe(raw, target, file.name);
  }
  root.StudyEZBankFile = { inspect, describe, readFile, lectureTarget, required, metadata, isJson, jsonVersion, filenameFor, MAX_BYTES };
})(globalThis);
