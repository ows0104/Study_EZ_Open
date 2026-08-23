# -*- coding: utf-8 -*-
"""재생성이 끝난 편의 기출 카드를 한 장짜리 검토 페이지로 모은다.

    python build_review.py <repo> <out.html>

`regen.log` 가 있는 편만 담는다. 새 편이 구워지면 다시 부르면 된다.
"""
import json
import glob
import os
import sys

repo = sys.argv[1]
out = sys.argv[2]

# 322장을 읽고 「사람이 판정해야 결론이 나는 것」만 추렸다. 값은 (묶음, 왜).
# 나열형·함정·의학지식은 표본이다 — 몇 장만 보고 범주째로 정하라는 뜻이다.
PICKS = {
    "260812_01/c062": ("고칠 것", "선지 다섯(형태·기능·유전·환경·모양)이 있어야 성립하는 문항인데 진술만 남았다 — needs_options 인데 genuinely_wrong 으로 갈려 문지기를 지나갔다"),

    "260813_03/c090": ("대조 끝 · 카드가 맞다", "2023-89는 「틀린 것을 고르시오」에 정답 ③ — PDGF 선지는 출제자가 참으로 뒀다. 슬라이드 13도 PDGF를 angiogenesis 성장인자에 싣는다"),
    "260813_03/c092": ("대조 끝 · 카드가 맞다", "2020-21 정답 ⑤ — 「근섬유모세포가 다수」는 거짓 선지다. 강의록도 myofibroblast 분화를 그 뒤 수축 단계에 둔다"),
    "260813_02/c083": ("대조 끝 · 카드가 맞다", "2021-12 정답 ① Integrin. 문항 자체가 integrin을 「세포바깥바탕질 단백질」로 부르고, 필기자도 교수의 정리를 그대로 적어 뒀다"),
    "260813_03/c104": ("대조 끝 · 카드가 맞다", "둘 다 자기 강의록에 충실하다 — 이 편의 슬라이드 13은 integrin을 「receptor」로 적는다. 어긋남은 카드가 아니라 두 강의록 사이에 있다"),
    "260814_03/c071": ("대조 끝 · 카드가 맞다", "2022-101 정답 ④ Neutrophil. 다만 원 문항의 현미경 사진이 카드에서 빠졌다"),

    "260814_02/c119": ("정답표 대조", "조각에 정답이 「미확인」이다 — 사람이 확인해 달라고 적혀 있다"),
    "260812_02/c079": ("정답표 대조", "정답이 조각에 없어 의학 지식으로 세웠다"),
    "260812_05/c039": ("정답표 대조", "복원본에 사진이 없어 정답 조합을 확정하지 못했다"),

    "260813_05/c102": ("연도 어긋남", "부록은 2018-8, 조각은 2021-R8 — 뒷면 연도가 갈린다"),
    "260813_05/c103": ("연도 어긋남", "부록은 2018-7, 조각은 2021-R7 — 뒷면 연도가 갈린다"),

    "260813_01/c128": ("나열형 표본", "「이 강의가 정한 다섯 가지」 — 자기채점으로 풀리는가"),
    "260813_01/c135": ("나열형 표본", "같은 꼴. 재현 검사가 목록을 다르게 재구성했다"),
    "260814_01/c105": ("나열형 표본", "넷 중 TLR 하나만 일반 지식과 겹친다"),
    "260814_01/c110": ("나열형 표본", "강의가 고른 넷과 절반만 겹친다"),
    "260812_03/c096": ("나열형 표본", "재현 답과 한 항목도 겹치지 않았다"),
    "260814_03/c072": ("나열형 표본", "삼차 림프구조·alveolar septum이 이 강의 고유 항목이다"),

    "260813_01/c137": ("함정 표본", "O/X 함정의 전형 — 손대지 않은 X 카드다"),
    "260814_03/c053": ("함정 표본", "O/X 함정"),
    "260814_02/c118": ("함정 표본", "O/X 함정"),
    "260812_03/c076": ("함정 표본", "O/X 함정 — 기전을 정반대로 뒤집었다"),
    "260813_05/c082": ("함정 표본", "O/X 함정"),
    "260814_03/c058": ("함정 표본", "O/X 함정"),

    "260813_02/c088": ("의학지식 표본", "강의록에 없는 되먹임 기전을 채웠다 — 분량을 줄 자리인가"),
    "260813_03/c102": ("의학지식 표본", "특수염색 넷이 무엇을 보는지는 강의록에 없다"),
    "260814_01/c109": ("의학지식 표본", "삼차 림프구조가 만성 염증 소견이라는 것은 강의록에 없다"),
}

cards = []
runs = []
for p in sorted(glob.glob(os.path.join(repo, "runs/2608*/items.reproduced.json"))):
    d = os.path.dirname(p)
    run = os.path.basename(d)
    if not os.path.exists(os.path.join(d, "regen.log")):
        continue
    doc = json.load(open(p, encoding="utf-8"))["cards"]
    jok = [c for c in doc if c.get("source_type") == "jokbo"]
    runs.append({"run": run, "cards": len(doc), "jokbo": len(jok),
                 "hit": sum(1 for c in doc if c.get("exam_hit"))})
    for c in jok:
        ref = c.get("jokbo_ref") or {}
        uid = run + "/" + c["id"]
        pick = PICKS.get(uid)
        cards.append({
            "uid": uid,
            "pick": pick[0] if pick else "",
            "why": pick[1] if pick else "",
            "run": run,
            "id": c["id"],
            "q": c["q"],
            "a": c["a"],
            "e": c.get("explanation") or "",
            "note": c.get("review_note") or "",
            "fmt": c.get("card_format"),
            "type": c.get("card_type"),
            "imp": c.get("importance"),
            "ev": c.get("evidence_type"),
            "ref": (ref.get("year") or "?") + "-" + (ref.get("no") or "?"),
            "flags": c.get("review_flags") or [],
            "verdict": (c.get("reproduce") or {}).get("verdict"),
        })

missing = set(PICKS) - {c["uid"] for c in cards}
if missing:
    print("!! PICKS 에 없는 카드를 가리킨다:", ", ".join(sorted(missing)))

data = json.dumps({"runs": runs, "cards": cards}, ensure_ascii=False, separators=(",", ":"))

HTML = """<title>기출 카드 검토대</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">
<style>
:root{
  --ground:#f7f6f9; --surface:#ffffff; --sunk:#f1eff5;
  --ink:#1e1a28; --muted:#6b6478; --faint:#918a9e;
  --line:#e3dfea; --line-strong:#d3cddf;
  --hema:#4a3a8c; --hema-soft:#ece8f8;
  --eosin:#c24e6e; --eosin-soft:#fbeaef;
  --same:#2e7d6b; --partial:#9d6a11; --diff:#c24e6e;
  --shadow:0 1px 2px rgba(30,26,40,.05), 0 8px 24px -16px rgba(30,26,40,.25);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#15121b; --surface:#1d1926; --sunk:#241f2f;
    --ink:#ece9f2; --muted:#a29ab2; --faint:#7d7690;
    --line:#2d2739; --line-strong:#3b3349;
    --hema:#a795ea; --hema-soft:#2a2340;
    --eosin:#e88ba2; --eosin-soft:#3a2430;
    --same:#5cbfa6; --partial:#d9a03c; --diff:#e88ba2;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px -16px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --ground:#15121b; --surface:#1d1926; --sunk:#241f2f;
  --ink:#ece9f2; --muted:#a29ab2; --faint:#7d7690;
  --line:#2d2739; --line-strong:#3b3349;
  --hema:#a795ea; --hema-soft:#2a2340;
  --eosin:#e88ba2; --eosin-soft:#3a2430;
  --same:#5cbfa6; --partial:#d9a03c; --diff:#e88ba2;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px -16px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans KR",-apple-system,"Malgun Gothic",sans-serif;
  font-size:16px; line-height:1.62; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:980px; margin:0 auto; padding:0 20px}
code,.mono,.ref,.num{font-family:"IBM Plex Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums}

/* ---- head ---- */
header{border-bottom:1px solid var(--line); background:var(--surface)}
.head{display:flex; flex-direction:column; gap:18px; padding:34px 0 26px}
.eyebrow{font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--hema); font-weight:600}
h1{margin:0; font-size:30px; line-height:1.25; font-weight:700; letter-spacing:-.02em; text-wrap:balance}
.lede{margin:0; max-width:62ch; color:var(--muted); font-size:15px}
.lede b{color:var(--ink); font-weight:600}

.stats{display:flex; flex-wrap:wrap; gap:0; border:1px solid var(--line); border-radius:10px; overflow:hidden; background:var(--sunk)}
.stat{flex:1 1 120px; padding:12px 16px; background:var(--surface); border-right:1px solid var(--line)}
.stat:last-child{border-right:0}
.stat .k{font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--faint); font-weight:600}
.stat .v{font-size:22px; font-weight:600; line-height:1.3}
.stat .v small{font-size:13px; color:var(--muted); font-weight:400}

/* ---- controls ---- */
.bar{position:sticky; top:0; z-index:10; background:color-mix(in srgb, var(--ground) 92%, transparent);
     backdrop-filter:blur(8px); border-bottom:1px solid var(--line); padding:10px 0}
.bar .wrap{display:flex; flex-wrap:wrap; gap:8px; align-items:center}
select,input[type=search],button{
  font-family:inherit; font-size:13px; color:var(--ink); background:var(--surface);
  border:1px solid var(--line-strong); border-radius:7px; padding:7px 10px;
}
input[type=search]{flex:1 1 180px; min-width:140px}
button{cursor:pointer}
button:hover{border-color:var(--hema)}
:focus-visible{outline:2px solid var(--hema); outline-offset:2px}
.count{margin-left:auto; font-size:13px; color:var(--muted)}

/* ---- tally ---- */
.tally{display:flex; gap:8px; align-items:center; flex-wrap:wrap; padding:12px 0 0}
.tally .pill{font-size:12px; padding:4px 10px; border-radius:99px; border:1px solid var(--line-strong); background:var(--surface)}
.tally .pill b{font-family:"IBM Plex Mono",monospace}

/* ---- list ---- */
main{padding:22px 0 80px; display:flex; flex-direction:column; gap:14px}
.card{background:var(--surface); border:1px solid var(--line); border-radius:12px; box-shadow:var(--shadow); overflow:hidden}
.card.marked-good{border-left:3px solid var(--same)}
.card.marked-meh{border-left:3px solid var(--partial)}
.card.marked-bad{border-left:3px solid var(--diff)}
.meta{display:flex; flex-wrap:wrap; gap:6px; align-items:center; padding:11px 16px 0}
.chip{font-size:11px; line-height:1.7; padding:1px 8px; border-radius:5px; background:var(--sunk); color:var(--muted); border:1px solid var(--line)}
.chip.ref{background:var(--hema-soft); color:var(--hema); border-color:transparent; font-weight:500}
.chip.trap{background:var(--eosin-soft); color:var(--eosin); border-color:transparent}
.chip.flag{background:var(--eosin-soft); color:var(--eosin); border-color:transparent}
.chip.v-partial{color:var(--partial); border-color:var(--partial)}
.chip.v-different{color:var(--diff); border-color:var(--diff)}
.chip.ev{background:transparent; border-style:dashed}
.chip.pick{background:var(--hema); color:#fff; border-color:transparent; font-weight:600}
:root[data-theme="dark"] .chip.pick{color:#15121b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .chip.pick{color:#15121b}}
.why{margin:6px 16px 0; padding:8px 12px; border-left:2px solid var(--hema); background:var(--hema-soft);
     border-radius:0 7px 7px 0; font-size:13px; color:var(--ink)}
.card.is-pick{border-color:var(--line-strong)}
.skew{margin:0; padding:12px 14px; border:1px solid var(--eosin); border-left-width:3px;
      border-radius:0 9px 9px 0; background:var(--eosin-soft); font-size:14px}
.skew b{font-weight:600}
.skew .hd{display:block; font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--eosin); font-weight:600; margin-bottom:3px}
.q{padding:8px 16px 14px; font-size:16.5px; font-weight:500; line-height:1.6; white-space:pre-wrap}
.reveal{width:100%; text-align:left; border:0; border-top:1px solid var(--line); border-radius:0;
        background:var(--sunk); color:var(--hema); font-weight:600; font-size:13px; padding:9px 16px}
.reveal:hover{background:var(--hema-soft)}
.back{border-top:1px solid var(--line); padding:14px 16px 4px; display:none; flex-direction:column; gap:10px}
.card.open .back{display:flex}
.card.open .reveal{display:none}
.a{white-space:pre-wrap; font-weight:600; line-height:1.6}
.e{color:var(--muted); font-size:14.5px; white-space:pre-wrap}
.note{border-left:2px solid var(--eosin); background:var(--eosin-soft); color:var(--ink);
      padding:9px 12px; border-radius:0 7px 7px 0; font-size:13.5px; white-space:pre-wrap}
.note .lbl{display:block; font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--eosin); font-weight:600; margin-bottom:2px}
.judge{display:flex; gap:6px; padding:10px 16px 12px; border-top:1px dashed var(--line); margin-top:4px}
.judge button{font-size:12.5px; padding:5px 12px}
.judge button[aria-pressed=true]{background:var(--hema); border-color:var(--hema); color:#fff}
:root[data-theme="dark"] .judge button[aria-pressed=true],
:root:not([data-theme="light"]) .judge button[aria-pressed=true]{color:#15121b}
.empty{padding:60px 0; text-align:center; color:var(--muted)}
footer{border-top:1px solid var(--line); padding:20px 0 40px; color:var(--faint); font-size:12.5px}
@media (max-width:600px){h1{font-size:24px} .stat{flex:1 1 50%}}
@media (prefers-reduced-motion:reduce){*{transition:none!important; animation:none!important}}
</style>

<header><div class="wrap head">
  <div>
    <div class="eyebrow">병리학 · 재생성 12편</div>
    <h1>기출 25~35장이 정말 원하던 물건인가</h1>
  </div>
  <p class="lede">파이프라인이 기출에 <b>자기 계획과 자기 분량</b>을 준 뒤 기출 카드가 편당 <b>9장에서 27장</b>으로 늘었다.
  숫자는 올랐는데 <b>아직 아무도 이 카드를 풀어 보지 않았다.</b> 남은 16편에 $175를 더 쓸지는 이 322장이 결정한다.
  322장을 다 볼 필요는 없다 — 신호 고르개에서 <b>「추린 것」</b>을 고르면 <b>사람이 판정해야 결론이 나는 것</b>만 남는다.
  한 장씩 뒤집어 보고 <b>좋다 / 애매 / 아니다</b>를 누르면, 아래 「판정 복사」로 한 덩어리로 뽑아낼 수 있다.</p>
  <p class="skew" id="skew"></p>
  <div class="stats" id="stats"></div>
  <div class="tally" id="tally"></div>
</div></header>

<div class="bar"><div class="wrap">
  <select id="f-run"></select>
  <select id="f-type"></select>
  <select id="f-mark">
    <option value="">판정 — 전체</option>
    <option value="unmarked">아직 안 본 것</option>
    <option value="good">좋다</option>
    <option value="meh">애매</option>
    <option value="bad">아니다</option>
  </select>
  <select id="f-sig">
    <option value="">신호 — 전체</option>
    <option value="pick">★ 추린 것 — 전부</option>
    <option value="pick:고칠 것">★ 고칠 것</option>
    <option value="pick:대조 끝 · 카드가 맞다">★ 대조 끝 — 카드가 맞았다</option>
    <option value="pick:정답표 대조">★ 정답표 대조</option>
    <option value="pick:연도 어긋남">★ 연도 어긋남</option>
    <option value="pick:나열형 표본">★ 나열형 표본</option>
    <option value="pick:함정 표본">★ 함정 표본</option>
    <option value="pick:의학지식 표본">★ 의학지식 표본</option>
    <option value="ox">O/X 카드만</option>
    <option value="note">검토 메모가 붙은 것</option>
    <option value="medical_knowledge">의학지식으로 메운 것</option>
    <option value="notsame">재현이 same이 아닌 것</option>
    <option value="flag">플래그가 붙은 것</option>
  </select>
  <input type="search" id="f-q" placeholder="본문 · 카드 번호(c090) 검색">
  <button id="reveal-all">모두 펼치기</button>
  <button id="copy">판정 복사</button>
  <span class="count" id="count"></span>
</div></div>

<div class="wrap"><main id="list"></main></div>
<div class="wrap"><footer>
  재생성이 끝난 12편(260812_01 ~ 260814_05)의 <code>items.reproduced.json</code>에서 <code>source_type=jokbo</code>인 카드만 모았다.
  강의록 카드와 <code>exam_hit</code> 태그는 여기 없다. 남은 16편은 아직 옛 산출물이라 담지 않았다.
</footer></div>

<script>
const DATA = __DATA__;
const TYPE_KO = {trap:"함정", fact:"사실", mechanism:"기전", list:"나열", comparison:"비교", sequence:"순서"};
const FLAG_KO = {
  missing_explanation:"해설 없음", jokbo_ref_outside_slice:"조각 밖 연도", similar_duplicate:"비슷한 중복",
  answer_leaked_in_question:"답이 문항에", question_too_long:"문항이 긺", too_many_items:"항목 과다",
  points_at_source:"출처를 가리킴"
};
const EV_KO = {jokbo_question:"기출 문항", jokbo_objection:"이의제기", medical_knowledge:"의학 지식"};
const KEY = "jokbo-review-v1";
let marks = {};
try { marks = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { marks = {}; }
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(marks)); } catch (e) {} };

const el = (t, c, x) => { const n = document.createElement(t); if (c) n.className = c; if (x != null) n.textContent = x; return n; };
const $ = s => document.querySelector(s);

/* ---- 요약 ---- */
const cards = DATA.cards;
const ox = cards.filter(c => c.fmt === "ox");
const oxX = ox.filter(c => c.a.trim() === "X").length;
const stats = [
  ["기출 카드", cards.length, "장 · " + DATA.runs.length + "편"],
  ["추린 것", cards.filter(c => c.pick).length, "장"],
  ["재현 same", cards.filter(c => c.verdict === "same").length, "/ " + cards.length],
  ["검토 메모", cards.filter(c => c.note).length, "장"],
  ["의학 지식", cards.filter(c => c.ev === "medical_knowledge").length, "장"],
];
{
  const s = $("#skew");
  s.append(el("span", "hd", "O/X 쏠림 — 고쳤다"));
  s.append(document.createTextNode(
    "처음 세었을 때 O/X 119장 가운데 X가 113장(95%)이었고 12편 중 8편은 O가 한 장도 없었다. " +
    "기출 함정을 오답 선지에서만 캐서 생긴 쏠림이다. 오답 선지 36장을 한 낱말씩 제자리로 돌려 참인 진술로 세웠고, " +
    "지금은 "));
  s.append(el("b", null, "O " + (ox.length - oxX) + " · X " + oxX));
  s.append(document.createTextNode(
    "다. 고친 36장은 빈 세션이 다시 풀어 35장이 일치했다(나머지 한 장은 「정답 의심」이 붙었다). " +
    "「함정 표본」을 넘겨 보고 어느 것이 고쳐진 것인지 결로 알아볼 수 있는지 봐 달라 — 알아볼 수 있으면 실패다."));
}
for (const [k, v, s] of stats) {
  const d = el("div", "stat");
  d.append(el("div", "k", k));
  const val = el("div", "v"); val.append(el("span", "num", String(v)), " ", el("small", null, s));
  d.append(val); $("#stats").append(d);
}

/* ---- 필터 옵션 ---- */
const opt = (sel, val, txt) => { const o = el("option", null, txt); o.value = val; sel.append(o); };
opt($("#f-run"), "", "편 — 전체 (" + DATA.runs.length + ")");
DATA.runs.forEach(r => opt($("#f-run"), r.run, r.run + " · 기출 " + r.jokbo + "장 / " + r.cards + "장"));
opt($("#f-type"), "", "형태 — 전체");
Object.entries(TYPE_KO).forEach(([k, v]) => {
  const n = cards.filter(c => c.type === k).length;
  if (n) opt($("#f-type"), k, v + " " + n);
});

/* ---- 그리기 ---- */
function build(c) {
  const card = el("article", "card");
  card.dataset.uid = c.uid;
  if (marks[c.uid]) card.classList.add("marked-" + marks[c.uid]);

  if (c.pick) card.classList.add("is-pick");

  const meta = el("div", "meta");
  if (c.pick) meta.append(el("span", "chip pick", "★ " + c.pick));
  meta.append(el("span", "chip ref", c.ref));
  meta.append(el("span", "chip" + (c.type === "trap" ? " trap" : ""), TYPE_KO[c.type] || c.type));
  if (c.imp === "detail") meta.append(el("span", "chip", "지엽"));
  meta.append(el("span", "chip ev", EV_KO[c.ev] || c.ev));
  if (c.verdict !== "same") meta.append(el("span", "chip v-" + c.verdict, "재현 " + c.verdict));
  c.flags.forEach(f => meta.append(el("span", "chip flag", FLAG_KO[f] || f)));
  meta.append(el("span", "chip mono", c.run.slice(2) + " " + c.id));
  card.append(meta);
  if (c.why) card.append(el("div", "why", c.why));
  card.append(el("div", "q", c.q));

  const btn = el("button", "reveal", "답 보기");
  const back = el("div", "back");
  back.append(el("div", "a", c.a));
  if (c.e) back.append(el("div", "e", c.e));
  if (c.note) {
    const n = el("div", "note");
    n.append(el("span", "lbl", "검토 메모"), document.createTextNode(c.note));
    back.append(n);
  }
  const judge = el("div", "judge");
  [["good", "좋다"], ["meh", "애매"], ["bad", "아니다"]].forEach(([k, label]) => {
    const b = el("button", null, label);
    b.setAttribute("aria-pressed", marks[c.uid] === k);
    b.onclick = () => {
      marks[c.uid] === k ? delete marks[c.uid] : marks[c.uid] = k;
      save();
      card.className = "card open" + (marks[c.uid] ? " marked-" + marks[c.uid] : "");
      judge.querySelectorAll("button").forEach((x, i) =>
        x.setAttribute("aria-pressed", marks[c.uid] === ["good", "meh", "bad"][i]));
      tally();
    };
    judge.append(b);
  });
  back.append(judge);
  btn.onclick = () => card.classList.add("open");
  card.append(btn, back);
  return card;
}

function tally() {
  const t = $("#tally"); t.textContent = "";
  const n = k => Object.values(marks).filter(v => v === k).length;
  const seen = Object.keys(marks).length;
  [["본 것", seen + " / " + cards.length], ["좋다", n("good")], ["애매", n("meh")], ["아니다", n("bad")]]
    .forEach(([k, v]) => {
      const p = el("span", "pill"); p.append(k + " ", el("b", null, String(v))); t.append(p);
    });
}

function render() {
  const run = $("#f-run").value, type = $("#f-type").value, mark = $("#f-mark").value,
        sig = $("#f-sig").value, q = $("#f-q").value.trim().toLowerCase();
  const list = $("#list"); list.textContent = "";
  const shown = cards.filter(c => {
    if (run && c.run !== run) return false;
    if (type && c.type !== type) return false;
    if (mark === "unmarked" ? marks[c.uid] : mark && marks[c.uid] !== mark) return false;
    if (sig === "pick" && !c.pick) return false;
    if (sig.startsWith("pick:") && c.pick !== sig.slice(5)) return false;
    if (sig === "ox" && c.fmt !== "ox") return false;
    if (sig === "note" && !c.note) return false;
    if (sig === "medical_knowledge" && c.ev !== "medical_knowledge") return false;
    if (sig === "notsame" && c.verdict === "same") return false;
    if (sig === "flag" && !c.flags.length) return false;
    if (q && !(c.uid + c.q + c.a + c.e + c.note).toLowerCase().includes(q)) return false;
    return true;
  });
  // 추린 것을 위로 올린다. 묶음 순서는 PICKS 에 적은 순서를 따른다.
  const ORDER = ["답 판정", "정답표 대조", "연도 어긋남", "나열형 표본", "함정 표본", "의학지식 표본"];
  shown.sort((a, b) => (a.pick ? ORDER.indexOf(a.pick) : 99) - (b.pick ? ORDER.indexOf(b.pick) : 99));
  shown.forEach(c => list.append(build(c)));
  if (!shown.length) list.append(el("div", "empty", "해당하는 카드가 없다."));
  $("#count").textContent = shown.length + "장";
}

["#f-run", "#f-type", "#f-mark", "#f-sig"].forEach(s => $(s).onchange = render);
$("#f-q").oninput = render;
$("#reveal-all").onclick = () => document.querySelectorAll(".card").forEach(c => c.classList.add("open"));
$("#copy").onclick = async () => {
  const by = k => cards.filter(c => marks[c.uid] === k)
    .map(c => c.uid + (c.pick ? "  [" + c.pick + "]" : "") + "  " + c.q.slice(0, 60));
  const txt = ["# 기출 카드 판정", "",
    "좋다 " + by("good").length + " / 애매 " + by("meh").length + " / 아니다 " + by("bad").length +
    " / 안 본 것 " + (cards.length - Object.keys(marks).length), "",
    "## 애매", ...by("meh"), "", "## 아니다", ...by("bad")].join("\\n");
  try { await navigator.clipboard.writeText(txt); $("#copy").textContent = "복사했다"; }
  catch (e) { $("#copy").textContent = "복사 실패"; }
  setTimeout(() => $("#copy").textContent = "판정 복사", 1600);
};

tally();
render();
</script>
"""

open(out, "w", encoding="utf-8").write(HTML.replace("__DATA__", data))
print("wrote", out, os.path.getsize(out) // 1024, "KB ·", len(cards), "cards ·", len(runs), "runs")
