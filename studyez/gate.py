"""덱을 사람 없이 올려도 되는지 본다.

`publish`가 편마다 부른다. 막을 것이 있으면 그 편은 **강의록만 내보내고 덱·run-meta·
예습은 미룬다.** 통째로 멈추지 않는 이유는 강의록이 그 검토와 무관한 자료이고,
먼저 나가야 캘린더 칸이 열리기 때문이다.

## 파이프라인이 이미 막는 것은 여기서 다시 막지 않는다

pdf2anki는 **재현 검사를 통과하지 못한 카드가 남으면 덱을 만들지 않는다.** 질문만
보고 다시 푼 답이 원래 답과 갈리고 그 사유가 문항 결함(`question_ambiguous`·
`needs_options`·`answer_underspecified`)이면 그 카드를 다시 쓰게 하고, 그래도 안
되면 빌드를 거부한다. 그러니 `.apkg`가 있다는 것 자체가 그 검사를 지났다는 뜻이다.

여기서 막는 것은 그래서 **산출물이 스스로 주장하는 것과 다른 경우**로 좁는다.

    막는다    apkg를 다시 열어 센 노트 수가 `item_count`와 다르다
    막는다    본문이 참조하는데 패키지에 없는 이미지가 있다
    막는다    덱에 문항 결함으로 갈린 카드가 남아 있다 (빌드가 자기 규칙을 어겼다)
    막는다    덱은 있는데 `run.meta.json`이 없다 (무엇으로 만들었는지 모른다)
    막는다    사람이 `HOLD`를 놓아 두었다

    적기만    soft flag 종류별 개수 — 카드 뒷면 경고 박스로 이미 나간다
    적기만    `different`·`partial` 재현 판정 — 눈가리개 세션이 몰랐을 뿐일 수 있다
    적기만    `slides_unused` — 품질이 아니라 강의록 생김새를 잰다
    적기만    `untouched_slides`·`objectives_without_card` — 커버리지는 순위가 내려갔다

`different`를 막지 않는 것이 중요하다. 재현 검사의 뜻은 「푸는 쪽이 같은 답에
닿는가」이지 「모델이 그 지식을 아는가」가 아니다. 사유로 갈린 것만 파이프라인이
이미 걸렀고, 남은 것을 개수로 다시 막으면 좋은 카드가 조용히 버려진다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 사람이 손으로 놓는 보류 표시. 안에 적힌 글이 그대로 사유가 된다.
HOLD_FILE = "HOLD"


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


def hold_reason(run_dir: Path) -> str:
    """이 자리가 보류돼 있으면 사유를, 아니면 빈 문자열.

    `studyez import`가 옆 저장소에서 옮겨 온 덱에 이걸 놓는다 — 다른 곳에서 만든
    것이라 아직 이 사이트의 눈으로 본 적이 없기 때문이다. 사람이 보고 `studyez
    release <run_id>`로 푼다.
    """
    path = run_dir / HOLD_FILE
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip() or "사유 없이 보류돼 있다"
    except OSError:
        return "보류 표시를 읽지 못했다"


def inspect(run_dir: Path, deck: Path | None, meta_path: Path | None,
            label: str, prefix: str = "") -> Verdict:
    """`label`은 보고에 쓸 이름, `prefix`는 산출물 접두어("" / "pre_")."""
    verdict = Verdict()
    if deck is None and meta_path is None:
        return verdict

    held = hold_reason(run_dir)
    if held:
        verdict.blocking.append(f"{label} 보류 — {held}")

    if meta_path is None or not meta_path.is_file():
        verdict.blocking.append(
            f"{label} 덱은 있는데 {prefix}run.meta.json이 없다 — 무엇으로 만들었는지 모른다")
        return verdict

    meta = _load(meta_path)
    if not isinstance(meta, dict):
        verdict.blocking.append(f"{label} {meta_path.name}을 읽지 못했다")
        return verdict

    # apkg를 도로 열어 센 값이다. 이게 어긋나면 덱이 내용과 다른 것을 담고 있다.
    verified = meta.get("verified") or {}
    count = int(meta.get("item_count") or 0)
    notes_in_apkg = verified.get("notes")
    if notes_in_apkg is None:
        verdict.blocking.append(f"{label} apkg 검증 기록이 없다 — 덱이 온전한지 모른다")
    elif int(notes_in_apkg) != count:
        verdict.blocking.append(
            f"{label} apkg에 노트가 {notes_in_apkg}장인데 item_count는 {count}장이다")

    missing = verified.get("missing_media") or []
    if missing:
        verdict.blocking.append(
            f"{label} 카드가 부르는데 패키지에 없는 이미지 {len(missing)}개: {missing[:3]}")

    defects = meta.get("reproduce_defects") or []
    if defects:
        verdict.blocking.append(
            f"{label} 문항 결함으로 갈린 카드가 덱에 {len(defects)}장 남아 있다 "
            f"({', '.join(defects[:5])}) — 빌드가 거부했어야 한다")

    flags = meta.get("review_flags") or {}
    if flags:
        verdict.notes.append(
            f"{label} 검토 표시 " + " · ".join(f"{k} {v}장" for k, v in sorted(flags.items()))
            + " — 카드 뒷면 경고 박스를 확인할 것")

    mix = meta.get("reproduce") or {}
    unsure = sum(int(mix.get(k) or 0) for k in ("different", "partial"))
    if unsure:
        verdict.notes.append(
            f"{label} 재현이 갈린 카드 {unsure}장 (같음 {mix.get('same', 0)}장) — "
            "문항 결함은 아니라고 판정된 것들이다")

    if meta.get("dropped"):
        verdict.notes.append(f"{label} 검증에서 {meta['dropped']}장이 hard로 떨어졌다")
    untouched = meta.get("untouched_slides") or []
    if untouched:
        verdict.notes.append(f"{label} 문항이 없는 슬라이드 {len(untouched)}장: {untouched}")
    orphan = meta.get("objectives_without_card") or []
    if orphan:
        verdict.notes.append(f"{label} 카드가 안 붙은 학습목표 {len(orphan)}개")
    if meta.get("similar_pairs"):
        verdict.notes.append(f"{label} 비슷한 카드 쌍 {meta['similar_pairs']}건")
    if meta.get("web_excluded"):
        verdict.notes.append(
            f"{label} 그림 카드 {meta['web_excluded']}장은 웹 풀이에서 빠진다 (덱에는 있다)")
    return verdict
