"""라벨이 맞는지 눈으로 훑는 대조표를 만든다.

    uv run --python 3.13 python scripts/label_sheet.py
    → build/label_sheet.html  (브라우저로 열기)

**틀린 라벨은 흐린 사진보다 나쁘다.** 흐린 사진은 어려운 문제일 뿐이지만,
틀린 라벨은 맞게 고른 사람을 틀렸다고 채점한다. 그런데 라벨이 맞는지는
자동으로 알 방법이 없다 — 선명도·해상도·순백비율·피부색을 다 재 봤지만
어느 것도 "이 사진이 이 종인가"를 말해 주지 않았다.

사람이 봐야 하는데, 973장을 한 장씩 열어 보는 것은 아무도 안 한다. 그래서
**같은 라벨이 붙은 사진을 한 줄에 모아** 놓는다. 그러면 틀린 것이 튄다 —
편충 여섯 장 사이에 낀 조충 한 장은 종을 몰라도 "쟤만 다르게 생겼다"로
보인다. 한 장씩 판정하는 일이 한 줄씩 훑는 일로 바뀐다.

**파일로 만들고 어디에도 올리지 않는다.** 실제실습본은 표지에 반출금지가
적혀 있다. 브라우저로 여는 로컬 파일이면 그 표시를 지킬 수 있다.
"""

import os
import sys
from collections import defaultdict

from jsonio import load_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
DB = os.path.join(BUILD, "quiz_db.json")
OUT = os.path.join(BUILD, "label_sheet.html")

# 사진 경로 앞머리 → 화면에 뜰 출처 이름. 색은 한 줄 안에서 어느 출처가
# 섞여 있는지 바로 보이라고 준다 — 한 라벨에 여러 출처가 모이는 자리가
# 곧 서로를 검산하는 자리다.
SOURCES = [
    ("practical/", "실제실습본", "#b3261e"),
    ("practical_ind", "실제실습본", "#b3261e"),
    ("jiseok/", "이지석", "#2f6f4f"),
    ("eunju/", "신은주", "#7a5cc4"),
    ("note/", "필기본", "#b26a00"),
    ("tonghap/", "실습사진통합", "#1f6f8b"),
    ("jms_", "전민서", "#555f6d"),
    ("questions/", "족보", "#111"),
]


def source_of(path):
    for pre, ko, color in SOURCES:
        if (path or "").startswith(pre):
            return ko, color
    return "?", "#888"


def main():
    if not os.path.isfile(DB):
        raise SystemExit("build/quiz_db.json 이 없습니다. scripts/build_web.py 를 먼저 돌리세요.")
    db = load_json(DB)
    imgs = db["meta"]["images"]

    # 사진 한 장이 어느 표본으로 나가는지. 같은 사진을 쓰는 문항은 라벨이
    # 같으므로 처음 것 하나만 본다.
    label, group, sptype = {}, {}, {}
    for q in db["questions"]:
        name = q["image"]
        if name not in label:
            label[name] = q.get("label") or "(라벨 없음)"
            group[name] = q.get("group") or ""
            sptype[name] = q.get("specimen_type") or ""

    rows = defaultdict(list)
    for name, meta in imgs.items():
        if name not in label:
            continue                       # 문항에 안 쓰이는 사진은 볼 이유가 없다
        rows[label[name]].append((name, meta))

    # 사진이 많은 라벨을 위로. 틀린 것이 섞였을 확률이 그만큼 높고,
    # 한 줄에 여럿이 서야 견주기도 쉽다.
    order = sorted(rows.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    cards = []
    for name_ko, items in order:
        items.sort(key=lambda it: it[1].get("path") or "")
        srcs = {source_of(m.get("path"))[0] for _, m in items}
        one = items[0][0]
        cells = []
        for name, meta in items:
            ko, color = source_of(meta.get("path"))
            cells.append(
                f'<figure><img loading="lazy" src="images/{name}" alt="">'
                f'<figcaption><b style="color:{color}">{ko}</b>'
                f'<span>{meta.get("src", "")}</span></figcaption></figure>')
        cards.append(
            f'<section data-src="{" ".join(srcs)}" data-n="{len(items)}">'
            f'<h2>{name_ko} <em>{group[one]} · {sptype[one]} · {len(items)}장</em></h2>'
            f'<div class="strip">{"".join(cells)}</div></section>')

    html = TEMPLATE.replace("{{CARDS}}", "\n".join(cards)) \
                   .replace("{{N_LABEL}}", str(len(order))) \
                   .replace("{{N_IMG}}", str(sum(len(v) for v in rows.values())))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"{OUT} — 라벨 {len(order)}개 · 사진 {sum(len(v) for v in rows.values())}장")
    print("브라우저로 열어서, 한 줄 안에 혼자 다르게 생긴 사진을 찾으면 됩니다.")


TEMPLATE = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>라벨 대조표 — 기생충학 땡시</title>
<style>
 body{margin:0;background:#14161a;color:#e9ecf1;
   font:14px/1.5 -apple-system,"Segoe UI","Malgun Gothic",sans-serif}
 header{position:sticky;top:0;z-index:5;background:#14161a;border-bottom:1px solid #2c313a;
   padding:12px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
 h1{font-size:15px;margin:0 12px 0 0}
 .sub{color:#9aa3af;font-size:12px}
 button{font:inherit;font-size:12.5px;cursor:pointer;border:1px solid #2c313a;background:#1c1f24;
   color:#e9ecf1;padding:5px 11px;border-radius:999px}
 button.on{border-color:#6cc196;color:#6cc196}
 section{border-top:1px solid #2c313a;padding:14px 16px}
 h2{font-size:15px;margin:0 0 8px;font-weight:600}
 h2 em{font-style:normal;color:#9aa3af;font-size:12px;font-weight:400;margin-left:8px}
 .strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}
 figure{margin:0;flex:none;width:190px}
 figure img{width:190px;height:190px;object-fit:contain;background:#0b0d10;border-radius:8px;
   cursor:zoom-in}
 figcaption{font-size:10.5px;color:#9aa3af;line-height:1.35;margin-top:4px;
   display:flex;flex-direction:column;gap:1px}
 figcaption span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .zoom{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;align-items:center;
   justify-content:center;z-index:9;cursor:zoom-out;padding:20px}
 .zoom img{max-width:100%;max-height:100%}
 .zoom.on{display:flex}
</style></head><body>
<header>
  <h1>라벨 대조표</h1>
  <span class="sub">라벨 {{N_LABEL}}개 · 사진 {{N_IMG}}장 —
    한 줄 안에서 <b>혼자 다르게 생긴 것</b>을 찾으세요</span>
  <span style="flex:1"></span>
  <button data-f="all" class="on">전체</button>
  <button data-f="이지석">이지석</button>
  <button data-f="신은주">신은주</button>
  <button data-f="필기본">필기본</button>
  <button data-f="실제실습본">실제실습본</button>
</header>
{{CARDS}}
<div class="zoom" id="z"><img id="zi" alt=""></div>
<script>
 // 한 출처만 보기. 그 출처가 낀 줄만 남긴다 — 옆에 다른 출처 사진이 같이
 // 서 있어야 견줄 수 있으므로 줄에서 사진을 빼지는 않는다.
 document.querySelectorAll('header button').forEach(function(b){
   b.onclick = function(){
     document.querySelectorAll('header button').forEach(function(x){x.classList.remove('on')});
     b.classList.add('on');
     var f = b.dataset.f;
     document.querySelectorAll('section').forEach(function(s){
       s.hidden = (f !== 'all') && s.dataset.src.indexOf(f) < 0;
     });
   };
 });
 var z = document.getElementById('z'), zi = document.getElementById('zi');
 document.addEventListener('click', function(e){
   if (e.target.tagName === 'IMG' && e.target.closest('figure')) {
     zi.src = e.target.src; z.classList.add('on');
   } else if (z.classList.contains('on')) { z.classList.remove('on'); }
 });
 document.addEventListener('keydown', function(e){
   if (e.key === 'Escape') z.classList.remove('on');
 });
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
