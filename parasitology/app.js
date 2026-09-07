/* 기생충학 땡시 연습.
 *
 * **문항 조립은 여기서 한다.** 서버가 넘기는 것은 완성된 후보 문항 전체이고,
 * 어떤 40문항을 뽑을지(가중 표집·중복 회피·순서)는 브라우저가 정한다. 시드를
 * 바꿀 때마다 왕복이 붙지 않게 하려는 것이다.
 *
 * 서버가 하는 일은 셋이다 — 로그인 확인, 사진 서명, 기록·제보 보관.
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
/* `imgs`는 **문항마다 사진 이름의 배열**이다. 대개 한 장이지만 족보에는
   현미경 + 데모처럼 두 장을 놓고 묻는 문항이 있고, 그중에는 indicator가
   둘째 장에만 찍힌 것도 있어서 첫 장만 그리면 문제가 성립하지 않는다. */
let S = { qs:[], i:0, answers:[], mode:'exam', limit:30, timer:null, left:0, rand:null,
          imgs:[], imgUrl:{}, opts:[], timedFor:-1, srcOpen:false, srcFor:-1 };
/** 문항이 쓰는 사진 이름 전부. 한 장짜리는 `images` 없이 `image`만 들고 온다. */
const imgsOf = q => (q.images && q.images.length ? q.images : [q.image]).filter(Boolean);
let QUIZ_META = null, QUIZ_DB = [];
let ME = null;                      // /api/me. 관리자 화면을 그릴지 정한다
let WRONG = new Set();              // 오답노트. 서버가 참, 없으면 localStorage
let RECORDS = [];
let MY_REPORTS = {};                // question_id → 내가 낸 제보

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
  S.imgs = S.qs.map(imgsOf);
  // 보기 순서는 풀 때마다 새로 섞는다. 위치를 외우는 걸 막는다.
  S.opts = S.qs.map(q => {
    const idx = q.options.map((_,i) => i);
    for (let i = idx.length-1; i > 0; i--){ const j = Math.floor(S.rand()*(i+1)); [idx[i],idx[j]] = [idx[j],idx[i]]; }
    return idx;
  });
  S.i = 0;
  S.timedFor = -1;
  // 새 판은 접힌 채로 시작한다. 지난 판에서 펴 둔 것이 따라오지 않는다.
  S.srcOpen = false; S.srcFor = -1;

  // 사진은 세트를 만든 직후에 한 번에 서명받는다. 문항마다 부르면 왕복이
  // 40번이고 그중 39번은 사용자를 기다리는 동안 노는 요청이 된다.
  try {
    await signImages([...new Set(S.imgs.flat())]);
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

  /* 사진은 문항마다 한 번만 고른다. 다시 그릴 때마다 바꾸면 답을 고른 순간
     사진이 바뀐다. **두 장짜리는 둘 다 놓는다** — 실제 땡시가 현미경과 데모를
     같이 놓고 묻는 자리가 있고, indicator가 둘째 장에만 찍힌 문항도 있다. */
  const names = S.imgs[S.i];
  /* 사진 위에 남기는 것은 배율뿐이다. **염색법은 답을 반쯤 알려 준다** —
     철헤마톡실린이라 쓰여 있으면 원충을 찍은 사진이고, 그것만으로 보기 넷 중
     둘이 지워진다. 사진을 보고 알아보는 것이 이 시험이므로, 염색은 출처와
     함께 접어 둔다 — 접힌 것을 펴는 것은 알아보기를 포기한 뒤의 일이다. */
  const meta = q.magnification || '';
  const row = $('q-imgs');
  row.classList.toggle('multi', names.length > 1);
  row.innerHTML = names.map((n, k) => `
    <div class="imgbox" onclick="zoom(${k})">
      <img src="${esc(S.imgUrl[n] || '')}" alt="표본 사진">
      ${meta && k === 0 ? `<span class="imgmeta">${esc(meta)}</span>` : ''}
    </div>`).join('');
  /* 출처는 접어 둔다. **땡시에서는 문항이 바뀌면 다시 접히고, 공부에서는
     펴 둔 채로 따라온다.** 시간을 재는 화면에서 한 번 편 것이 마흔 문항을
     따라다니면 접어 둔 뜻이 없고, 사진마다 원본을 짚어 보는 공부 중에는
     문항마다 다시 누르는 것이 성가시다. */
  if (S.mode === 'exam' && S.srcFor !== S.i) S.srcOpen = false;
  S.srcFor = S.i;
  renderSrc();

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

  $('q-hint').innerHTML = S.mode === 'exam'
    ? '키보드 1·2·3·4로 선택 — 고르면 바로 다음 문항으로 넘어갑니다<br>제보하는 동안은 시계가 멈춥니다.'
    : '키보드 1·2·3·4로 선택, Enter로 다음<br>제보하는 동안은 시계가 멈춥니다.';
  markReported($('report-btn'), q.id);
  $('btn-prev').disabled = S.i === 0;
  $('btn-next').classList.toggle('hidden', S.i === S.qs.length-1);
  $('btn-finish').classList.toggle('hidden', S.i !== S.qs.length-1);
  // 다음 문제 사진 미리 받아두기
  (S.imgs[S.i+1] || []).forEach(n => { if (S.imgUrl[n]) new Image().src = S.imgUrl[n]; });
  // **시계는 문항이 바뀔 때만 되감는다.** render()는 답을 고를 때도 불리므로
  // 여기서 무조건 startTimer()를 부르면 답을 누르는 것이 곧 시간 연장이 된다.
  if (S.timedFor !== S.i) startTimer();
}

function choose(i){
  S.answers[S.i] = i;
  // 공부 모드는 답을 고른 순간 시계를 세운다. 여기서는 고른 자리에 머물러
  // 정답과 해설을 읽는 것이 할 일이다.
  if (S.mode === 'study'){ stopTimer(); render(); return; }
  /* **땡시 모드에서는 고르는 것이 곧 넘기는 것이다.** 실제 땡시는 종이 울리면
     다음 자리로 옮겨 서는 것이고, 다 골라 놓고 Enter를 한 번 더 치는 동작은
     화면에만 있는 절차다. 30초 안에 두 번 누르게 하면 그 한 번이 아깝다.

     다시 고를 길은 남는다 — 「이전」이나 ←로 돌아오면 고른 것이 그대로 있고
     바꿀 수 있다. 잃는 것은 그 문항에 남아 있던 시간뿐이다.

     **마지막 문항에서는 넘기지 않는다.** 넘길 자리가 채점밖에 없는데, 손이
     미끄러진 한 번으로 마흔 문항이 끝나 버리면 되돌릴 방법이 없다. 채점은
     눌러서 끝낸다. */
  if (S.i < S.qs.length - 1) next();
  else render();
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
  // 「30초」가 아니라 「0:30」. 글자가 붙으면 문장처럼 읽혀 자꾸 눈이 가는데,
  // 시계 모양이면 시계로만 보인다. 자리 수도 끝까지 안 바뀐다.
  $('q-timer').textContent = Math.floor(S.left / 60) + ':'
    + String(S.left % 60).padStart(2, '0');
  $('q-timer').classList.toggle('warn', S.left <= 5);
  if (S.left <= 0){ stopTimer(); buzz();
    if (S.i < S.qs.length-1){ S.i++; render(); } else finish();
    return; }
  S.left--;
}
function startTimer(){
  stopTimer();
  S.timedFor = S.i;
  if (!S.limit){ $('q-timer').textContent = ''; return; }
  S.left = S.limit;
  tick();
  S.timer = setInterval(tick, 1000);
}
function stopTimer(){ if (S.timer){ clearInterval(S.timer); S.timer = null; } }
/** 제보 창이 열려 있는 동안은 시계를 멈춘다. 오류를 적는 시간까지 재면
 *  제보하는 것이 손해가 되고, 그러면 아무도 안 한다. */
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
      <span class="revimgs">${S.imgs[i].map(n =>
        `<img src="${esc(S.imgUrl[n] || '')}" data-img="${esc(n)}" alt="">`).join('')}</span>
      <div class="q">${i+1}. [${esc(ko(QTYPE_KO, r.q.qtype))}] ${esc(r.q.stem)}</div>
      <div class="a">${r.ok ? '' : `<i>내 답: ${r.picked===null?'무응답':esc(r.q.options[r.picked])}</i><br>`}
        <b>정답: ${esc(r.q.options[r.q.answer])}</b></div>
      <div class="explain" style="margin-top:8px">${esc(r.q.explanation)}</div>
      <div class="imgsrc${S.imgs[i].length > 1 ? ' many' : ''}">${stainHtml(r.q)}${
        S.imgs[i].map(n => srcHtml(n, true)).join('')}</div>
      <button class="report-link" data-qid="${esc(r.q.id)}" data-idx="${i}"
        onclick="openReport('${esc(r.q.id)}', ${i})">이 문항 제보</button>
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

/** 풀던 판을 접고 시작 화면으로. 결과 화면의 「처음으로」도 여기로 온다.
 *
 *  **땡시 모드에서 답을 하나라도 골랐으면 한 번 묻는다.** 시간을 재는 화면에서
 *  잘못 누르면 그 판이 채점도 없이 사라지고, 되돌릴 방법이 없다. 공부 모드는
 *  고른 즉시 정답을 봤으므로 잃을 것이 없어 그냥 나간다.
 */
function quit(){
  const inQuiz = !$('quiz').classList.contains('hidden');
  if (inQuiz && S.mode === 'exam' && S.answers.some(a => a !== null)
      && !confirm('풀던 땡시를 그만둡니다. 지금까지 고른 답은 채점하지 않습니다.')) return;
  stopTimer();
  $('quiz').classList.add('hidden');
  $('result').classList.add('hidden');
  $('start').classList.remove('hidden');
  scrollTo(0,0);
}

function retryWrong(){
  if (!S.wrongSet || !S.wrongSet.length) return;
  S.qs = S.wrongSet.slice();
  S.answers = new Array(S.qs.length).fill(null);
  S.imgs = S.qs.map(imgsOf);
  S.opts = S.qs.map(q => q.options.map((_,i) => i));
  S.i = 0; S.timedFor = -1; S.mode = 'study'; S.limit = 0;
  S.srcOpen = false; S.srcFor = -1;
  $('result').classList.add('hidden');
  $('quiz').classList.remove('hidden');
  render(); scrollTo(0,0);
}

/* ══════════ 문항 제보 ══════════ */
let reportFor = null;

function markReported(btn, qid){
  if (!btn) return;
  const mine = MY_REPORTS[qid];
  // 문제 화면의 버튼은 시계를 멈추는 일도 겸하므로 이름이 다르다. 그 이름은
  // 버튼이 `data-label`로 들고 있고, 다시보기 쪽은 예전 이름을 그대로 쓴다.
  const base = btn.dataset.label || '이 문항 제보';
  btn.classList.toggle('done', !!mine);
  btn.textContent = mine
    ? (mine.status === 'open' ? '제보함 · 고치기' : '제보함 · ' + STATUS_KO[mine.status])
    : base;
}

const STATUS_KO = { open:'확인 중', resolved:'고침', wontfix:'의도된 것' };
const KIND_KO = { answer:'정답이 틀렸다', image:'사진이 문제와 안 맞는다',
                  options:'보기가 이상하다', explanation:'해설이 틀렸다', other:'그 밖에' };

/** `idx`가 있으면 다시보기에서 부른 것이다. 없으면 푸는 중이다. */
function openReport(qid, idx){
  if (OFFLINE){ alert('로그인해야 제보할 수 있습니다.'); return; }
  const q = QUIZ_DB.find(x => x.id === qid) || (S.qs[S.i] || {});
  // 사진이 둘인 문항은 둘 다 적어 보낸다. 어느 쪽이 이상한지는 제보 글이 말한다.
  const names = imgsOf(q);
  const srcs = names.map(imgSrc).filter(Boolean).map(s => s.src + ' / ' + s.path);
  reportFor = { id: qid, stem: q.stem || '', answer: (q.options||[])[q.answer] || '',
                image: names.join(', '), imageSrc: srcs.join(' · ') };
  const mine = MY_REPORTS[qid];
  $('report-kind').value = mine ? mine.kind : 'answer';
  $('report-note').value = mine ? mine.note : '';
  $('report-stem').textContent = reportFor.stem;
  $('report-detail').innerHTML = reportDetail(q, names);
  $('report-msg').textContent = '';
  $('report-save').disabled = false;
  stopTimer();                       // 적는 시간은 안 잰다
  $('report').classList.remove('hidden');
  $('report-note').focus();
}

/** 제보 창 안에서 보는 출처와 해설.
 *
 *  틀렸다고 적으려면 무엇이 어떻게 틀렸는지부터 봐야 한다. 창을 닫고
 *  확인한 뒤 다시 열면 적던 글이 날아가므로, 볼 것을 창 안으로 들인다.
 *
 *  **편 채로 연다.** 제보하러 온 사람은 이미 이 문항을 포기하고 고치러 온
 *  사람이라, 답이 보이는 것은 잃을 것이 아니다. 한 번 더 누르게 하면 그
 *  한 번이 제보를 그만두게 하는 쪽에 선다.
 *
 *  접는 손잡이는 남겨 둔다 — 해설이 길면 적는 칸이 화면 밖으로 밀린다.
 */
function reportDetail(q, names){
  const box = (title, body) =>
    `<details open><summary>${title}</summary><div class="body">${body}</div></details>`;
  const out = [];

  const srcs = (names || []).map(imgSrc).filter(Boolean);
  const bits = [
    q.stain ? `<span class="k">염색</span> ${esc(q.stain)}` : '',
    q.magnification ? `<span class="k">배율</span> ${esc(q.magnification)}` : '',
    ...srcs.map(s => `<span class="k">출처</span> ${esc(s.src)}<br><code>${esc(s.path)}</code>`
      + (s.sharp && s.sharp < 12 ? `<br><span class="k">선명도 ${s.sharp} · 흐린 사진</span>` : '')),
  ].filter(Boolean);
  if (bits.length) out.push(box('사진 출처', bits.join('<br>')));

  const ans = (q.options || [])[q.answer];
  if (ans || q.explanation)
    out.push(box('정답과 해설',
      (ans ? `<b>정답: ${esc(ans)}</b>` : '')
      + (q.explanation ? `${ans ? '<br>' : ''}${esc(q.explanation)}` : '')));

  return out.join('');
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

/* ══════════ 제보함 (관리자) ══════════ */
async function loadAdmin(){
  if (!ME || !ME.isAdmin) return;
  $('admin').classList.remove('hidden');
  try {
    const { groups, total } = await api('/api/spotter/admin/reports');
    const open = groups.reduce((a,g) => a + g.open, 0);
    $('admin-sum').textContent = `제보 ${total}건 · 문항 ${groups.length}개 · 확인 중 ${open}건`;
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
      </div>`).join('') : '들어온 제보가 없습니다.';
  } catch (e){
    $('admin-sum').textContent = '제보함을 못 읽었습니다: ' + e.message;
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
// 선명도는 낮을수록 흐리다. 아래쪽 것들만 표시해서 "내 눈이 문제인가"를 가른다.
function blurHtml(s){
  return s.sharp && s.sharp < 12 ? `<span class="dim">흐린 사진 (선명도 ${s.sharp})</span>` : '';
}
/* 사진 하나가 한 덩어리다. **둘일 때 덩어리로 묶지 않으면** 두 줄이 한 줄로
   섞여서, 「흐린 사진」이 어느 쪽 이야기인지 알 수 없게 된다. */
function srcHtml(name, withLabel){
  const s = imgSrc(name);
  if (!s) return '';
  return `<span class="src-one"><span>${withLabel ? '출처: ' : ''}${esc(s.src)}</span>`
       + `<code>${esc(s.path)}</code>${blurHtml(s)}</span>`;
}
/** 염색법 한 줄. 사진 위가 아니라 출처 쪽에 선다. 사진이 둘이어도 염색은
 *  문항의 것이라 한 번만 적는다. */
function stainHtml(q){
  return q && q.stain ? `<span>염색: ${esc(q.stain)}</span>` : '';
}

/** 문제 화면의 출처 줄. 접힌 채로 손잡이만 서 있다가, 누르면 펴진다.
 *
 *  선명도도 같이 접는다. 흐린 사진이라는 말이 먼저 눈에 들어오면 사진을
 *  보기 전에 "이건 못 맞히는 문제"라고 접어 버리게 된다 — 알아볼 수 있는지
 *  먼저 겨뤄 보고, 그러고 나서 펴 보는 순서가 맞다.
 */
function renderSrc(){
  const el = $('q-src');
  // 사진이 둘이면 출처도 둘이다. 사진 하나가 한 줄이 되게 나눠 놓는다.
  const names = S.imgs[S.i].filter(imgSrc);
  // 염색만 있고 출처가 없는 사진도 있다. 그때도 손잡이는 서 있어야 한다.
  const stain = stainHtml(S.qs[S.i]);
  if (!names.length && !stain){ el.innerHTML = ''; return; }
  el.classList.toggle('many', names.length > 1);
  el.innerHTML =
    `<button class="src-toggle" onclick="toggleSrc()">출처 ${S.srcOpen ? '▾' : '▸'}</button>`
    + (S.srcOpen ? stain + names.map(n => srcHtml(n)).join('') : '');
}
function toggleSrc(){ S.srcOpen = !S.srcOpen; renderSrc(); }

/* ── 확대창
 *
 * 화면에 맞춰 놓는 것만으로는 부족하다. 실습 사진은 접안렌즈에 대고 찍은
 * 것이라 400x라 해도 정작 봐야 할 충란은 시야 한구석의 작은 점이고, 화면
 * 폭에 맞춘 크기로는 무엇인지 가려낼 수가 없다. 그래서 **그 위에서 더
 * 키우고 밀어 볼 수 있게** 한다.
 *
 * 배율은 `transform: scale`로 준다 — `width`를 늘리면 브라우저가 레이아웃을
 * 다시 잡느라 손가락을 따라오지 못한다.
 */
let Z = { k:1, x:0, y:0, drag:null };

function zApply(){
  const el = $('modal-img');
  el.style.transform = `translate(${Z.x}px,${Z.y}px) scale(${Z.k})`;
  $('modal').classList.toggle('zoomed', Z.k > 1.01);
  $('modal-hint').style.opacity = Z.k > 1.01 ? 0 : 1;
}
function zReset(){ Z.k = 1; Z.x = 0; Z.y = 0; zApply(); }

/** 화면의 한 점을 붙잡은 채로 배율만 바꾼다. 손가락(또는 커서) 밑에 있던
 *  것이 그 자리에 그대로 있어야 어디를 보고 있었는지 놓치지 않는다. */
function zAt(cx, cy, k2){
  const b = $('modal-img').getBoundingClientRect();
  // 이미지 좌표에서 그 점이 어디였는지 — 지금 배율을 걷어낸 값
  const ix = (cx - b.left) / Z.k, iy = (cy - b.top) / Z.k;
  Z.k = Math.min(8, Math.max(1, k2));
  Z.x += cx - (b.left + ix * Z.k);
  Z.y += cy - (b.top + iy * Z.k);
  if (Z.k <= 1.01) { Z.x = 0; Z.y = 0; Z.k = 1; }
  zApply();
}

/** 사진 이름 하나를 확대창에 건다. 문제 화면과 채점 화면이 같은 창을 쓴다. */
function zoomImg(name){
  if (!name) return;
  $('modal-img').src = S.imgUrl[name] || '';
  const s = imgSrc(name);
  $('modal-src').textContent = s ? s.src + '  ·  ' + s.path : '';
  zReset();
  $('modal').classList.remove('hidden');
}

function zoom(k){
  // 누른 사진을 키운다. 두 장짜리 문항에서 아무 쪽이나 키울 수 있어야 한다.
  zoomImg(S.imgs[S.i][k || 0]);
}

/* 다시보기 사진을 누르면 같은 확대창이 뜬다. 다시보기는 채점할 때마다 통째로
   다시 그리므로 사진 하나하나에 손잡이를 다는 대신 목록에 하나만 단다. */
$('r-review').addEventListener('click', e => {
  const img = e.target.closest('img[data-img]');
  if (img) zoomImg(img.dataset.img);
});

(function zoomControls(){
  const m = $('modal');

  // 배경을 누르면 닫는다. **끌고 나서 뗀 것은 닫지 않는다** — 사진을 밀다가
  // 손을 떼면 창이 닫혀 버리면 확대해 놓은 것이 매번 날아간다.
  let moved = false;
  m.addEventListener('pointerdown', e => {
    moved = false;
    if (Z.k > 1.01){
      Z.drag = { x:e.clientX, y:e.clientY };
      m.classList.add('dragging');
      // 창 밖으로 끌고 나가도 계속 따라오게 붙잡는다. 붙잡을 수 없는
      // 포인터면(이미 놓인 뒤 등) 던지므로, 못 붙잡아도 끌기는 되게 둔다.
      try { m.setPointerCapture(e.pointerId); } catch (_){}
    }
  });
  m.addEventListener('pointermove', e => {
    if (!Z.drag) return;
    const dx = e.clientX - Z.drag.x, dy = e.clientY - Z.drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
    Z.x += dx; Z.y += dy;
    Z.drag = { x:e.clientX, y:e.clientY };
    zApply();
  });
  m.addEventListener('pointerup', e => {
    Z.drag = null;
    m.classList.remove('dragging');
    if (!moved && e.target.id !== 'modal-img') m.classList.add('hidden');
    else if (!moved && Z.k <= 1.01) m.classList.add('hidden');
  });

  m.addEventListener('wheel', e => {
    e.preventDefault();
    zAt(e.clientX, e.clientY, Z.k * (e.deltaY < 0 ? 1.18 : 1 / 1.18));
  }, { passive:false });

  m.addEventListener('dblclick', e => {
    e.preventDefault();
    Z.k > 1.01 ? zReset() : zAt(e.clientX, e.clientY, 3);
  });

  // 두 손가락. 포인터 두 개의 거리 변화가 곧 배율이다.
  const pts = new Map();
  let base = 0;
  m.addEventListener('pointerdown', e => { pts.set(e.pointerId, e); if (pts.size === 2) base = 0; });
  m.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, e);
    if (pts.size !== 2) return;
    Z.drag = null;                      // 두 손가락일 때는 끌기를 멈춘다
    const [a, b] = [...pts.values()];
    const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    if (!base) { base = d; return; }
    zAt((a.clientX + b.clientX) / 2, (a.clientY + b.clientY) / 2, Z.k * (d / base));
    base = d;
  });
  const drop = e => { pts.delete(e.pointerId); base = 0; };
  m.addEventListener('pointerup', drop);
  m.addEventListener('pointercancel', drop);
})();
document.addEventListener('keydown', e => {
  if (!$('report').classList.contains('hidden')){
    if (e.key === 'Escape') closeReport();
    return;                          // 제보 창이 열려 있으면 문제 단축키를 막는다
  }
  // 확대창은 채점 화면에서도 열리므로 문제 화면인지보다 먼저 본다. 닫는 키만
  // 가로챈다 — 문제 화면에서는 사진을 키워 둔 채로 답을 고를 수 있어야 한다.
  if (e.key === 'Escape' && !$('modal').classList.contains('hidden')){
    $('modal').classList.add('hidden');
    return;
  }
  if ($('quiz').classList.contains('hidden')) return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key >= '1' && e.key <= '4'){ const pos = +e.key - 1;
    const order = S.opts[S.i];
    if (pos < order.length) choose(order[pos]); }
  else if (e.key === 'Enter'){ S.i === S.qs.length-1 ? finish() : next(); }
  else if (e.key === 'ArrowLeft') prev();
  else if (e.key === 'ArrowRight') next();
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
