"""해부학 과목 앱을 한 판(`web/anatomy/_template.html`)에서 찍어 낸다.

    uv run --python 3.13 python scripts/build_anatomy.py           찍는다
    uv run --python 3.13 python scripts/build_anatomy.py --check   다른지만 본다

## 왜 한 판인가

**2026-09-14 에 세어 보니 셋이 사본이었다.** `trunk` 과 `head-neck` 은 635줄 중
**네 줄**만 다르고(제목·번호·표제·과목 키), `exam1` 은 거기에 핀 표시 기능이
붙은 것이었다. 사본 셋을 손으로 고치는 동안 하나가 뒤처져도 아무도 모른다.

실제로 그랬다. `loadQuestion` 안의 사진 한 줄을 `exam1` 만 고쳐서, **`trunk` 과
`head-neck` 은 본문 사진이 안 나오는 채로 배포돼 있었다** — 없는 상대경로
`Spotter_Questions_All/…` 를 부르고 있었다. 사본이 셋이 아니었으면 못 생길 버그다.

`neuro` 는 여기 안 들어온다. 989줄이고 트렁크 계열과 1,586줄이 다르다 — **다른
앱이다.** 억지로 한 판에 넣으면 판이 두 앱을 다 아는 괴물이 된다.

## 판 문법

자리표시자와 갈래 둘이 전부다. 더 늘리지 마라 — 판이 언어가 되기 시작하면
사본 셋보다 나쁘다.

    {{TITLE}}  {{NAV}}  {{HEADING}}  {{SUBJECT}}      과목마다 다른 글자

    {{#if marker}} … {{else}} … {{/if}}               핀 표시를 쓰는 과목만

지시줄(`{{#if …}}`·`{{else}}`·`{{/if}}`)은 **제 줄을 통째로 차지하고 출력에서
사라진다.** 그래서 판을 읽을 때 들여쓰기가 한 칸도 안 밀린다.
"""

import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANATOMY = os.path.join(ROOT, "web", "anatomy")
TEMPLATE = os.path.join(ANATOMY, "_template.html")
SUBJECTS = os.path.join(ANATOMY, "subjects.json")

DIRECTIVE = re.compile(r"^\{\{(#if (\w+)|else|/if)\}\}$")


def render(template, flags, values):
    """지시줄을 접고 자리표시자를 채운다.

    **중첩은 안 된다.** 지금 필요한 것이 한 겹이고, 중첩을 허용하면 판을 읽는
    사람이 갈래를 머릿속에서 세게 된다. 필요해지면 그때 늘린다.
    """
    out, keep, seen_if = [], True, False
    for n, line in enumerate(template.split("\n"), 1):
        m = DIRECTIVE.match(line.strip())
        if not m:
            if keep:
                out.append(line)
            continue
        head = m.group(1)
        if head.startswith("#if"):
            if seen_if:
                raise SystemExit(f"{n}행: 갈래 안에 갈래를 넣지 마라")
            seen_if, keep = True, bool(flags.get(m.group(2)))
        elif head == "else":
            if not seen_if:
                raise SystemExit(f"{n}행: 짝 없는 {{{{else}}}}")
            keep = not keep
        else:
            if not seen_if:
                raise SystemExit(f"{n}행: 짝 없는 {{{{/if}}}}")
            seen_if, keep = False, True
    if seen_if:
        raise SystemExit("{{/if}} 가 모자란다")

    text = "\n".join(out)
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    left = re.findall(r"\{\{[^}]+\}\}", text)
    if left:
        raise SystemExit(f"안 채운 자리표시자: {sorted(set(left))}")
    return text


def main():
    check = "--check" in sys.argv
    with open(TEMPLATE, encoding="utf-8") as fh:
        template = fh.read()
    with open(SUBJECTS, encoding="utf-8") as fh:
        subjects = json.load(fh)

    stale = []
    for name, conf in subjects.items():
        if name.startswith("_"):   # `_note` 처럼 사람에게 하는 말
            continue
        body = render(template, conf.get("flags", {}), conf["values"])
        dest = os.path.join(ANATOMY, name, "index.html")
        old = None
        if os.path.isfile(dest):
            with open(dest, encoding="utf-8") as fh:
                old = fh.read()
        if old == body:
            print(f"  같음     {name}")
            continue
        stale.append(name)
        if check:
            print(f"  다름     {name}")
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="") as fh:
            fh.write(body)
        print(f"  찍었음   {name}")

    if check and stale:
        raise SystemExit(
            "\n판에서 찍은 것과 파일이 다릅니다: " + ", ".join(stale) + "\n"
            "파일을 손으로 고쳤다면 그 고침을 판으로 옮기세요. "
            "판이 맞다면 인자 없이 다시 돌리세요."
        )


if __name__ == "__main__":
    main()
