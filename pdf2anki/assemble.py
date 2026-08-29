"""모델이 읽을 프롬프트를 완제품으로 조립한다.

모델에게 규칙·스키마·자료를 찾아다니게 하지 않는다. 코드가 한 파일로 묶어 준다.
텍스트는 전부 인라인하고, 파일로 남기는 것은 PDF 뿐이다(Read 로 읽어야 하므로).

두 개를 만든다.
  prompt.plan.md    ① 학습 목표만 세운다. 사람이 승인한다.
  prompt.cards.md   ② 승인된 목표를 카드로 만든다.

사용:
    python -m pdf2anki.assemble out/lec03 --jokbo-dir out/jokbo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .pack import (
    READ_TOKEN_CAP,
    estimate_pdf_tokens,
    find_jokbo,
    needs_clean,
    read_instructions,
    write_parts,
)
from .prompting import DEFAULT_DOMAIN, DOMAINS, lecture_adapters, read_modules

PROMPTS = Path(__file__).parent / "prompts"
# ── 전략 ──────────────────────────────────────────────────────────
# 자동 판정은 아래 순서를 지킨다. 앞 조건이 뒤 조건보다 항상 우선한다.
# 축은 하나 — **이번 시험의 출제자가 무엇을 보고 판별하게 할 것인가.**
#   image(사진 중심)       실습이고 사진이 많다. 사진·조직·육안·영상 판독을 중심에 둔다.
#   jokbo(족보 중심)       교수 유임이고 반복률이 높다. 기출이 물은 것을 먼저 덮는다.
#   annotation(필기 중심)  교수 교체 또는 낮은 반복률. 사용자 확인 뒤 올해 필기를 우선한다.
#   base(기본)             위 조건 어디에도 들지 않는다.
STRATEGIES = {"annotation": "필기 중심", "jokbo": "족보 중심", "image": "사진 중심",
              "base": "기본"}
STRATEGY_ALIAS = {"필기": "annotation", "필기 중심": "annotation",
                  "족보": "jokbo", "족보 중심": "jokbo",
                  "사진": "image", "사진 중심": "image", "기본": "base",
                  "annotation": "annotation", "jokbo": "jokbo", "image": "image",
                  "photo": "image", "base": "base",
                  "auto": "auto"}

HIGH_REPEAT_RATE = 0.35
LOW_REPEAT_RATE = 0.20
MIN_PHOTO_FIGURE_SLIDES = 10
MIN_PHOTO_FIGURE_SHARE = 0.30
ASK_ANNOTATION = "ask_annotation"

# 사용자가 이미 답한 `ASK_ANNOTATION`만 저장한다. 목록에 없는 미래 강의는 다시 묻는다.
CONFIRMED_STRATEGY_OVERRIDES = {
    "260812_01": "base",
    "260813_02": "base",
    "260813_03": "base",
    "260819_01": "base",
    "260819_02": "base",
    "260819_03": "base",
    "260820_01": "annotation",
    "260820_02": "annotation",
    "260820_03": "annotation",
    "260820_05": "annotation",
    "260824_01": "base",
    "260824_02": "base",
}


class StrategyConfirmationRequired(RuntimeError):
    """자동 판정이 사용자 선택을 필요로 하지만 stdin이 대화형이 아닐 때."""


def photo_profile(prep: dict, lecture_title: str = "") -> dict:
    """실습 여부와 사진 밀도를 결정론적으로 계산한다.

    사진 수 자체는 한 슬라이드의 작은 도형 여러 개에 부풀 수 있어, 사진이 하나라도 있는
    *슬라이드 수*와 그 비율을 함께 쓴다.
    """
    pages = prep.get("pages") or []
    total_slides = int(prep.get("slides") or len(pages) or 0)
    figure_slides = sum(bool(p.get("lecture_figures")) for p in pages)
    figure_count = sum(len(p.get("lecture_figures") or []) for p in pages)
    share = figure_slides / total_slides if total_slides else 0.0
    identity = f"{prep.get('source', '')} {lecture_title}"
    practical = bool(re.search(r"실습|practical|practice", identity, re.IGNORECASE))
    image_rich = (figure_slides >= MIN_PHOTO_FIGURE_SLIDES
                  and share >= MIN_PHOTO_FIGURE_SHARE)
    return {"practical": practical, "image_rich": image_rich,
            "total_slides": total_slides, "figure_slides": figure_slides,
            "figure_count": figure_count, "figure_slide_share": share}


def apply_confirmed_strategy(strategy: str, why: str, prep: dict,
                             lecture_title: str = "") -> tuple[str, str]:
    """확인 필요 판정에 대해 사용자가 이미 답한 강의만 확정한다."""
    if strategy != ASK_ANNOTATION:
        return strategy, why
    identity = f"{prep.get('source', '')} {lecture_title}"
    match = re.search(r"\[(\d{6}_\d{2})\]", identity)
    run_id = match.group(1) if match else ""
    confirmed = CONFIRMED_STRATEGY_OVERRIDES.get(run_id)
    if not confirmed:
        return strategy, why
    return confirmed, f"{why} → 저장된 사용자 선택: {STRATEGIES[confirmed]}"


def image_strategy_body(has_jokbo: bool) -> str:
    """실습 사진을 실제로 판독하게 하는 전략 지침.

    **누출 금지가 여기 있는 이유는 자리 때문이다.** `260818_01` 의 이미지 카드
    37장 중 **31장이 사진을 가려도 그대로 풀렸다**(`doby_is_free/score.py` 실측).
    그때 `prompts/core/media.md` 에 있던 것은 평범한 불릿 한 줄이었다 —
    「질문에서 이미지가 이미 답할 수 있는 진단·구조·범주를 미리 말하지 않는다」.
    지금 거기 있는 굵은 두 줄은 그 카드들이 쓰인 세 시간 반 뒤(`833502b`)에
    들어왔고 **아직 한 번도 재지 않았다.** 이 주석이 한동안 「굵은 규칙이
    있었는데도 졌다」고 적고 있었는데 사실이 아니다.

    같은 날 기준선으로 재 봤다. 「이 파일을 이미지 안키로 만들어줘」 한 문장에
    아래와 같은 뜻의 **한 문단만** 더했더니 사진이 일하는 카드가 16장 → 37장,
    17% → 55% 로 올랐다. 이 함수가 만드는 글은 `assemble()` 의 `head` 에 들어가
    프롬프트 맨 앞에 서므로, 먹혔던 그 자리와 같다.

    뒤의 한 문단(그림이 줄 수 없는 것은 준다)도 실측이다. 앞 문단만 넣었을 때
    「사진을 줘도 못 푸는」 카드가 5장 → 18장으로 늘었다. 한쪽만 막으면 반대쪽이 샌다.

    **「실습 판독 카드」는 실측이 아니라 관리자 지시다(2026-08-26).** 그 전까지 여기는
    「질문은 판독 하나를 요구하고, 정답에는 진단·구조의 이름을」이었고 `260821_05` 는
    같은 사진을 축마다 쪼개 c004·c006·c008 로 냈다. 관리자의 말은 이것이다 —

    > 사진 하나를 앞면으로 주고, 뒷면으로 이게 어떤 조직인지, 어떤 질병인지,
    > 조직학적 소견과 판단근거는 무엇인지, 유전자와 기전은 무엇인지를 기억해내는거야.

    **그 넷이 서식이 아니라는 것도 같은 자리에서 나왔다.** 처음 옮겨 적을 때 이 함수가
    「조직:·진단:·소견과 근거:·유전자와 기전:」 네 줄짜리 서식으로 적었는데 관리자가
    바로잡았다 — *"저 4개를 따로따로 모두 적을 필요는 없고 저런 것들을 적어달라는 거야.
    실습을 위한 새로운 퀴즈 유형이야."* 넷은 칸이 아니라 회수의 범위다.

    이어서 근거 쪽에 무게를 실으라고 했다 — *"판단근거를 명확하게 알려줘. 헷갈리는걸
    잘 짚어줘."* 그래서 뭉뚱그린 근거를 막는 문단과 `explanation` 의 감별 문단이 있다.

    **2026-08-27 에 관리자가 형식을 못 박았다.** 시험 전날이었고, 위의 「회수의 범위」
    문단이 sonnet-5 에서 층을 빼도 된다는 허가로 읽혀 유전자·기전이 22장 중 1장에만
    남았다(`out/exp_prac2_260819_05` 실측). 지시는 이렇다 —

    > 앞면: annotation/필기/화살표/설명박스를 제거한 병리 이미지 1장만 · 뒷면: 진단명 +
    > 조직 + 꼭 외울 핵심 소견/유전자·기전만 아주 짧게 · 덜 중요한 판단근거, 감별
    > 포인트는 아래에 짧은 해설로 · 질문 문구는 없어도 됨 · 한 질환당 한 장만 만들지
    > 말고 gross/저배율/고배율/EM/임상사진 등 가능한 이미지를 최대한 많이 카드화 ·
    > 비슷한 질환끼리 헷갈리는 오답방지/감별 카드도 추가 · 정상 비교 이미지가 있으면
    > 같이 추가 · 강의록 내용만 기준으로 하고, 강의록 밖 지식은 필요하면 별도 표시

    **앞면의 clean 판과 질문 문구는 이미 코드가 보장한다.** `image_basic` 앞면은
    `clean.pdf` 에서 뜨고(`build.MediaMaker.figure`), guid 씨앗에 그림이 들어가므로
    (`build.guid_of`) 카드마다 `q` 가 같아도 노트가 겹치지 않는다. 그래서 프롬프트는
    `q` 를 한 마디로 줄이라고만 적으면 된다. `image_occlusion` 을 금지한 것도 코드 때문이다 —
    오클루전 앞면만 `annotated` 에서 뜬다(`build.MediaMaker.occlusion`).

    **강의록 밖 지식은 `evidence_type` 이 아니라 글자로 표시한다.** `medical_knowledge` 는
    강의록 카드에 붙으면 `validate` 가 떨어뜨리는 값이라(스키마 주석) 그 길이 막혀 있다.
    시험 전날에 검사기를 흔들지 않고 `explanation` 앞에 `(강의록 밖)` 을 붙이게 했다.

    **아직 재지 않은 것.** `reproduce` 가 이미지 카드를 검사에서 빼므로
    (`reproduce.py` 의 `testable`) 이 짧은 답이 재현되는지 재는 자리가 없다.
    """
    exam = (
        "기출에서는 이번 실습의 사진·조직·육안·영상 판독 문항을 먼저 골라 목표에 연결한다. "
        "텍스트 기출은 사진을 구분하는 진단 기준을 보강할 때만 우선한다.\n"
        if has_jokbo else
        "기출 조각이 없으므로 강의록 사진과 그 캡션·본문이 제시한 판독 기준을 근거로 삼는다.\n"
    )
    return (
        "**이 강의는 사진 판독 덱으로 만든다.** 앞면은 병리 사진 한 장이고, 뒷면에서 진단·조직·"
        "핵심 소견·유전자와 기전을 떠올리게 한다.\n\n"
        "**질문이 사진을 대신 읽어 주지 마라.** `q` 는 「이 사진을 판독하라.」 한 마디로 둔다. "
        "사진에서 읽어 낼 소견 — 형태·배열·색조·위치 — 도, 진단명·세포 이름도 앞면에 적지 "
        "않는다. 적으면 남는 일은 이름 붙이기뿐이고 사진은 장식이 된다.\n\n"
        "**다만 그림이 줄 수 없는 것은 질문에 준다.** 염색 종류, 배율, 어느 부위를 보라는 지시, "
        "사진에 안 나오는 임상 정보가 그것이다. 이것까지 빼면 사진을 봐도 답이 좁혀지지 않는다. "
        "한 마디로 붙인다 — 「이 사진을 판독하라. (H&E, 고배율)」.\n\n"
        "**`image_occlusion` 은 이 실습에서 쓰지 않는다.** 오클루전 앞면만 필기가 남은 판에서 "
        "뜨는데, 이 덱의 앞면은 필기·화살표·설명 상자가 걷힌 사진이어야 한다. 전부 "
        "`image_basic` 으로 만든다.\n\n"
        "**쓸 만한 사진 하나가 카드 하나다.** 한 질환에 gross·저배율·고배율·EM·임상 사진이 "
        "여러 장 있으면 **그 전부를 각각 카드로 만든다.** 같은 진단이라고 한 장으로 묶지 마라 — "
        "시험은 그 사진들 중 아무거나 내놓는다. `lecture_figures` 중 판독할 만한 것을 훑어 "
        "전부 카드로 옮기고, 카드 수에 스스로 상한을 두지 않는다.\n\n"
        "**정상 비교 사진이 있으면 그것도 카드로 만든다.** 정상 조직·정상 장기 사진은 병변을 "
        "가르는 기준선이므로 「정상 ○○」을 답으로 하는 카드를 따로 세운다.\n\n"
        "**헷갈리는 질환끼리는 감별 카드를 따로 만든다.** 같은 실습 안에서 서로 오답이 되는 "
        "짝(예: 피막 있는 것과 없는 것, 큰 낭종과 작은 낭종, 정상과 병변)을 찾아, 무엇을 보고 "
        "가르는지만 묻는 카드를 얹는다. 사진 둘을 한 앞면에 놓을 수 없으면 `basic` 텍스트 "
        "카드로 만든다.\n\n"
        + exam +
        "\n**뒷면 `a` 는 아주 짧게, 꼭 외울 것만.** 아래를 각각 한 줄로 적고 문장으로 늘어놓지 "
        "않는다. 자료가 주지 않는 줄은 뺀다.\n\n"
        "    - 진단명\n"
        "    - 조직·장기\n"
        "    - 꼭 외울 핵심 소견 (한둘)\n"
        "    - 유전자와 기전 (한 줄)\n\n"
        "각 줄에서 회수의 핵심이 되는 말만 `**` 로 씌운다. 줄 전체를 씌우지 않는다.\n\n"
        "**덜 중요한 것은 `explanation` 으로 내린다.** 나머지 판단 근거와 감별 포인트가 그것이다. "
        "짧게 — 두세 줄을 넘기지 않는다. 헷갈릴 짝이 있으면 무엇과 헷갈리고 무엇을 보고 갈랐는지를 "
        "여기에 적는다.\n\n"
        "**강의록만 근거로 쓴다.** 진단·소견·유전자를 강의록 밖 지식으로 세우지 않는다. 꼭 필요한 "
        "보충은 `explanation` 에만 두고 맨 앞에 `(강의록 밖)` 을 붙여 사람이 바로 알아보게 한다.\n\n"
        "crop 은 설명 상자·캡션·화살표 주석·정답이 인쇄된 글자를 덜어낼 때 쓴다. 주변 조직·배율·"
        "방향처럼 판독에 필요한 맥락은 남긴다. 사진만으로 성립하지 않는 기전·정의와 사진을 읽기 "
        "위한 최소 선행지식만 텍스트 카드로 만든다.\n\n"
        "사진이 장식이거나 해상도가 낮거나 정답이 픽셀 안에 그대로 인쇄돼 안전하게 자를 수 없으면 "
        "쓰지 말고 제외 근거를 남긴다."
    )


def guidance_without_jokbo(strategy: str) -> str:
    """기출 조각이 없어도 사람이 고른 전략을 프롬프트까지 보존한다."""
    if strategy == "image":
        body = image_strategy_body(False)
    elif strategy == "annotation":
        body = ("기출 조각이 없다. 강의록의 구조와 올해 필기의 강조점을 우선하고, "
                "올해 필기가 몰린 슬라이드부터 목표를 세운다.")
    elif strategy == "jokbo":
        body = ("기출 조각이 없어 족보 중심 우선순위를 적용할 근거가 없다. "
                "강의록 구조를 축으로 만들고 이 실행의 근거 부족을 숨기지 않는다.")
    else:
        body = "기출 조각이 없다. 강의록 구조를 축으로 만들고 필기는 중요도 신호로만 쓴다."
    return f"## 이 강의의 전략: `{STRATEGIES[strategy]}`\n\n{body}\n"


def decide_strategy(stats: dict | None, mixed_owner: bool = False, *,
                    practical: bool = False, image_rich: bool = False) -> tuple[str, str]:
    """(전략, 고른 이유 한 줄). practical/photo → high → ask annotation → base.

    `ASK_ANNOTATION`은 최종 전략이 아니라 사용자 확인이 필요한 중간 판정이다.
    다른 강의 소유의 조각은 반복률·교수 정보를 어느 조건에도 사용하지 않는다.
    """
    usable_stats = bool(stats) and not mixed_owner
    rate = float((stats or {}).get("repeat_rate") or 0.0)

    if practical and image_rich:
        return "image", "실습이며 사진 포함 슬라이드가 충분히 많다"
    professor_changed = usable_stats and bool(stats.get("professor_changed_2026"))
    if usable_stats and not professor_changed and rate >= HIGH_REPEAT_RATE:
        return "jokbo", f"연도간 반복률 {rate:.0%}로 높다 (기준 {HIGH_REPEAT_RATE:.0%} 이상)"
    if professor_changed:
        return ASK_ANNOTATION, f"올해 담당 교수가 바뀌었다 (기출 반복률 {rate:.0%})"
    if usable_stats and rate < LOW_REPEAT_RATE:
        return ASK_ANNOTATION, f"연도간 반복률 {rate:.0%}로 낮다 (기준 {LOW_REPEAT_RATE:.0%} 미만)"
    if mixed_owner:
        return "base", "이 조각의 주인이 다른 강의라 통계를 이 강의에 적용할 수 없다"
    if not stats:
        return "base", "기출 조각이 없다 — 강의록만으로 만든다"
    return "base", f"반복률 {rate:.0%}로 중간 구간이다"


def resolve_auto_strategy(strategy: str, why: str, *, interactive: bool | None = None,
                          input_fn=input) -> tuple[str, str]:
    """확인이 필요한 자동 판정을 필기 중심 또는 기본으로 확정한다."""
    if strategy != ASK_ANNOTATION:
        return strategy, why
    if interactive is None:
        interactive = sys.stdin.isatty()
    prompt = f"{why}. 필기 중심으로 만들까요? [Y/n] "
    if not interactive:
        raise StrategyConfirmationRequired(
            f"{why}. 사용자 확인이 필요하다. --strategy 필기 또는 --strategy 기본을 지정해 다시 실행해라")
    answer = input_fn(prompt).strip().lower()
    if answer in {"", "y", "yes", "예", "네"}:
        return "annotation", f"{why} → 사용자 확인: 필기 중심"
    return "base", f"{why} → 사용자 확인: 기본"


def slice_for(prep: dict, jokbo_dir: Path, explicit: str | None = None
              ) -> tuple[Path | None, dict, bool]:
    """이 강의의 족보 조각과 그 통계를 찾는다. (조각, stats, 주인이-다른-강의인가)"""
    if explicit:
        p = Path(explicit)
        jk = json.loads(p.read_text(encoding="utf-8"))
        return p, jk.get("stats", {}), bool(jk.get("may_contain"))
    if not (Path(jokbo_dir) / "index.json").exists():
        return None, {}, False
    path, score, top = find_jokbo(prep, Path(jokbo_dir))
    if not path or score < 0.25:
        return None, {}, False
    jk = json.loads(path.read_text(encoding="utf-8"))
    return path, jk.get("stats", {}), top[0][2] is not None


MAX_REPEAT_CLUSTERS = 12       # 프롬프트에 실을 묶음 수. 실측 최대가 13개다(LPRAC)


def repeat_clusters(stats: dict, questions: list | None = None) -> list[dict]:
    """반복 쌍을 묶음으로 잇는다. 쌍 목록보다 묶음이 읽기 쉽다.

    `2020-68 ↔ 2022-55`, `2022-55 ↔ 2023-61`, `2023-61 ↔ 2025-103` 을 쌍으로 늘어놓으면
    같은 것이 세 번 보인다. 이어 붙이면 **한 주제가 다섯 해 반복됐다** 가 한 줄로 선다.

    돌려주는 각 묶음은 `{"members": [최근 연도부터], "stem": 대표 문항의 본문}` 이다.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for pair in stats.get("repeat_pairs") or []:
        ra, rb = find(pair["a"]), find(pair["b"])
        if ra != rb:
            parent[ra] = rb

    groups: dict[str, list[str]] = {}
    for k in parent:
        groups.setdefault(find(k), []).append(k)

    stems = {f"{q['year']}-{q['no']}": (q.get("stem") or "") for q in (questions or [])}
    out = []
    for members in groups.values():
        # 연도 내림차순. 대표는 가장 최근 것이다 — 그 해의 문구가 지금 출제자에 가깝다.
        members.sort(key=lambda m: (m.split("-")[0], m), reverse=True)
        stem = next((stems[m] for m in members if stems.get(m)), "")
        out.append({"members": members, "stem": " ".join(stem.split())[:70]})
    out.sort(key=lambda c: (-len(c["members"]), c["members"][0]))
    return out


def topic_count(stats: dict, questions: list | None = None) -> tuple[int, int, int]:
    """(실질 주제 수, 반복 묶음 수, 묶음에 안 든 문항 수).

    기출 파트의 목표 수는 문항 수가 아니라 **이 수**를 상한으로 잡는다. 문항 수로
    잡으면 같은 주제를 다섯 해치 따로 세우게 된다 — 병리학 533문항 중 182개(34%)가
    어떤 묶음에 들어 있고, 묶어서 세면 실질 주제는 420개다.
    """
    clusters = repeat_clusters(stats, questions)
    clustered = sum(len(c["members"]) for c in clusters)
    n = stats.get("n_questions", 0)
    singles = max(n - clustered, 0)
    return len(clusters) + singles, len(clusters), singles


def repeat_block(stats: dict, questions: list | None, stayed: bool) -> str:
    """반복 묶음을 프롬프트에 싣는다.

    **이 블록이 복습 쪽에는 없었다.** `jokbo.py` 가 `repeat_pairs` 를 계산해 두는데
    복습 지침은 `repeat_rate` 숫자 한 줄만 쓰고 쌍 목록을 버렸고, 정작 예습 쪽
    (`prequiz/assemble.py`) 만 그것을 모델에게 보여 주고 있었다. 복습이 예습보다
    기출을 덜 보고 있었던 셈이다.

    관리자가 막아 달라고 명시한 것이 여기 걸린다 — *"겹치는 문제를 너무 반복해서
    풀지 않도록(어 이거 아까 봤던 거네, 선지만 바뀐듯 방지)"*. 병리학 533문항 중
    **182개(34%)가 어떤 묶음에 들어 있다.** 묶어서 세면 실질 주제는 420개다.
    """
    clusters = repeat_clusters(stats, questions)
    if not clusters:
        return ""
    shown = clusters[:MAX_REPEAT_CLUSTERS]
    rows = "".join(f"- {' · '.join(c['members'])}\n"
                   + (f"  「{c['stem']}」\n" if c["stem"] else "")
                   for c in shown)
    more = ("" if len(clusters) == len(shown) else
            f"\n> 묶음 {len(clusters)}개 중 큰 것 {len(shown)}개만 실었다.\n")
    # 쌍 목록 자체가 `jokbo.py` 에서 40개로 잘린다. 잘린 채로 묶으면 묶음이 덜 이어진
    # 것일 수 있으므로, 상한에 닿았을 때만 그렇다고 적는다. 조용히 자르지 않는다.
    cut = ("\n> ⚠ 쌍 목록이 상한(40개)에 닿았다. 위 묶음이 덜 이어졌을 수 있으니\n"
           "> 여기 없는 문항끼리도 겹치는지 직접 보아라.\n"
           if len(stats.get("repeat_pairs") or []) >= 40 else "")
    tail = (
        "**한 묶음은 한 주제다. 각 해의 문항을 따로 카드화하지 마라.** 푸는 사람에게는 "
        "「아까 봤던 건데 선지만 바뀐」 카드로 온다.\n"
        "묶음이 요구한 지식의 **축을 나눠** 3~5장을 내고, `jokbo_ref` 에는 묶음에서 "
        "가장 최근 연도의 문항을 단다. 묶음에 안 든 문항은 1~2장으로 족하다.\n"
        if stayed else
        "**교수가 바뀌었으므로 이 반복은 중요도의 근거가 아니다.** 그래도 묶음은 묶음이다 — "
        "겹치는 문항을 여러 장으로 내면 같은 카드를 두 번 푸는 것이 된다. 한 주제로 묶어라.\n")
    return ("\n### 여러 해 반복된 문항 묶음\n\n"
            "문항 본문의 어휘 겹침으로 코드가 묶었다. 한 줄이 한 주제다.\n\n"
            + rows + more + cut + "\n" + tail)


def jokbo_guidance(stats: dict, title: str, mixed: list | None = None,
                   strategy: str | None = None, shared_bank: bool = False,
                   questions: list | None = None) -> str:
    """전략에 맞는 족보 가중치 지침을 만든다. 전략을 안 주면 통계에서 판정한다."""
    yr = stats.get("professors_by_year") or {}
    rate = stats.get("repeat_rate", 0.0)
    prof_line = " · ".join(f"20{y} {'/'.join(v)}" for y, v in sorted(yr.items(), reverse=True))
    strategy = strategy or decide_strategy(stats, bool(mixed))[0]
    # 이 함수는 프롬프트 문자열만 만드는 저수준 API라 사용자에게 물을 수 없다.
    # 실제 CLI/runner는 이 지점 전에 resolve_auto_strategy로 확정한다.
    if strategy == ASK_ANNOTATION:
        strategy = "annotation"

    if strategy == "image":
        body = image_strategy_body(True)
    elif strategy == "annotation":
        body = (
            "**올해 담당 교수가 바뀌었다.** 과거 기출은 이전 교수의 출제이며, "
            "같은 문항이 다시 나올 것으로 가정하지 마라.\n"
            "기출은 '이 단원에서 무엇이 시험 가능한 지식인가'를 알려주는 신호로만 쓰고, "
            "**강의록의 구조와 올해 필기의 강조점을 우선**한다.\n"
            "필기의 연도가 올해인 항목이 지금 교수가 실제로 강조한 것이다.\n\n"
            "**카드를 어디에 몰 것인가.** 올해 필기가 몰린 슬라이드 → 스탬프·형광펜이 붙은 곳 "
            "→ 강의록이 구조적으로 강조한 곳 순이다. 기출 전용 카드는 만들지 마라 — "
            "기출과 겹치는 내용이면 그것대로 좋지만, 기출을 덮는 것 자체를 목표로 삼지 않는다."
        )
    elif strategy == "jokbo":
        # 자동 전략에서는 교수 유임일 때만 들어온다. 명시적 --strategy 족보도 지원하므로
        # 교수 교체 상태의 문구는 거짓 단언 없이 따로 둔다.
        if stats.get("professor_changed_2026"):
            head = ("**연도간 문항 반복률이 %.0f%%로 높다.** 올해 담당 교수는 바뀌었지만, "
                    "정한 우선순위에 따라 높은 반복률을 먼저 적용한다.\n" % (rate * 100))
        elif prof_line:
            head = ("**담당 교수가 그대로이고 연도간 문항 반복률이 %.0f%%로 높다.** "
                    "이 교수는 기출을 재활용한다.\n" % (rate * 100))
        else:
            # 교수를 모르는 조각(실습)에서 "교수가 그대로"라고 단언하지 않는다.
            head = ("**연도간 문항 반복률이 %.0f%%로 높다.** 이 과목은 기출이 재활용된다.\n"
                    % (rate * 100))
        body = (
            head +
            "기출이 물은 회수 목표를 **먼저 덮은 뒤** 나머지를 채워라. "
            "반복 출제된 문항은 `importance=core`로 둔다.\n\n"
            "**덮되 나누어 덮어라.** 한 기출 문항이 축을 여럿 물고 있으면 **카드도 여럿으로 나눈다.** "
            "한 장에 몰면 하나만 떠올라도 틀린 카드가 되어 회수를 재지 못한다. "
            "나눌 수 없으면 여러 해 반복된 축만 낸다.\n"
            "**스탬프가 붙었다는 것은 '여기를 보라'이지 '여기를 다 내라'가 아니다.**\n\n"
            "**카드를 어디에 몰 것인가.** 여러 해 반복 출제된 주제에 각 3~5장, "
            "한 해만 나온 기출 주제에 각 1~2장을 먼저 배정하고, 남는 분량으로 "
            "필기·스탬프가 가리키는 곳을 채운다. 기출도 표시도 없는 슬라이드는 목표당 1장을 넘기지 않는다."
        )
    else:
        body = (
            f"담당 교수는 그대로이나 연도간 반복률은 {rate:.0%}로 높지 않다.\n"
            "**강의록을 우선**하고 기출은 우선순위 신호로 쓴다. "
            "교수는 대체로 가르친 데에서 낸다는 것이 기본 가정이다.\n\n"
            "**카드를 어디에 몰 것인가.** 강의록이 구조적으로 강조한 곳(장 제목·요약 슬라이드·"
            "반복 등장하는 개념)을 축으로 잡고, 기출·스탬프·필기가 가리키는 곳을 그 위에 얹는다."
        )
    mix = ""
    if shared_bank:
        # 족보의 실습 문항은 회차 구분 없이 한 덩어리다. 6회 실습이 이 조각 하나를 나눠 쓴다.
        mix += ("\n> ⚠ **이 조각은 실습 전 회차의 문항을 한데 모은 것이다.**\n"
                "> 이번 강의는 그중 한 회차다. **이번 실습 소관 문항만 골라 써라** —\n"
                "> 다른 회차의 문항으로 카드를 만들면 이 덱의 범위를 벗어난다.\n"
                "> 소관 여부는 문항이 다루는 조직·염색·질환이 이번 강의록에 나오는지로 판단한다.\n"
                "> 위의 반복률은 **실습 전체 기준**이다.\n")
    if mixed:
        mix += ("\n> ⚠ **이 조각의 주인은 다른 강의다.** 아래 강의는 족보 본문에 제목이 없어\n"
               "> 문항이 이 섹션으로 흘러들어왔다. **이번 강의 소관 문항을 직접 골라내라.**\n>\n"
               + "".join(f"> - {m['lecture_key']} {m['title']}\n" for m in mixed)
               + ">\n> 위의 담당 교수·반복률은 **주 섹션 기준**이다. 이번 강의에 그대로 적용하지 마라.\n")
    repeats = repeat_block(stats, questions, strategy != "annotation")
    topics, n_cl, n_sg = topic_count(stats, questions)
    return (f"## 이 강의의 전략: `{STRATEGIES[strategy]}`\n\n"
            f"- 조각의 주 섹션: {title}\n"
            f"- 담당 교수: {prof_line or '미상'}\n"
            f"- 연도간 문항 반복률: {rate:.0%} (문항 {stats.get('n_questions', 0)}개)\n"
            f"- 실질 주제 수: **{topics}개** (반복 묶음 {n_cl}개 + 낱개 {n_sg}개)"
            f" — 기출 파트 목표 수의 상한이다\n"
            f"- 족보 가중치 권고: `{stats.get('jokbo_weight_hint', 'normal')}`\n"
            f"{mix}\n{body}\n{repeats}")


def assemble(prep_dir: Path, jokbo_file: Path | None, schema_dir: Path,
             strategy: str | None = None, domain: str = DEFAULT_DOMAIN) -> dict:
    prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))
    prep_md = (prep_dir / "prep.md").read_text(encoding="utf-8")
    contract = (schema_dir / "contract.md").read_text(encoding="utf-8")
    pdf = (prep_dir / prep["annotated_pdf"]).resolve()

    if jokbo_file:
        jk = json.loads(jokbo_file.read_text(encoding="utf-8"))
        jokbo_md = jokbo_file.with_suffix(".md").read_text(encoding="utf-8")
        guidance = jokbo_guidance(jk["stats"], f"{jk['lecture_key']} {jk['title']}",
                                  jk.get("may_contain"), strategy,
                                  shared_bank=jk["lecture_key"] == "PRAC",
                                  questions=jk.get("questions"))
        jokbo_block = (f"# 기출 조각 — {jk['lecture_key']} {jk['title']}\n\n"
                       "이 단원의 과거 기출 전량이다. 정답과 이의제기 답변이 결합돼 있다.\n\n"
                       + jokbo_md.split("\n", 1)[1].lstrip())
    else:
        jk = None
        guidance = guidance_without_jokbo(strategy or "base")
        jokbo_block = ""

    sidecar = "# 슬라이드 사이드카\n\n" + prep_md.split("\n", 1)[1]
    adapters = lecture_adapters(has_past_exam=bool(jokbo_file), domain=domain,
                                allow_medical_exam_repair=True)
    shared_prompt = read_modules(profile="exam_review", adapters=adapters,
                                 domain=domain)

    # 단계와 무관한 자료(사이드카·기출)는 따로 낸다. 두 단계가 같은 파일을 다시 읽지 않게 한다.
    ctx_sections = [sidecar] + ([jokbo_block] if jokbo_block else [])
    ctx_files = write_parts(prep_dir, "context", ctx_sections, label="자료 파트")
    ctx_names = [f["name"] for f in ctx_files]

    head = (f"# 강의 → Anki 덱 : {prep['source']}\n\n"
            "너는 이 강의의 시험 대비 Anki 덱을 만든다. 자료는 여기와 아래 지정한 파일에 전부 있다.\n"
            "그 밖의 파일을 찾아다니지 마라.\n\n"
            + read_instructions(pdf, prep["slides"], [prep_dir / n for n in ctx_names],
                                (prep_dir / prep["clean_pdf"]).resolve(),
                                needs_clean(prep))
            + "\n" + guidance)

    out = {"context": ctx_files}
    for stage, task_file, subs in (
        ("plan", "plan.md", {"plan_out": (prep_dir / "plan.json").as_posix()}),
        ("cards", "cards.md", {"plan_in": (prep_dir / "plan.approved.json").as_posix(),
                               "cards_out": (prep_dir / "items.raw.json").as_posix()}),
    ):
        task = (PROMPTS / task_file).read_text(encoding="utf-8")
        for k, v in subs.items():
            task = task.replace("{" + k + "}", v)
        sections = [head, *shared_prompt, task]
        if stage == "cards":
            sections.append(contract)

        out[stage] = write_parts(prep_dir, f"prompt.{stage}", sections, manifest=True)

    out["_pdf_tokens"] = estimate_pdf_tokens(prep)
    out["_jokbo"] = jk
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="완제품 프롬프트를 조립한다")
    ap.add_argument("prep_dir")
    ap.add_argument("--jokbo", help="족보 조각 json. 생략하면 목차 제목으로 자동 대조한다")
    ap.add_argument("--jokbo-dir", default="out/jokbo")
    ap.add_argument("--schema-dir", default="out/schema")
    ap.add_argument("--strategy", default="auto", choices=sorted(STRATEGY_ALIAS),
                    help="기본/필기/족보/사진 중 무엇을 축으로 삼을지. "
                         "auto 면 실습 사진·반복률·교수 교체 순으로 판정한다")
    ap.add_argument("--domain", default=DEFAULT_DOMAIN, choices=sorted(DOMAINS),
                    help=f"퀴즈 도메인 정책 (기본 {DEFAULT_DOMAIN})")
    args = ap.parse_args(argv)

    prep_dir = Path(args.prep_dir)
    prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))

    mixed_owner = False
    jokbo_file = Path(args.jokbo) if args.jokbo else None
    if jokbo_file is None and Path(args.jokbo_dir).exists():
        jokbo_file, score, top = find_jokbo(prep, Path(args.jokbo_dir))
        print("족보 조각 자동 대조:")
        for sc, e, via in top:
            mark = " ←선택" if jokbo_file and e["file"] in jokbo_file.name else ""
            label = (f"{e['lecture_key']} {e['title']}" if not via
                     else f"{via['lecture_key']} {via['title']}  (조각은 {e['lecture_key']} 안에 섞여 있음)")
            print(f"   {sc:.2f}  {label}{mark}")
        if score < 0.25:
            print(f"⚠ 일치도가 낮다({score:.2f}). --jokbo 로 직접 지정하는 편이 낫다.")
            jokbo_file = None
        else:
            mixed_owner = top[0][2] is not None

    stats = {}
    if jokbo_file:
        stats = json.loads(jokbo_file.read_text(encoding="utf-8")).get("stats", {})
    strategy = STRATEGY_ALIAS[args.strategy]
    if strategy == "auto":
        profile = photo_profile(prep)
        strategy, why = decide_strategy(stats, mixed_owner,
                                        practical=profile["practical"],
                                        image_rich=profile["image_rich"])
        strategy, why = apply_confirmed_strategy(strategy, why, prep)
        try:
            strategy, why = resolve_auto_strategy(strategy, why)
        except StrategyConfirmationRequired as e:
            print(f"\n⚠ {e}", file=sys.stderr)
            return 2
    else:
        why = "사람이 --strategy 로 지정했다"

    res = assemble(prep_dir, jokbo_file, Path(args.schema_dir), strategy, args.domain)

    print(f"\n전략: {STRATEGIES[strategy]}  — {why}")
    if res["_jokbo"]:
        st = res["_jokbo"]["stats"]
        print(f"   족보 가중치 {st['jokbo_weight_hint']} "
              f"· 반복률 {st['repeat_rate']:.0%}"
              f"{' · 교수 교체' if st['professor_changed_2026'] else ''}")
    print()
    ctx_tok = sum(f["tokens"] for f in res["context"])
    for label in ("context", "plan", "cards"):
        files = res[label]
        for f in files:
            warn = "  ⚠ Read 상한 초과" if f["tokens"] > READ_TOKEN_CAP else ""
            print(f"[{label:<7}] {f['name']:<24}{f['chars']:>7,}자 {f['tokens']:>7,}토큰{warn}")
    plan_tok = sum(f["tokens"] for f in res["plan"])
    cards_tok = sum(f["tokens"] for f in res["cards"])
    pdf = res["_pdf_tokens"]
    print("\n한 세션에서 ①②를 이어 하면 PDF와 자료는 한 번만 읽는다:")
    print(f"   PDF {pdf:,} + 자료 {ctx_tok:,} + ① {plan_tok:,} + ② {cards_tok:,} "
          f"= 약 {pdf + ctx_tok + plan_tok + cards_tok:,}토큰")
    first = res["plan"][0]["name"]
    print(f"\n   ① {first} 부터 읽혀 {prep_dir}/plan.json 을 받는다")
    print(f"   ② python -m pdf2anki.review {prep_dir}  → 훑고 --approve")
    print(f"   ③ {res['cards'][0]['name']} 를 읽혀 {prep_dir}/items.raw.json 을 받는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
