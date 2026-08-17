"""덱을 사람 없이 올려도 되는지 본다.

`publish`가 편마다 부른다. 막을 것이 있으면 그 편은 `hold_artifacts()`로 **강의록만
내보내고 덱·run-meta·예습은 미룬다.** 통째로 멈추지 않는 이유는 강의록이 그 검토와
무관한 자료이고, 먼저 나가야 캘린더 칸이 열리기 때문이다.

## 무엇을 막고 무엇을 적기만 하나

CLAUDE.md "계수기는 아직 사람을 부를 줄 모른다"가 후보 둘을 이미 떨어뜨렸다.
그래서 여기서 막는 것은 **개수가 아니라 종류이거나, 산출물이 스스로 주장하는
것과 다른 경우**뿐이다.

    막는다    apkg의 실제 내용물이 `item_count`와 다르다
    막는다    `answer_mismatch` — 정답이 틀렸다는 뜻인 유일한 플래그
    막는다    확정본 검증에서 hard 제거가 났다 (빌드 불가 카드가 섞여 있었다)
    막는다    덱은 있는데 `run.meta.json`이 없다 (무엇으로 만들었는지 모른다)

    적기만    `slides_unused` — 품질이 아니라 강의록 생김새를 잰다. 실측 두 편에서
              `blueprint.skip_slides`와 정확히 일치했다(11/11, 9/9)
    적기만    `review_flagged` 총계 — 실측 세 건이 전부 스스로 풀린 것이었다
    적기만    `untouched_slides` — 진짜 누락 신호이긴 하나, 지금 이 값이 자료의 범위와
              어긋나 있다는 것을 아무도 확인한 적이 없다(CLAUDE.md "아직 실측하지
              않은 것"). 근거 없이 막지 않는다
    적기만    유사 후보군·커버리지 누락·과출제 의심 — 4단계 감사가 이미 보고 지나간 것

`answer_mismatch`는 실측에서 **아직 한 번도 안 나왔다.** 그러니 이 문턱이 실제로
무엇을 잡는지는 아직 모른다 — 처음 걸리는 편이 나오면 그것이 첫 실측이다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 이 플래그만 "정답이 틀렸다"는 뜻이다. 나머지 둘(`question_error`·`uncertain`)은
# 족보 문항 자체의 흠이거나 모델이 결론을 못 낸 것이고, 실측에서 셋 다 스스로 풀렸다.
BLOCKING_REVIEW_FLAG = "answer_mismatch"


@dataclass
class Verdict:
    blocking: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocking


def _load(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _flag_kinds(run_dir: Path, meta: dict, prefix: str) -> dict[str, int] | None:
    """플래그를 종류별로. `run.meta.json`에 없으면 확정본에서 직접 센다.

    종류를 메타에 적기 시작한 것이 이 기능부터라, 그 전에 만든 덱은 총계만 들고
    있다. 그렇다고 옛 덱을 전부 막으면 다시 빌드하라는 말밖에 안 되므로
    `items.final.json`을 본다. 그것도 없으면 종류를 모른다고 답한다.
    """
    kinds = meta.get("review_flags")
    if isinstance(kinds, dict):
        return {str(k): int(v) for k, v in kinds.items()}

    items = _load(run_dir / f"{prefix}items.final.json")
    if isinstance(items, dict):
        items = items.get("items")
    if not isinstance(items, list):
        return None

    counted: dict[str, int] = {}
    for item in items:
        for flag in item.get("review_flags") or []:
            counted[str(flag)] = counted.get(str(flag), 0) + 1
    return counted


def inspect(run_dir: Path, deck: Path | None, meta_path: Path | None,
            label: str, prefix: str = "") -> Verdict:
    """`label`은 보고에 쓸 이름, `prefix`는 산출물 접두어("" / "pre_")."""
    verdict = Verdict()
    if deck is None and meta_path is None:
        return verdict
    if meta_path is None or not meta_path.is_file():
        verdict.blocking.append(f"{label} 덱은 있는데 run.meta.json이 없다 — 무엇으로 만들었는지 모른다")
        return verdict

    meta = _load(meta_path)
    if not isinstance(meta, dict):
        verdict.blocking.append(f"{label} {meta_path.name}을 읽지 못했다")
        return verdict

    # apkg를 도로 열어 센 값이다. 이게 어긋나면 덱이 내용과 다른 것을 담고 있다.
    verified, count = meta.get("verified") or {}, int(meta.get("item_count") or 0)
    notes_in_apkg = verified.get("notes")
    if notes_in_apkg is None:
        verdict.blocking.append(f"{label} apkg 검증 기록이 없다 — 덱이 온전한지 모른다")
    elif int(notes_in_apkg) != count:
        verdict.blocking.append(
            f"{label} apkg에 노트가 {notes_in_apkg}장인데 item_count는 {count}장이다")

    kinds = _flag_kinds(run_dir, meta, prefix)
    flagged = int(meta.get("review_flagged") or 0)
    if kinds is None:
        if flagged:
            verdict.blocking.append(
                f"{label} 정오 검토 {flagged}장인데 종류를 모른다 "
                f"(run.meta.json에 review_flags가 없고 items.final.json도 못 읽었다)")
    else:
        wrong = int(kinds.get(BLOCKING_REVIEW_FLAG) or 0)
        if wrong:
            verdict.blocking.append(
                f"{label} {BLOCKING_REVIEW_FLAG} {wrong}장 — 정답이 틀렸다는 플래그다")
        rest = {k: v for k, v in sorted(kinds.items()) if k != BLOCKING_REVIEW_FLAG and v}
        if rest:
            verdict.notes.append(
                f"{label} 정오 검토 " + " · ".join(f"{k} {v}장" for k, v in rest.items())
                + " — 카드 뒷면 경고 박스를 확인할 것")

    suspects = _load(run_dir / f"{prefix}suspects.json")
    if not isinstance(suspects, dict):
        verdict.notes.append(f"{label} {prefix}suspects.json이 없다 — 3단계 검증 결과를 못 봤다")
        return verdict

    removed = suspects.get("removed") or []
    if removed:
        reasons = sorted({r for x in removed for r in (x.get("reason") or [])})
        verdict.blocking.append(
            f"{label} 확정본 검증에서 {len(removed)}장이 hard로 떨어졌다 "
            f"({', '.join(reasons) or '사유 미상'}) — 감사가 안 끝났다")

    untouched = suspects.get("untouched_slides") or []
    if untouched:
        verdict.notes.append(f"{label} 문항이 없는 슬라이드 {len(untouched)}장: {untouched}")
    hot = suspects.get("hot_slides") or []
    if hot:
        verdict.notes.append(
            f"{label} 과출제 의심 슬라이드 {[h.get('slide_no') for h in hot]}")
    return verdict
