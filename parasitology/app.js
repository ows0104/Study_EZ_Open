/* 기생충학 땡시 연습.
 *
 * **문항 조립은 여기서 한다.** 서버가 넘기는 것은 완성된 후보 문항 전체이고,
 * 어떤 40문항을 뽑을지(가중 표집·중복 회피·순서)는 브라우저가 정한다. 시드를
 * 바꿀 때마다 왕복이 붙지 않게 하려는 것이다.
 *
 * 서버가 하는 일은 셋이다 — 로그인 확인, 사진 서명, 기록·신고 보관.
 */

/* ══════════ 유틸 ══════════ */
function rng(seed){                 // 시드를 주면 같은 세트가 나온다
  let s = seed >>> 0 || 1;
  return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296;
}
const $ = id => document.getElementById(id);
const KEYS = '①②③④⑤';
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c]));

/* ══════════ 상태 ══════════ */
let S = { qs:[], i:0, answers:[], mode:'exam', limit:30, timer:null, left:0, rand:null,
          imgs:[], imgUrl:{}, opts:[], timedFor:-1 };
let QUIZ_META = null, QUIZ_DB = [];
let ME = null;                      // /api/me. 관리자 화면을 그릴지 정한다
let WRONG = new Set();              // 오답노트. 서버가 참, 없으면 localStorage
let RECORDS = [];
let MY_REPORTS = {};                // question_id → 내가 낸 신고

/* 로그인 없이 도는 갈래. **localhost에서만이다** — `config.js`의 설명을 보라. */
const OFFLINE = !CONFIG.apiBase && ['localhost','127.0.0.1',''].includes(location.hostname);
/* 그때 문항 DB와 사진을 찾을 자리. 생성물은 배포 폴더 밖(`build/`)에 있으므로
   개발 서버는 **저장소 루트**를 열어야 한다(`.claude/launch.json`). */
const OFFLINE_ROOT = '../build/';
/* 이 화면이 다루는 과목. 서버의 R2 키와 사이트 경로가 같은 이름을 쓴다.
   해부학 넷은 `gate.js`가 같은 것을 들고 있다. */
const SUBJECT = 'parasitology';
/* 서버는 붙이되 Supabase는 건너뛰는 갈래. 서버가 local-test 모드일 때만 통한다. */
const LOCAL_TEST = (CONFIG.localTestToken || '').trim();

/* ══════════ 서버 ══════════ */
/* 토큰·갱신·401 처리는 `gate.js`가 든다. 다섯 과목이 같은 규칙을 써야 해서
   여기 따로 두지 않는다. */
const api = (path, init) => GATE.api(path, init);

/** 세트가 쓰는 사진의 서명 URL을 받아 둔다. */
async function signImages(names){
  if (OFFLINE){
    names.forEach(n => { S.imgUrl[n] = OFFLINE_ROOT + 'images/' + n; });
    return;
  }
  await GATE.prefetch(names);
  names.forEach(n => { S.imgUrl[n] = GATE.image(n); });
}

/* ══════════ 고른 범위 ══════════ */
/* 화면 셋(분류군·표본·묻는 방식)이 정하는 것은 결국 "이 문항을 쓸까"
   하나뿐이다. 그 판단을 한 군데 두고, 세트를 만들 때도 몇 개인지 셀 때도
   같은 것을 부른다 — 두 벌이면 화면에 뜬 수와 실제로 나오는 세트가 갈린다. */
function filters(){
  return { groups: chosen($('f-group')), sptypes: chosen($('f-sptype')),
           types: chosen($('f-qtype')) };
}
function inScope(q, f){
  return (!f.groups.length  || f.groups.includes(q.group))
      && (!f.sptypes.length || f.sptypes.includes(q.specimen_type))
      && (!f.types.length   || f.types.includes(q.qtype));
}
/** 한 세트에 담을 수 있는 최대 문항 수. 같은 표본은 한 판에 두 번 안 나오므로
 *  문항 수가 아니라 **표본 수**가 천장이다. */
function capacity(pool){ return new Set(pool.map(q => q.specimen_id)).size; }

/* ══════════ 세트 만들기 ══════════ */
function weightedPick(pool, rand){
  const total = pool.reduce((a,q) => a + (q.weight || 1), 0);
  let r = rand() * total;
  for (const q of pool){ r -= (q.weight || 1); if (r <= 0) return q; }
  return pool[pool.length - 1];
}

function buildSet(n, f, rand){
  const DB = QUIZ_DB.filter(q => inScope(q, f));
  if (!DB.length) return [];

  /* 비율은 meta가 준 것을 쓰되 **고른 범위 안에서 다시 정규화한다.** 흡충만
     골랐는데 선충 몫 29%를 그대로 두면 그 자리가 빈 채 남아 40문항을 시켜도
     서른 몇 개만 나온다. 비율표에 없는 값(범위를 좁히면 나온다)은 그 범위에서
     실제로 차지하는 비중으로 대신한다. */
  const spread = (mix, field) => {
    const keys = [...new Set(DB.map(q => q[field]))].filter(Boolean);
    const w = {};
    keys.forEach(k => { w[k] = mix[k] != null ? mix[k]
      : DB.filter(q => q[field] === k).length / DB.length; });
    const sum = keys.reduce((a,k) => a + w[k], 0) || 1;
    const out = {};
    keys.forEach(k => { out[k] = Math.max(1, Math.round(w[k] / sum * n)); });
    return out;
  };
  const baseQ = spread(QUIZ_META.qtype_mix, 'qtype');
  const wantQ = { ...baseQ };
  const wantG = spread(QUIZ_META.group_mix, 'group');

  /* 바닥난 유형. **한 번 비면 다시 안 찬다** — 뽑을수록 `usedSpec`이 늘어날
     뿐이라서다. 되채울 때 이것들을 살려내면 빈 유형을 붙잡고 도는 바퀴가
     된다. '특징 구조물'은 indicator의 예비 통이라 따로 뽑지 않는다. */
  const dead = new Set();
  if (baseQ['indicator']) dead.add('특징 구조물');

  const usedSpec = new Set(), usedSp = {}, out = [];
  const order = Object.keys(wantQ).sort((a,b) => wantQ[b]-wantQ[a]);
  let guard = 0;
  while (out.length < n && guard++ < n*80){
    const qt = order.find(k => wantQ[k] > 0 && !dead.has(k));
    if (!qt){
      const live = order.filter(k => !dead.has(k));
      if (!live.length) break;
      live.forEach(k => { wantQ[k] = baseQ[k]; });
      continue;
    }
    const pick = (loose) => DB.filter(q =>
      (q.qtype === qt || (loose && qt === 'indicator' && q.qtype === '특징 구조물'))
      && !usedSpec.has(q.specimen_id)
      && (usedSp[q.species_id]||0) < 2
      && (loose || (wantG[q.group]||0) > 0));
    let pool = pick(false);
    if (!pool.length) pool = pick(true);
    if (!pool.length){ dead.add(qt); continue; }
    const q = weightedPick(pool, rand);
    out.push(q);
    usedSpec.add(q.specimen_id);
    usedSp[q.species_id] = (usedSp[q.species_id]||0) + 1;
    wantQ[qt]--; wantG[q.group] = (wantG[q.group]||0) - 1;
  }
  // 족보를 보면 충란은 앞쪽에 몰리지만(5개년 예외 없음)
  // 분류군 순으로 정렬되지는 않는다(8개년 전부 섞임). 그 형태를 따른다.
  const shuf = a => { for (let i=a.length-1;i>0;i--){ const j=Math.floor(rand()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; } return a; };
  if ($('order-input').value === 'random') return shuf(out);
  return shuf(out.filter(q => q.specimen_type === '충란'))
    .concat(shuf(out.filter(q => q.specimen_type !== '충란')));
}

/* ══════════ 시작 화면 ══════════ */
function renderRecords(){
  $('records').innerHTML = RECORDS.length
    ? RECORDS.slice(0,8).map(r => {
        const when = r.at
          ? new Date(r.at).toLocaleString('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})
          : r.date;
        const mode = r.mode === 'study' ? '공부' : (r.mode === 'exam' ? '땡시' : r.mode);
        return `<div>${esc(when)} · ${esc(mode)} · ${r.score}/${r.total} (${Math.round(r.score/r.total*100)}%)</div>`;
      }).join('')
    : '아직 기록이 없습니다.';
}

function renderWrongButton(){
  // 문항 id는 내용에서 뽑으므로, 데이터가 바뀌어 사라진 문항의 id는 여기서 버린다.
  // **서버에서 지우지는 않는다** — 서버는 문항 DB의 내용을 모른다.
  const live = new Set(QUIZ_DB.map(q => q.id));
  const n = [...WRONG].filter(id => live.has(id)).length;
  $('wrong-btn').textContent = n ? `오답만 다시 풀기 (${n}문항)` : '오답만 다시 풀기';
  $('wrong-btn').disabled = !n;
}

/* 화면에 쓰는 이름. 데이터의 값은 그대로 두고 보이는 글자만 바꾼다 —
   'gross'와 'indicator'는 한글 화면에 그대로 두기에는 낯설다. */
const SPTYPE_KO = { gross:'육안 표본', '혈액도말':'혈액도말' };
const QTYPE_KO  = { indicator:'지시 구조물' };
const ko = (map, v) => map[v] || v;

/** 칩 한 줄. 맨 앞의 '전체'가 켜져 있으면 그 줄은 아무것도 안 거른다. */
function chipRow(el, values, label){
  el.innerHTML =
    `<label class="chip on"><input type="checkbox" data-all checked> 전체</label>` +
    values.map(v =>
      `<label class="chip"><input type="checkbox" value="${esc(v)}"> ${esc(label(v))}</label>`).join('');
  const all = el.querySelector('[data-all]');
  const rest = [...el.querySelectorAll('input:not([data-all])')];
  const paint = () => {
    const any = rest.some(i => i.checked);
    all.checked = !any;                       // 아무것도 안 고르면 곧 '전체'다
    all.closest('.chip').classList.toggle('on', !any);
    rest.forEach(i => i.closest('.chip').classList.toggle('on', i.checked));
  };
  el.addEventListener('change', e => {
    if (e.target === all) rest.forEach(i => { i.checked = false; });
    paint();
    renderScope();
  });
  paint();
}
function chosen(el){
  return [...el.querySelectorAll('input:not([data-all]):checked')].map(i => i.value);
}

/** 지금 고른 범위가 몇 문항인지. **시작을 누르기 전에** 알려 준다 —
 *  좁히다 보면 40문항이 안 나오는 조합이 생기고, 눌러 보고 아는 것은 늦다. */
function renderScope(){
  const pool = QUIZ_DB.filter(q => inScope(q, filters()));
  const cap = capacity(pool), want = +$('n-input').value;
  const el = $('scope');
  if (!pool.length){
    el.className = 'scope thin';
    el.innerHTML = '<b>이 조합에는 문항이 없습니다.</b> 하나쯤 되돌려 주세요.';
    return;
  }
  el.className = 'scope' + (cap < want ? ' thin' : '');
  el.innerHTML = `고른 범위 <b>${pool.length.toLocaleString('ko-KR')}</b>문항 · 표본 <b>${cap}</b>건`
    + (cap < want
        ? ` — 같은 표본은 한 판에 한 번만 나오므로 <b>${cap}문항</b>까지입니다.`
        : '');
}

function initStart(){
  const c = QUIZ_META.counts;
  $('dbinfo').textContent =
    `문항 ${c.questions}개 · 표본 ${c.specimens}건 · ${c.species}종 · 사진 ${c.images}장`;

  /* 값은 문항 DB에서 뽑고, 늘어놓는 차례는 meta가 정한 것을 따른다. meta에
     없는 값이 나오면 뒤에 붙인다 — 데이터가 늘었을 때 조용히 사라지느니
     낯선 자리에라도 보이는 편이 낫다. */
  const uniq = (field, order) => {
    const seen = [...new Set(QUIZ_DB.map(q => q[field]))].filter(Boolean);
    return (order || []).filter(k => seen.includes(k))
      .concat(seen.filter(k => !(order || []).includes(k)));
  };
  chipRow($('f-group'),  uniq('group', QUIZ_META.group_order), v => v);
  chipRow($('f-sptype'), uniq('specimen_type', ['충란','충체','조직','혈액도말','gross']),
          v => ko(SPTYPE_KO, v));
  chipRow($('f-qtype'),  uniq('qtype', Object.keys(QUIZ_META.qtype_mix || {})),
          v => ko(QTYPE_KO, v));
  $('n-input').addEventListener('change', renderScope);

  renderScope();
  renderRecords();
  renderWrongButton();
}

async function start(mode, wrongOnly){
  const f = filters();
  // 고른 범위가 좁으면 그만큼만 낸다. 40을 시켰다고 없는 표본을 지어낼 수는 없다.
  const n = Math.min(+$('n-input').value,
                     capacity(QUIZ_DB.filter(q => inScope(q, f))) || 1);
  const seedRaw = $('seed-input').value;
  const seed = seedRaw ? +seedRaw : Math.floor(Math.random()*1e9);
  S.rand = rng(seed);
  S.mode = mode;
  S.limit = mode === 'exam' ? +$('t-input').value : 0;

  if (wrongOnly){
    S.qs = QUIZ_DB.filter(q => WRONG.has(q.id));
    for (let i = S.qs.length-1; i > 0; i--){ const j = Math.floor(S.rand()*(i+1)); [S.qs[i],S.qs[j]] = [S.qs[j],S.qs[i]]; }
  } else {
    S.qs = buildSet(n, f, S.rand);
  }
  if (!S.qs.length){ alert('조건에 맞는 문항이 없습니다.'); return; }

  S.answers = new Array(S.qs.length).fill(null);
  S.imgs = S.qs.map(q => q.image);
  // 보기 순서는 풀 때마다 새로 섞는다. 위치를 외우는 걸 막는다.
  S.opts = S.qs.map(q => {
    const idx = q.options.map((_,i) => i);
    for (let i = idx.length-1; i > 0; i--){ const j = Math.floor(S.rand()*(i+1)); [idx[i],idx[j]] = [idx[j],idx[i]]; }
    return idx;
  });
  S.i = 0;
  S.timedFor = -1;

  // 사진은 세트를 만든 직후에 한 번에 서명받는다. 문항마다 부르면 왕복이
  // 40번이고 그중 39번은 사용자를 기다리는 동안 노는 요청이 된다.
  try {
    await signImages(S.imgs);
  } catch (e){
    alert('사진을 불러오지 못했습니다. ' + e.message);
    return;
  }

  $('start').classList.add('hidden');
  $('quiz').classList.remove('hidden');
  render();
}

/* ══════════ 문제 표시 ══════════ */
function render(){
  const q = S.qs[S.i];
  const qt = ko(QTYPE_KO, q.qtype);
  $('q-type').textContent = q.jokbo ? qt + ' · 족보' : qt;
  $('q-count').textContent = `${S.i+1} / ${S.qs.length}`;
  $('q-stem').textContent = q.stem;

  // 사진은 문항마다 한 번만 고른다. 다시 그릴 때마다 바꾸면 답을 고른 순간 사진이 바뀐다.
  $('q-img').src = S.imgUrl[S.imgs[S.i]] || '';
  const meta = [q.stain, q.magnification].filter(Boolean).join(' · ');
  $('q-meta').textContent = meta;
  $('q-meta').style.display = meta ? '' : 'none';
  $('q-src').innerHTML = srcHtml(S.imgs[S.i]);

  const picked = S.answers[S.i];              // 원본 보기 번호로 저장한다
  const reveal = S.mode === 'study' && picked !== null;
  const order = S.opts[S.i];
  $('q-opts').innerHTML = order.map((oi,pos) => {
    let cls = 'opt';
    if (reveal && oi === q.answer) cls += ' ok';
    else if (reveal && oi === picked) cls += ' no';
    else if (!reveal && oi === picked) cls += ' sel';
    return `<button class="${cls}" onclick="choose(${oi})"><b>${KEYS[pos]}</b><span>${esc(q.options[oi])}</span></button>`;
  }).join('');

  const ex = $('q-explain');
  if (reveal){ ex.classList.remove('hidden');
    ex.innerHTML = `<span class="tag">해설</span>\n` + esc(q.explanation);
  } else ex.classList.add('hidden');

  markReported($('report-btn'), q.id);
  $('btn-prev').disabled = S.i === 0;
  $('btn-next').classList.toggle('hidden', S.i === S.qs.length-1);
  $('btn-finish').classList.toggle('hidden', S.i !== S.qs.length-1);
  // 다음 문제 사진 미리 받아두기
  if (S.imgs[S.i+1] && S.imgUrl[S.imgs[S.i+1]]) new Image().src = S.imgUrl[S.imgs[S.i+1]];
  // **시계는 문항이 바뀔 때만 되감는다.** render()는 답을 고를 때도 불리므로
  // 여기서 무조건 startTimer()를 부르면 답을 누르는 것이 곧 시간 연장이 된다.
  if (S.timedFor !== S.i) startTimer();
}

function choose(i){
  S.answers[S.i] = i;
  // 공부 모드는 답을 고른 순간 시계를 세운다. 땡시 모드는 그대로 흐른다 —
  // 고르고 나서 남은 시간에 다시 고를 수 있어야 실제 땡시와 같다.
  if (S.mode === 'study') stopTimer();
  render();
}

function next(){ if (S.i < S.qs.length-1){ S.i++; render(); } }
function prev(){ if (S.i > 0){ S.i--; render(); } }

/* ══════════ 타이머 ══════════ */
let audioCtx = null;
function buzz(){                     // 땡 — 시간이 다 됐을 때
  if (!$('buzzer').checked) return;
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const t = audioCtx.currentTime, o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.type = 'sine'; o.frequency.setValueAtTime(880, t);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.25, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.45);
    o.connect(g); g.connect(audioCtx.destination); o.start(t); o.stop(t + 0.5);
  } catch (e) {}
}
function tick(){
  $('q-timer').textContent = S.left + '초';
  $('q-timer').classList.toggle('warn', S.left <= 5);
  $('q-bar').style.width = (S.left / S.limit * 100) + '%';
  if (S.left <= 0){ stopTimer(); buzz();
    if (S.i < S.qs.length-1){ S.i++; render(); } else finish();
    return; }
  S.left--;
}
function startTimer(){
  stopTimer();
  S.timedFor = S.i;
  if (!S.limit){ $('q-timer').textContent = ''; $('q-bar').style.width = '100%'; return; }
  S.left = S.limit;
  tick();
  S.timer = setInterval(tick, 1000);
}
function stopTimer(){ if (S.timer){ clearInterval(S.timer); S.timer = null; } }
/** 신고 창이 열려 있는 동안은 시계를 멈춘다. 오류를 적는 시간까지 재면
 *  신고하는 것이 손해가 되고, 그러면 아무도 안 한다. */
function resumeTimer(){ if (S.limit && !S.timer && !$('quiz').classList.contains('hidden')) S.timer = setInterval(tick, 1000); }

/* ══════════ 채점 ══════════ */
async function finish(){
  stopTimer();
  const rows = S.qs.map((q,i) => ({ q, picked: S.answers[i], ok: S.answers[i] === q.answer }));
  const score = rows.filter(r => r.ok).length;

  $('r-score').innerHTML = `${score}<small> / ${S.qs.length}</small>
    <div style="font-size:14px;font-weight:600;color:var(--muted);margin-top:4px">
    정답률 ${Math.round(score/S.qs.length*100)}%</div>`;

  const tally = (key) => {
    const m = {};
    // 족보에서 그대로 가져온 문항 중 몇 개는 표본을 못 짚어 분류군이 비어 있다.
    // 없는 분류군을 지어내지 않고 그대로 '미상'으로 센다.
    rows.forEach(r => {
      const k = key === 'qtype' ? ko(QTYPE_KO, r.q.qtype) : (r.q[key] || '미상');
      (m[k] = m[k] || [0,0]); m[k][1]++; if (r.ok) m[k][0]++; });
    return `<tr><th>${key==='qtype'?'유형':'분류군'}</th><th class="num">정답</th><th class="num">문항</th><th class="num">정답률</th></tr>` +
      Object.entries(m).sort((a,b)=>b[1][1]-a[1][1]).map(([k,[c,t]]) =>
      `<tr><td>${esc(k)}</td><td class="num">${c}</td><td class="num">${t}</td><td class="num">${Math.round(c/t*100)}%</td></tr>`).join('');
  };
  $('r-type').innerHTML = tally('qtype');
  $('r-group').innerHTML = tally('group');

  $('r-review').innerHTML = rows.map((r,i) => `
    <div class="rev ${r.ok?'right':'wrong'}">
      <img src="${esc(S.imgUrl[S.imgs[i]] || '')}" alt="">
      <div class="q">${i+1}. [${esc(ko(QTYPE_KO, r.q.qtype))}] ${esc(r.q.stem)}</div>
      <div class="a">${r.ok ? '' : `<i>내 답: ${r.picked===null?'무응답':esc(r.q.options[r.picked])}</i><br>`}
        <b>정답: ${esc(r.q.options[r.q.answer])}</b></div>
      <div class="explain" style="margin-top:8px">${esc(r.q.explanation)}</div>
      <div class="imgsrc">${srcHtml(S.imgs[i])}</div>
      <button class="report-link" data-qid="${esc(r.q.id)}" data-idx="${i}"
        onclick="openReport('${esc(r.q.id)}', ${i})">이 문항 신고</button>
    </div>`).join('');
  [...$('r-review').querySelectorAll('.report-link')]
    .forEach(b => markReported(b, b.dataset.qid));

  // 오답노트와 기록. 서버가 참이고, 못 닿으면 이 브라우저에 남긴다.
  const wrongIds = rows.filter(r => !r.ok).map(r => r.q.id);
  const rightIds = rows.filter(r => r.ok).map(r => r.q.id);
  wrongIds.forEach(id => WRONG.add(id));
  rightIds.forEach(id => WRONG.delete(id));
  RECORDS.unshift({ at: new Date().toISOString(), mode: S.mode, score, total: S.qs.length });
  RECORDS = RECORDS.slice(0, 30);

  if (OFFLINE) saveLocal();
  else {
    try {
      const state = await api('/api/spotter/finish', { method:'POST', body: JSON.stringify({
        mode: S.mode, score, total: S.qs.length, wrong: wrongIds, right: rightIds }) });
      RECORDS = state.records;
      WRONG = new Set(state.wrong);
    } catch (e){
      // 서버에 못 닿아도 화면은 채점 결과를 그대로 보여 준다. 다음 접속에서
      // 서버 것으로 덮이므로 이 판의 기록은 잃는다 — 그 사실만 알린다.
      $('r-sync').textContent = '기록을 서버에 못 남겼습니다 (' + e.message + ')';
      $('r-sync').classList.remove('hidden');
      saveLocal();
    }
  }
  renderRecords();
  renderWrongButton();

  S.wrongSet = rows.filter(r => !r.ok).map(r => r.q);
  $('r-retry').disabled = !S.wrongSet.length;
  $('quiz').classList.add('hidden');
  $('result').classList.remove('hidden');
  scrollTo(0,0);
}

function retryWrong(){
  if (!S.wrongSet || !S.wrongSet.length) return;
  S.qs = S.wrongSet.slice();
  S.answers = new Array(S.qs.length).fill(null);
  S.imgs = S.qs.map(q => q.image);
  S.opts = S.qs.map(q => q.options.map((_,i) => i));
  S.i = 0; S.timedFor = -1; S.mode = 'study'; S.limit = 0;
  $('result').classList.add('hidden');
  $('quiz').classList.remove('hidden');
  render(); scrollTo(0,0);
}

/* ══════════ 문항 신고 ══════════ */
let reportFor = null;

function markReported(btn, qid){
  if (!btn) return;
  const mine = MY_REPORTS[qid];
  btn.classList.toggle('done', !!mine);
  btn.textContent = mine
    ? (mine.status === 'open' ? '신고함 · 고치기' : '신고함 · ' + STATUS_KO[mine.status])
    : '이 문항 신고';
}

const STATUS_KO = { open:'확인 중', resolved:'고침', wontfix:'의도된 것' };
const KIND_KO = { answer:'정답이 틀렸다', image:'사진이 문제와 안 맞는다',
                  options:'보기가 이상하다', explanation:'해설이 틀렸다', other:'그 밖에' };

/** `idx`가 있으면 다시보기에서 부른 것이다. 없으면 푸는 중이다. */
function openReport(qid, idx){
  if (OFFLINE){ alert('로그인해야 신고할 수 있습니다.'); return; }
  const q = QUIZ_DB.find(x => x.id === qid) || (S.qs[S.i] || {});
  const src = imgSrc(q.image);
  reportFor = { id: qid, stem: q.stem || '', answer: (q.options||[])[q.answer] || '',
                image: q.image || '', imageSrc: src ? src.src + ' / ' + src.path : '' };
  const mine = MY_REPORTS[qid];
  $('report-kind').value = mine ? mine.kind : 'answer';
  $('report-note').value = mine ? mine.note : '';
  $('report-stem').textContent = reportFor.stem;
  $('report-msg').textContent = '';
  $('report-save').disabled = false;
  stopTimer();                       // 적는 시간은 안 잰다
  $('report').classList.remove('hidden');
  $('report-note').focus();
}

function closeReport(){
  $('report').classList.add('hidden');
  reportFor = null;
  resumeTimer();
}

async function sendReport(){
  if (!reportFor) return;
  $('report-save').disabled = true;
  $('report-msg').textContent = '보내는 중…';
  try {
    const row = await api('/api/spotter/reports', { method:'POST', body: JSON.stringify({
      questionId: reportFor.id,
      kind: $('report-kind').value,
      note: $('report-note').value,
      stem: reportFor.stem, answer: reportFor.answer,
      // 사진은 파일명만으로는 원본을 못 찾는다. 출처를 붙여서 보낸다.
      image: reportFor.imageSrc ? `${reportFor.image} (${reportFor.imageSrc})` : reportFor.image,
    })});
    MY_REPORTS[row.questionId] = row;
    markReported($('report-btn'), S.qs[S.i] && S.qs[S.i].id);
    // 다시보기 쪽 링크만. `#report-btn`도 같은 클래스지만 `data-qid`가 없어서
    // 여기 섞이면 방금 칠한 것을 undefined로 되돌린다.
    [...document.querySelectorAll('#r-review .report-link')]
      .forEach(b => markReported(b, b.dataset.qid));
    closeReport();
  } catch (e){
    $('report-msg').textContent = e.message;
    $('report-save').disabled = false;
  }
}

/* ══════════ 신고함 (관리자) ══════════ */
async function loadAdmin(){
  if (!ME || !ME.isAdmin) return;
  $('admin').classList.remove('hidden');
  try {
    const { groups, total } = await api('/api/spotter/admin/reports');
    const open = groups.reduce((a,g) => a + g.open, 0);
    $('admin-sum').textContent = `신고 ${total}건 · 문항 ${groups.length}개 · 확인 중 ${open}건`;
    $('admin-list').innerHTML = groups.length ? groups.map(g => `
      <div class="rep${g.open ? ' hot' : ''}">
        <div class="rep-head">
          <b>${g.open ? g.open + '명 확인 중' : '닫힘'}</b>
          <code>${esc(g.questionId)}</code>
          ${g.open ? `<button class="is-quiet" onclick="closeQuestion('${esc(g.questionId)}')">이 문항 닫기</button>` : ''}
        </div>
        <div class="rep-stem">${esc(g.reports[0].stem)}</div>
        <div class="rep-ans">정답으로 나간 보기: ${esc(g.reports[0].answer) || '—'}</div>
        ${g.reports.map(r => `
          <div class="rep-one">
            <span class="rep-kind">${esc(KIND_KO[r.kind] || r.kind)}</span>
            <span class="rep-who">${esc(r.email)} · ${esc(STATUS_KO[r.status] || r.status)}</span>
            ${r.note ? `<div class="rep-note">${esc(r.note)}</div>` : ''}
          </div>`).join('')}
      </div>`).join('') : '들어온 신고가 없습니다.';
  } catch (e){
    $('admin-sum').textContent = '신고함을 못 읽었습니다: ' + e.message;
  }
}

async function closeQuestion(qid){
  try {
    await api(`/api/spotter/admin/reports/${encodeURIComponent(qid)}/close`, { method:'POST' });
    await loadAdmin();
  } catch (e){ alert(e.message); }
}

/* ══════════ 저장 ══════════ */
/* localStorage는 이제 **로그인 전과 서버에 못 닿을 때만** 쓴다. 로그인하면
   서버가 참이고, 로그인 직후 여기 있던 오답은 한 번 계정으로 합쳐진다. */
function saveLocal(){
  try {
    localStorage.setItem('para_wrong', JSON.stringify([...WRONG]));
    localStorage.setItem('para_records', JSON.stringify(RECORDS.slice(0,30)));
  } catch (e){}
}
function loadLocal(){
  try {
    WRONG = new Set(JSON.parse(localStorage.getItem('para_wrong') || '[]'));
    RECORDS = JSON.parse(localStorage.getItem('para_records') || '[]');
  } catch (e){ WRONG = new Set(); RECORDS = []; }
}

/* ══════════ 기타 ══════════ */
/** 사진 한 장의 출처 한 줄. `meta.images`에 사진마다 한 번만 들어 있다 —
 *  문항마다 넣으면 같은 문장이 6,461번 되풀이된다. */
function imgSrc(name){ return (QUIZ_META && QUIZ_META.images && QUIZ_META.images[name]) || null; }
function srcHtml(name){
  const s = imgSrc(name);
  if (!s) return '';
  // 선명도는 낮을수록 흐리다. 아래쪽 것들만 표시해서 "내 눈이 문제인가"를 가른다.
  const blur = s.sharp && s.sharp < 12 ? `<span class="dim">흐린 사진 (선명도 ${s.sharp})</span>` : '';
  return `<span>출처: ${esc(s.src)}</span><code>${esc(s.path)}</code>${blur}`;
}

function zoom(){
  $('modal-img').src = $('q-img').src;
  const s = imgSrc(S.imgs[S.i]);
  $('modal-src').textContent = s ? s.src + '  ·  ' + s.path : '';
  $('modal').classList.remove('hidden');
}
document.addEventListener('keydown', e => {
  if (!$('report').classList.contains('hidden')){
    if (e.key === 'Escape') closeReport();
    return;                          // 신고 창이 열려 있으면 문제 단축키를 막는다
  }
  if ($('quiz').classList.contains('hidden')) return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key >= '1' && e.key <= '4'){ const pos = +e.key - 1;
    const order = S.opts[S.i];
    if (pos < order.length) choose(order[pos]); }
  else if (e.key === 'Enter'){ S.i === S.qs.length-1 ? finish() : next(); }
  else if (e.key === 'ArrowLeft') prev();
  else if (e.key === 'ArrowRight') next();
  else if (e.key === 'Escape') $('modal').classList.add('hidden');
});

/* ══════════ 부팅 ══════════ */

async function loadDB(){
  const r = await fetch(OFFLINE_ROOT + 'quiz_db.json');
  if (!r.ok) throw new Error('build/quiz_db.json이 없습니다. scripts/build_web.py를 돌리세요.');
  return r.json();
}

/** 로그인이 끝난 뒤. `gate.js`가 문항 DB를 받아서 넘겨준다.
 *
 *  던지면 GATE가 그 자리에 이유를 띄운다 — 여기서 따로 안 잡는다.
 */
async function enter(db){
  QUIZ_META = db.meta; QUIZ_DB = db.questions;

  if (OFFLINE) loadLocal();
  else {
    // 로그인 전에 이 브라우저에 쌓인 오답을 한 번만 계정으로 옮긴다.
    const stray = JSON.parse(localStorage.getItem('para_wrong') || '[]');
    const state = stray.length
      ? await api('/api/spotter/state/merge', { method:'POST', body: JSON.stringify({ wrong: stray }) })
      : await api('/api/spotter/state');
    if (stray.length) localStorage.removeItem('para_wrong');
    RECORDS = state.records; WRONG = new Set(state.wrong);

    ME = await api('/api/me');
    const mine = await api('/api/spotter/reports/mine');
    MY_REPORTS = Object.fromEntries(mine.reports.map(r => [r.questionId, r]));
    $('who-email').textContent = ME.email;
    $('who').classList.remove('hidden');
    loadAdmin();
  }

  initStart();
  $('start').classList.remove('hidden');
}

async function signOut(){
  await AUTH.signOut();
  location.reload();
}

async function boot(){
  /* 로그인 없이 도는 갈래는 문을 아예 안 연다. localhost 전용이고,
     `build/`를 직접 읽는다 — `config.js`의 설명을 보라. */
  if (OFFLINE){
    try { await enter(await loadDB()); }
    catch (e){
      document.body.innerHTML =
        `<div class="wrap"><div class="card">불러오지 못했습니다.<br><br>` +
        `<span style="color:var(--muted)">${esc(e.message)}</span></div></div>`;
    }
    return;
  }
  // 나머지는 전부 공용 문을 지난다. 해부학 넷과 같은 화면, 같은 세션이다.
  GATE.start(SUBJECT, enter);
}

boot();
