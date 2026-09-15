"""필기본이 새 판으로 갈렸을 때 **갈린 슬라이드의 카드만** 갈아 끼운다.

관리자 지시(2026-09-03): *"강의록 버전이 바뀐 경우, 바뀐 부분만 체크하여 카드를
교체하는 코드를 만드는건 어때? 너무 많이 바뀐 경우에만 새로 하고."*

## 왜 통째로 다시 만들면 안 되는가

guid 가 `(강의 ID, 정규화한 질문)` 에서 나온다(`build.guid_of`). 질문 글자가 한 자라도
달라지면 Anki 는 **새 노트**로 받고 그 카드의 복습 이력이 죽는다. `260903_05` 의
v1(53장)과 v2(50장)를 실제 `guid_of` 로 맞대 보면 **7장(13%)만 살아남았다** —
그것도 전부 「이 사진을 판독하라」 꼴의 형식이 정해진 이미지 카드였고, 산문 질문은
거의 하나도 안 살아남았다. 모델은 실행마다 질문을 사실상 새로 쓴다.

그래서 여기서는 **갈리지 않은 슬라이드의 카드를 글자 그대로 옮긴다.** 옮긴 카드는
질문이 같으니 guid 가 같고, Anki 가 같은 노트의 갱신으로 받는다.

## 카드를 세 갈래로 가른다

    안 갈린 슬라이드      그대로 옮긴다. 모델이 보지도 않는다
    갈린 슬라이드         모델에게 **카드마다** 처분을 묻는다 — keep / revise / drop
    없어진 슬라이드       근거가 사라졌으므로 뺀다

**가운데가 실측에서 나왔다.** 처음에는 갈린 슬라이드의 카드를 통째로 버리고 다시
쓰게 했는데, 여섯 쌍(2026-09-04)을 재 보니 그렇게 버려질 16장 중 **8장이 오타
수정이나 형광펜 하나** 때문이었다. `260903_01` 이 그 편이다 — `facificum` →
`pacificum`, `유구조충` → `유구조충증` 같은 표기 수정이고, 카드는 이미 바르게
적고 있었다. 다시 쓰면 **질문 글자가 달라져 이력만 죽는다.**

그래서 갈린 자리의 카드도 안 버리고, 무엇이 어떻게 갈렸는지(v1 문구 → v2 문구)와
그 자리의 카드를 같이 보여 준 뒤 카드마다 처분을 받는다. 관리자가 정한 갈래가
`prompts/revise.md` 의 표다 — 오타·족보답은 확인만, 내용 정정은 확인하고 재생성,
필기·표시 추가는 카드 추가 검토.

옮기는 카드에는 손을 안 댄다. 딱 둘만 고친다.

    slide_no      슬라이드가 밀렸으면 새 번호로  (질문 글자가 아니라 guid 밖의 값이다)
    media 의 id   `fig_p07_01` 은 쪽 번호를 품는다. 같이 밀어 준다

## 슬라이드가 늘어나는 경우

**끼는 것이 실제로 있다**(관리자, 2026-09-04). 그래서 번호로 맞대지 않는다 —
`slidediff` 가 본문으로 짝을 짓고, 뒤로 밀린 슬라이드의 카드는 `slide_no` 와
그림 id 를 같이 밀어서 옮긴다. 끼었다는 이유로 뒤 카드를 버리지 않는다.

## 너무 많이 갈렸으면 통째로 — **거의 안 쓰는 길이다**

관리자 판정(2026-09-04): *"'너무 많이 바뀌면 통째로'는 거의 없을 거야."*
그래서 문턱은 **기본이 없음**이고, 값도 정하지 않는다(CLAUDE.md ① — 근거 없는 규칙은
안 쓴다). `--full-rebuild-over 0.5` 처럼 사람이 줄 때만 그리로 간다.

문턱이 없어도 값이 커질수록 갈아 끼우기는 저절로 통째 재빌드에 가까워진다 — 옮길
카드가 그만큼 없기 때문이다. **다만 한 가지가 다르다:** 이 길은 ①목표와 ②카드를
**한 세션에서** 쓰고 사람 승인 칸이 없다. 갈린 자리가 몇 장일 때를 보고 만든 모양이라,
편의 대부분이 갈린 날에는 그 두 칸을 도로 세우는 편이 나을 수 있다. 그때 쓰라고
깃발을 남겨 둔다.

## 부르는 법

    python -m quizgen.run "새판.pdf" --resume runs/260902_02 --revise
    python -m quizgen.run "새판.pdf" --resume runs/260902_02 --revise --slides 37

두 번째가 **사람이 알려준 경우**다 — "37p 에서 폐흡충이 duodenum 이 아니라 폐에서
성충이 된다고 고쳤습니다" 처럼. 코드가 못 보는 갈림(그림 픽셀만 바뀐 것)이 그리로 들어온다.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter
from pathlib import Path

from . import slidediff
from .run import Runner
from .runbase import Failed
from .schema import CARD_SCHEMA, IMAGE_FORMATS

# 카드에 남겨도 되는 키. `items.reproduced.json` 의 카드는 `reproduce` 를 달고 있는데
# 계약이 `additionalProperties: false` 라 그대로 옮기면 **검증이 통째로 떨어뜨린다.**
CARD_KEYS = tuple(CARD_SCHEMA["properties"])

# 갈아 끼울 때 남겨 두는 옛 판의 산출물. JSON 만 뜬다 — PDF 는 다시 만들 수 있다.
KEEP = ("prep.json", "prep.md", "plan.json", "plan.approved.json", "items.raw.json",
        "items.checked.json", "items.reproduced.json", "suspects.json",
        "reproduce.answers.json", "reproduce.grades.json", "run.config.json",
        "run.report.json", "revise.json")

_ID_PAGE = re.compile(r"_p(\d+)_")
_NUM = re.compile(r"(\d+)")


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def source_cards(out: Path) -> list[dict]:
    """옛 판의 카드. 가장 뒤 단계의 것부터 찾는다."""
    for name in ("items.reproduced.json", "items.checked.json", "items.raw.json"):
        got = _load(out / name)
        if isinstance(got, dict) and got.get("cards"):
            return got["cards"]
    return []


def remap_media(card: dict, old_slide: int, new_slide: int) -> dict:
    """`fig_p07_01` · `occ_p07_02` 의 쪽 번호를 새 번호로 민다.

    옮기는 카드는 그림의 개수와 자리가 같은 슬라이드의 것뿐이므로(`slidediff` 가
    그것을 확인했다) 번호만 밀면 같은 그림을 가리킨다.
    """
    media = card.get("media")
    if not media:
        return card
    def shift(value: str) -> str:
        return _ID_PAGE.sub(lambda m: f"_p{new_slide:02d}_", value, count=1)
    media = dict(media)
    if media.get("figure_id"):
        media["figure_id"] = shift(str(media["figure_id"]))
    if media.get("occlusion_ids"):
        media["occlusion_ids"] = [shift(str(x)) for x in media["occlusion_ids"]]
    card["media"] = media
    return card


def _move(card: dict, old_slide: int, new_slide: int) -> dict:
    if new_slide != old_slide:
        card["slide_no"] = new_slide
        remap_media(card, old_slide, new_slide)
    return card


def split_cards(cards: list[dict], d: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """(그대로 옮길 것, 모델이 볼 것, 자리가 없어진 것).

    **가운데가 이번 실측으로 생긴 갈래다.** 예전에는 갈린 슬라이드의 카드를 통째로
    버리고 다시 쓰게 했는데, 6쌍을 재 보니 그렇게 버려지는 16장 중 8장이 **오타
    수정이나 형광펜 하나** 때문이었다(`260903_01`). 그 카드들은 이미 옳고, 다시 쓰면
    질문 글자가 달라져 **이력만 죽는다.**

    그래서 갈린 슬라이드의 카드도 버리지 않고 모델에게 보여 준다. 카드마다
    「그대로 / 고침 / 버림」을 받는다(`merge_back`). 기본값은 **그대로**다.

    **기출 카드(`slide_no` 가 없는 것)는 언제나 그대로 둔다.** 근거가 강의록이 아니라
    기출 문항에 서 있어서 강의록이 갈려도 안 움직인다. 필기에 적힌 족보 답이 고쳐진
    경우도 마찬가지다 — 기출 카드는 과목 족보 조각에서 나오지 필기 부록에서 나오지
    않는다(6쌍 중 두 편이 그 경우였다).
    """
    carry_map, slide_map = d["carry_map"], d["slide_map"]
    keep, review, orphan = [], [], []
    for card in cards:
        slim = {k: v for k, v in card.items() if k in CARD_KEYS}
        slide = slim.get("slide_no")
        if slide is None:
            keep.append(slim)
            continue
        key = str(slide)
        if key in carry_map:
            keep.append(_move(slim, slide, carry_map[key]))
        elif key in slide_map:
            review.append(_move(slim, slide, slide_map[key]))
        else:
            orphan.append(slim)          # 그 슬라이드가 새 판에 없다
    return keep, review, orphan


def split_plan(plan: dict, d: dict) -> tuple[dict, list[dict]]:
    """계획의 슬라이드 번호를 새 판으로 민다. **목표는 웬만하면 안 버린다.**

    갈린 슬라이드의 목표까지 내리던 판이 있었는데, 그러면 그 자리에서 살아남은 카드의
    `objective_id` 가 **없는 목표를 가리킨다** — 계획과 카드를 잇는 끈이 거기서 끊긴다.
    버리는 것은 슬라이드 자체가 새 판에서 없어진 목표뿐이다.
    """
    slide_map = d["slide_map"]
    kept, dropped = [], []
    for obj in plan.get("objectives") or []:
        slides = obj.get("slides") or []
        moved = [slide_map.get(str(s)) for s in slides]
        if slides and all(m is not None for m in moved):
            kept.append(dict(obj, slides=moved))
        else:
            dropped.append(obj)
    survivors = dict(plan)
    survivors["objectives"] = kept
    return survivors, dropped


def change_block(d: dict, old_prep: dict, new_prep: dict,
                 review: list[dict], plan: dict) -> str:
    """갈린 슬라이드마다 **판단에 필요한 것 셋**을 한자리에 편다.

        무엇이 어떻게 갈렸는가   v1 문구 → v2 문구 (`slidediff.detail`)
        그 자리에 있는 카드      질문·정답 그대로. 처분을 답할 대상이다
        v1 은 그 자리를 어땠나   목표가 있었나, 일부러 뺐나, 원래 카드가 없었나

    셋째가 실측에서 나왔다. 갈린 슬라이드 17장 중 **10장이 원래 카드가 없던 자리**
    였고(표지·인사말·부록), `260902_02` 의 37쪽은 v1 계획이 `out_of_scope` 로
    **일부러 뺀** 자리였다. 그 판단을 안 보여 주면 갈아 끼우기가 그것을 모르고
    없던 카드를 새로 만든다.
    """
    old_pages = {p["slide"]: p for p in old_prep["pages"]}
    new_pages = {p["slide"]: p for p in new_prep["pages"]}
    by_slide: dict[int, list[dict]] = {}
    for card in review:
        by_slide.setdefault(card["slide_no"], []).append(card)

    objectives = plan.get("objectives") or []
    rejected = plan.get("rejected_candidates") or []
    slide_map = d["slide_map"]

    L = ["## 갈린 슬라이드", ""]
    for pair in d["pairs"]:
        if not pair["changed"]:
            continue
        old_no, new_no = pair["old"], pair["new"]
        L.append(f"### Slide {new_no}" + (f"  (옛 판의 {old_no}쪽)" if pair["moved"] else ""))
        L += slidediff.detail(old_pages[old_no], new_pages[new_no], pair["changed"])
        L.append("")
        here = by_slide.get(slide_map.get(str(old_no), new_no), [])
        if here:
            L.append(f"**이 자리의 기존 카드 {len(here)}장** — 카드마다 처분을 답해라.")
            for card in here:
                L.append(f"- `{card['id']}` [{card['card_format']}] Q. {card['q']}")
                L.append(f"      A. {str(card['a'])[:300]}")
        else:
            L.append("**이 자리에는 카드가 없다.**")
        mine = [o for o in objectives if new_no in (o.get("slides") or [])]
        if mine:
            L.append("v1 이 세운 목표: "
                     + " · ".join(f"`{o.get('id')}` {o['objective']}" for o in mine))
        out = [r for r in rejected if old_no in (r.get("slides") or [])]
        for r in out:
            L.append(f"⚠ v1 은 이 자리를 **일부러 뺐다** — {r['candidate'][:120]} "
                     f"(`{r['reason']}`)")
        if not mine and not out and not here:
            L.append("v1 은 이 자리를 목표로 삼지도, 제외 기록에 적지도 않았다.")
        L.append("")

    for n in d["added"]:
        page = new_pages[n]
        L.append(f"### Slide {n}  (새 판에서 새로 생긴 슬라이드)")
        L.append(f"    · 본문 {'있음' if (page.get('lecture_text') or '').strip() else '없음'}"
                 f" · 필기 {len(page.get('annotations') or [])}개"
                 f" · 그림 {len(page.get('lecture_figures') or [])}개")
        L.append("")
    if d["removed"]:
        L.append(f"### 없어진 슬라이드 (옛 번호) {d['removed']}")
        L.append("그 자리의 카드는 근거가 사라졌다. 코드가 이미 뺐다.")
        L.append("")
    return "\n".join(L)


def next_number(used: list[str], prefix: str) -> int:
    """`c095` 다음은 96. **지워진 카드의 번호까지 피한다.**

    옛 채점 결과(`reproduce.grades.json`)는 지운 카드의 id 를 그대로 들고 있다.
    번호를 다시 쓰면 `apply` 가 **없어진 카드의 채점을 새 카드에 붙인다.**
    """
    top = 0
    for value in used:
        if not value or not str(value).startswith(prefix):
            continue
        m = _NUM.search(str(value))
        if m:
            top = max(top, int(m.group(1)))
    return top + 1


def used_ids(out: Path, cards: list[dict]) -> list[str]:
    """이 폴더가 지금까지 쓴 카드 id 전부 (지워진 것 포함)."""
    seen = [str(c.get("id") or "") for c in cards]
    for name, key in (("reproduce.grades.json", "grades"),
                      ("reproduce.answers.json", "answers")):
        got = _load(out / name)
        if isinstance(got, dict):
            seen += [str(r.get("id") or "") for r in got.get(key) or []]
    return seen


def snapshot(out: Path, tag: str) -> Path:
    """옛 판의 산출물을 `revisions/` 로 뜬다. 갈아 끼운 뒤 되짚을 자리다."""
    dest = out / "revisions" / tag
    dest.mkdir(parents=True, exist_ok=True)
    for name in KEEP:
        src = out / name
        if src.exists():
            shutil.copy2(src, dest / name)
    return dest


class ReviseRunner(Runner):
    """판이 갈린 편을 갈아 끼운다. 못 갈아 끼우면 통째로 다시 만든다.

    `Runner` 의 단계를 그대로 쓴다 — 검증·누출 수선·재현 검사·수선·빌드는 **새로
    만드는 것과 같아야 한다.** 다른 것은 앞의 세 칸뿐이다: 판을 비교하고, 남길
    카드를 고르고, 갈린 자리만 모델에게 다시 쓰게 한다.
    """

    def __init__(self, out: Path, args):
        super().__init__(out, args)
        self.full = False          # 통째로 다시 만들기로 했는가
        self.diff: dict = {}
        self.new_ids: list[str] = []
        self.carried = 0
        prior = getattr(args, "revise_from", "") or ""
        self.prior = Path(prior) if prior else out

    def carry_in(self):
        """옛 판의 산출물을 이번 판 폴더로 들여온다.

        **이 단계가 있는 이유는 판 폴더다.** 옛 모양에서는 `--out` 이 강의 폴더라
        옛 판의 `prep.json` 과 카드가 그 자리에 그대로 있었고, `compare` 는 그것을
        읽으면 됐다. 판마다 폴더를 가르고 나서는 **이번 판이 빈 폴더**라 그대로 두면
        `compare` 가 「옛 판의 산출물이 없다」로 읽는다.

        그러면 조용히 통째로 다시 만들기로 내려가고, **질문 글자가 달라져 복습 이력이
        죽는다**(`260903_05` 실측: 53장 중 7장만 살아남았다). `--revise` 가 있는
        이유가 그것이므로 이 길로 새면 안 된다.

        들여온 뒤로는 옛 모양과 같은 자리가 되어 아래 단계가 한 글자도 안 바뀐다.
        `--force`(통째로)로 내려가면 `runbase.step` 이 단계마다 지우고 다시 만든다.
        """
        if self.prior.resolve() == self.out.resolve():
            return                      # 옛 모양이거나 --resume — 이미 그 자리다
        got = [name for name in KEEP if (self.prior / name).exists()]
        for name in got:
            shutil.copy2(self.prior / name, self.out / name)
        print(f"   옛 판을 들여왔다 ← {self.prior.as_posix()} ({len(got)}개)", flush=True)

    # ── 판 비교 ────────────────────────────────────────────────
    def compare(self):
        self.carry_in()
        old_prep = _load(self.out / "prep.json")
        old_cards = source_cards(self.out)
        if not old_prep or not old_cards:
            print("   옛 판의 산출물이 없다 (prep.json 또는 카드). 통째로 만든다.", flush=True)
            self.full = True
            # **새 판으로 다시 읽게 한다.** 안 그러면 옛 prep.json 이 남아 있는 자리에서
            # 그 단계를 건너뛰고 **옛 판의 사이드카로 새 덱을 만든다.**
            self.args.force = True
            return

        old_ver = re.search(r"v(\d+)", old_prep.get("source", "") or "")
        tag = f"v{old_ver.group(1) if old_ver else '0'}_{time.strftime('%y%m%d-%H%M')}"
        kept_at = snapshot(self.out, tag)
        print(f"   옛 판을 떠 뒀다 → {kept_at.as_posix()}", flush=True)

        self.prep()                     # 새 판으로 prep.json 을 다시 쓴다
        new_prep = _load(self.out / "prep.json")
        if not new_prep:
            raise Failed("새 판의 prep.json 을 못 읽었다")

        self.diff = slidediff.diff(old_prep, new_prep, self.args.slides)
        report = slidediff.render(self.diff)
        (self.out / "revise.md").write_text(report, encoding="utf-8")
        print(report, flush=True)
        if self.diff["hinted_missing"]:
            print(f"   ⚠ 알려준 슬라이드 {self.diff['hinted_missing']} 가 새 판에 없다. "
                  "번호를 확인해라.", flush=True)

        over = self.args.full_rebuild_over
        if over is not None and self.diff["ratio"] > over:
            print(f"   갈린 비율 {self.diff['ratio']:.0%} > {over:.0%} — 통째로 다시 만든다.",
                  flush=True)
            self.full = True
            self.args.force = True      # 산출물이 있어도 전 단계를 다시 돈다
            return

        keep, review, orphan = split_cards(old_cards, self.diff)
        self.carried = len(keep)
        plan = _load(self.out / "plan.approved.json") or _load(self.out / "plan.json") or {}
        plan = plan.get("learning_plan", plan)
        survivors, dropped = split_plan(plan, self.diff)

        (self.out / "items.carry.json").write_text(
            json.dumps({"cards": keep}, ensure_ascii=False, indent=1), encoding="utf-8")
        (self.out / "items.review.json").write_text(
            json.dumps({"cards": review}, ensure_ascii=False, indent=1), encoding="utf-8")
        (self.out / "plan.carry.json").write_text(
            json.dumps(survivors, ensure_ascii=False, indent=1), encoding="utf-8")
        self.diff["prompt_block"] = change_block(self.diff, old_prep, new_prep, review, survivors)
        (self.out / "revise.json").write_text(
            json.dumps(self.diff, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"   카드 {len(old_cards)}장 = 그대로 {len(keep)}장 + 처분을 물을 것 "
              f"{len(review)}장" + (f" + 자리가 없어진 것 {len(orphan)}장" if orphan else ""),
              flush=True)
        print(f"   목표 {len(survivors['objectives'])}개 유지"
              + (f" · {len(dropped)}개는 슬라이드가 없어져 내렸다" if dropped else ""), flush=True)
        for card in orphan:
            print(f"      뺀다 [{card['id']}] slide {card['slide_no']} {card['q'][:52]}",
                  flush=True)
        if not self.diff["changed_slides"]:
            print("   갈린 슬라이드가 없다 — 카드는 그대로 두고 덱만 다시 굽는다.", flush=True)

    # ── 갈린 자리만 다시 쓴다 ──────────────────────────────────
    def assemble(self):
        # **통째로 만들기로 했으면 `revise.json` 이 없다.** `all()` 이 `super().all()`
        # 로 내려가도 파이썬은 이 덮어쓴 메서드를 부르므로, 여기서 갈라 주지 않으면
        # 없는 파일을 `--revise` 로 넘겨 `assemble` 이 FileNotFoundError 로 죽는다
        # (2026-09-15 `260831_02`). 클래스 머리가 적어 둔 대로 **새로 만드는 것과
        # 같아야 한다.**
        if self.full:
            super().assemble()
            return
        argv = ["quizgen.assemble", str(self.out), "--jokbo-dir", self.args.jokbo_dir,
                "--strategy", self.strategy, "--domain", self.args.domain,
                "--revise", str(self.out / "revise.json")]
        if self.args.jokbo:
            argv += ["--jokbo", self.args.jokbo]
        self.sh(*argv)

    def rewrite(self):
        (self.out / "revise.out.json").unlink(missing_ok=True)
        self.agent(f"{self.prompt_path('revise').resolve().as_posix()} 를 읽고 "
                   "그 안의 지시를 그대로 수행해라. 끝나면 목표 몇 개·카드 몇 장을 "
                   "어느 슬라이드에 냈는지 한 줄로만 보고해라.",
                   "판교체")

    def merge_back(self):
        """처분대로 합쳐 `items.raw.json` 을 만든다.

        갈린 슬라이드의 카드는 셋 중 하나가 된다.

            keep    글자 하나 안 건드린다 → guid 가 살아 이력이 이어진다 (**기본값**)
            revise  모델이 낸 카드로 갈아 끼운다 → 질문이 달라지면 그 카드의 이력은 죽는다
            drop    뺀다

        **기본값이 keep 인 이유**는 실측이다. 6쌍에서 갈린 슬라이드의 카드 16장 중
        8장이 오타·형광펜 때문에 걸린 것이었다. 모델이 아무 말도 안 한 카드를 버리는
        쪽으로 두면 그런 카드의 이력이 조용히 죽는다. 대신 **말 없이 남은 카드는
        화면에 적는다** — 조용히 남는 것도 조용히 사라지는 것만큼 나쁘다.

        **id 는 코드가 박는다.** 이 뒤의 모든 단계가 id 로 짝을 맞추는데
        `reproduce.assign_ids` 는 빈 id 를 **순서대로** 채운다. 옮긴 카드가 섞인
        자리에서 그대로 두면 새 카드가 남의 번호를 가져간다.
        """
        keep = (_load(self.out / "items.carry.json") or {}).get("cards", [])
        review = (_load(self.out / "items.review.json") or {}).get("cards", [])
        plan = _load(self.out / "plan.carry.json") or {"objectives": []}
        fresh = _load(self.out / "revise.out.json") or {}
        if isinstance(fresh, dict) and "cards" not in fresh and "learning_plan" in fresh:
            fresh = fresh["learning_plan"]          # 감싸개를 쓰고 나오는 경우가 있다
        new_objs = list(fresh.get("objectives") or [])
        verdicts = {str(v.get("id")): str(v.get("verdict") or "keep")
                    for v in fresh.get("verdicts") or []}

        # ① 새 목표에 진짜 번호를 준다. 모델이 붙인 임시 id 는 카드가 가리키는 이름이다.
        alive = {str(o.get("id")) for o in plan.get("objectives") or [] if o.get("id")}
        start = next_number([o.get("id") for o in plan.get("objectives") or []], "o")
        rename: dict[str, str] = {}
        for i, obj in enumerate(new_objs):
            temp = str(obj.get("id") or "")
            obj["id"] = f"o{start + i:02d}"
            # 임시 id 가 살아 있는 목표의 번호와 겹치면 **바꾸지 않는다.** 그 이름을
            # 가리키는 카드는 남아 있는 목표를 가리킨 것일 수 있고, 여기서 갈아 끼우면
            # 계획과 카드의 끈이 조용히 엉뚱한 데로 옮겨 붙는다.
            if temp and temp not in alive:
                rename[temp] = obj["id"]

        def clean(card: dict) -> dict:
            slim = {k: v for k, v in card.items() if k in CARD_KEYS}
            if slim.get("objective_id") in rename:
                slim["objective_id"] = rename[slim["objective_id"]]
            return slim

        # ② 모델이 낸 카드를 「고친 것」과 「새로 쓴 것」으로 가른다.
        known = {str(c["id"]): c for c in review}
        fixed: dict[str, dict] = {}
        made, refused = [], []
        allowed = set(self.diff["changed_slides"])
        for card in fresh.get("cards") or []:
            slim = clean(card)
            cid = str(slim.get("id") or "")
            if cid in known:
                fixed[cid] = slim
                continue
            slim.pop("id", None)
            if slim.get("source_type") != "lecture" or slim.get("slide_no") not in allowed:
                refused.append(slim)     # 갈린 슬라이드 밖 — 그 자리 카드는 이미 있다
                continue
            made.append(slim)

        # ③ 처분대로 고른다.
        settled, tally, silent = [], Counter(), []
        for card in review:
            cid = str(card["id"])
            call = verdicts.get(cid, "keep")
            if cid in fixed:
                settled.append(dict(fixed[cid], id=cid))
                tally["revise"] += 1
                continue
            if call == "drop":
                tally["drop"] += 1
                print(f"      뺀다 [{cid}] {card['q'][:60]}", flush=True)
                continue
            if call == "revise":
                # 「고치겠다」고 해 놓고 카드를 안 냈다. 버리지 않고 그대로 둔다.
                print(f"   ⚠ [{cid}] 를 고친다고 했는데 카드가 안 왔다 — 그대로 둔다", flush=True)
            elif cid not in verdicts:
                silent.append(cid)
            settled.append(card)
            tally["keep"] += 1

        # ④ 새 카드에 번호를 준다. 지워진 카드의 번호는 피한다.
        start = next_number(used_ids(self.out, keep + review), "c")
        for i, card in enumerate(made):
            card["id"] = f"c{start + i:03d}"
        # 다시 검사할 것은 **글자가 달라진 카드뿐**이다. 그대로 둔 카드의 판정은 산다.
        self.new_ids = [c["id"] for c in made] + sorted(fixed)

        merged = keep + settled + made
        merged.sort(key=lambda c: (c.get("slide_no") is None, c.get("slide_no") or 0))
        (self.out / "items.raw.json").write_text(
            json.dumps({"cards": merged}, ensure_ascii=False, indent=1), encoding="utf-8")

        plan["objectives"] = (plan.get("objectives") or []) + new_objs
        plan["rejected_candidates"] = ((plan.get("rejected_candidates") or [])
                                       + list(fresh.get("rejected_candidates") or []))
        (self.out / "plan.approved.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")

        # 무엇을 왜 그렇게 했는지 남긴다. **갈림의 성격 분류가 여기 쌓인다** —
        # 나중에 그 분포를 세면 어떤 갈림이 카드를 실제로 흔드는지 알 수 있다.
        (self.out / "revise.report.json").write_text(json.dumps({
            "changed_slides": self.diff["changed_slides"],
            "slides": fresh.get("slides") or [],
            "verdicts": fresh.get("verdicts") or [],
            "silent": silent, "refused": len(refused),
            "counts": {"carried": len(keep), "reviewed": len(review),
                       "kept": tally["keep"], "revised": tally["revise"],
                       "dropped": tally["drop"], "added": len(made),
                       "total": len(merged)},
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        for row in fresh.get("slides") or []:
            print(f"   Slide {row.get('slide')}: {row.get('change_kind')} — "
                  f"{str(row.get('note') or '')[:70]}", flush=True)
        print(f"   그대로 {len(keep) + tally['keep']}장 (그중 갈린 자리 {tally['keep']}장) · "
              f"고침 {tally['revise']}장 · 뺌 {tally['drop']}장 · 새로 {len(made)}장 "
              f"= {len(merged)}장", flush=True)
        if silent:
            print(f"   ⚠ 처분을 안 말한 카드 {len(silent)}장 — 그대로 뒀다: "
                  f"{', '.join(silent[:10])}", flush=True)
        if refused:
            print(f"   ⚠ 갈린 슬라이드 밖이라 안 받은 카드 {len(refused)}장:", flush=True)
            for card in refused[:6]:
                print(f"      [slide {card.get('slide_no')}] {str(card.get('q'))[:60]}",
                      flush=True)

    # ── 재현 검사는 새 카드만 ──────────────────────────────────
    def recheck(self):
        """**글자가 달라진 카드만** 풀고 채점한다 — 새로 쓴 것과 고친 것.

        그대로 둔 카드는 질문이 한 글자도 안 바뀌었으므로 옛 판정이 그대로 유효하다.
        재현 검사가 이 파이프라인에서 돈이 가장 많이 나가는 자리라, 안 바뀐 카드를
        다시 푸는 것은 그만큼을 버리는 일이다.

        **`apply` 는 늘 전체를 훑는다.** 옮긴 카드가 밀린 번호로 다시 쓰였을 수 있고,
        빌드가 읽는 파일(`items.reproduced.json`)은 지금의 카드 목록이어야 한다.
        """
        checked = (_load(self.out / "items.checked.json") or {}).get("cards", [])
        alive = {str(c.get("id")) for c in checked}
        testable = [c["id"] for c in checked
                    if c.get("id") in self.new_ids and c["card_format"] not in IMAGE_FORMATS]
        gone = [i for i in self.new_ids if i not in alive]
        if gone:
            print(f"   갈아 끼운 카드 {len(gone)}장이 검증에서 떨어졌다: {gone}", flush=True)
        if testable:
            self.reproduce(only=testable)
        elif (self.out / "reproduce.grades.json").exists():
            print("   새로 검사할 카드가 없다. 판정만 다시 붙인다.", flush=True)
            self.sh("quizgen.reproduce", "apply", str(self.out))
        else:
            # 옛 판이 재현 검사를 안 거친 편이다. 그러면 붙일 판정이 없으니 통째로 잰다.
            print("   옛 판의 채점 결과가 없다. 전체를 검사한다.", flush=True)
            self.reproduce()

    # ── 전체 ──────────────────────────────────────────────────
    def all(self):
        self.step("판 비교", None, self.compare)
        if self.full:
            super().all()
            return
        self.step("전략 판정", None, self.plan_strategy)
        self.step("프롬프트 조립", None, self.assemble)
        if self.diff["changed_slides"]:
            self.step("갈린 슬라이드 다시 쓰기", "revise.out.json", self.rewrite)
            self.step("합치기", None, self.merge_back)
        else:
            shutil.copyfile(self.out / "items.carry.json", self.out / "items.raw.json")
            shutil.copyfile(self.out / "plan.carry.json", self.out / "plan.approved.json")
        self.step("기계 검증", None, self.validate)
        self.step("누출 수선", None, self.leak_repair)
        self.step("재현 검사 (새 카드만)", None, self.recheck)
        self.repair()
        self.step("누출 재확인", None, self.leak_repair)
        self.step("덱 빌드", None, self.build)
