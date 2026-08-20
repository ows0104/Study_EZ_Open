"""프로필 — 밀도와 교수님 맞춤 지침. **이 파일은 저장과 CLI만 한다.**

규칙 문자열은 `prompt.py`에 있다 (그쪽이 규칙 문서다). 여기는 값을 받아
`runs/<id>/profile.json`에 남기고, 뒤 단계가 그걸 읽는다.

## 왜 스타일이 열거형이 아닌가

기준은 meddeck 사이트의 생성 설정 패널이다. **두 칸의 생김새가 서로 다르고, 그
차이를 그대로 옮긴다.**

    카드 밀도        <select> 셋 — 핵심만 / 균형 있게 / 빠짐없이
    교수님 맞춤 지침  <textarea maxLength=4000> — 자유 입력, 선택 사항

`webapp/app/shared/constants/prompts.ts`의 네 개(`professorPromptExamples`)는
고르는 목록이 아니라 **예시 버튼**이다. 누르면 입력란에 붙여넣고, 붙여넣은 뒤
고쳐 쓴다 — 선택 상태 표시조차 문자열 비교다
(`professorPrompt === example.text`, `GenerationSettingsPanel.tsx`).

스타일을 열거형으로 박으면 내가 `prompt.py`에 새 규칙 문장 셋을 쓰는 일이 되고,
그건 인터뷰에 없는 규칙이다 (`CLAUDE.md` 「규칙 문서를 쓰는 법」 ①).
**자유 텍스트는 규칙이 아니라 관리자의 지시라서 그 문제가 없다.**

## 자유 텍스트로 못 하는 것이 하나 있다

코드 거동은 문자열로 못 바꾼다. 필기를 강의록 급 근거로 올리는 것(2026-08-20
관리자 승인)은 프롬프트 문단 하나가 아니라 세 자리를 건드린다.

    prompt.annotation_section()   ⑤ 문단이 갈린다
    assemble._file_list()         필기본을 언제 붙이나
    validate                      필기만(exam_hit 없음) 카드를 센다

그래서 `annotation_as_evidence`만 따로 불리언으로 둔다. 예시 중 「필기 중심」을
고르면 기본으로 켜지고, 플래그로 덮어쓸 수 있다.

## 자동으로 안 고른다

meddeck은 파일명에서 교수 이름을 찾아 지침을 붙였다(`neuro_professor_instruction`).
여기서는 **안 한다.** 프로필은 부르는 사람이 정한다.

관리자가 관찰 하나를 줬다 (2026-08-20) — *"실습 수업은 높은 확률로 필기 중심이 될
거야."* 규칙으로 굳히지 않는다. 굳히려면 먼저 물어야 하고(`CLAUDE.md` ③),
가진 실습 두 편이 아직 갈린다.

    260813_05  실습 2   annotation 68/140 (49%)
    260812_05  실습 1   annotation  2/37  (5%)

풀리는 조건: 실습 편이 몇 개 더 쌓여 한쪽으로 몰리는 것.

## 왜 `prep.json`이 아닌가

거기 쓰려면 `quiz/prep.py`를 고쳐야 하는데 v1은 비교 기준선이라 안 건드린다
(`quiz2/README.md` 「조심할 것」).

**프로필이 없으면 기본값이고, 기본값이면 문구가 지금과 글자 하나까지 같다.**
기존 편은 아무것도 안 달라진다.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz2.prompt import DENSITIES, DENSITY_DEFAULT, budget_per_slide  # noqa: E402

FILENAME = "profile.json"

# meddeck의 <textarea maxLength={4000}>과 같은 값.
STYLE_NOTE_MAX = 4000

# `prompts.ts`의 `professorPromptExamples`를 그대로 옮겼다.
# **예시다. 목록이 아니다** — 골라서 고쳐 쓰라고 있는 것이고, 코드는 이 문자열을
# 어디서도 검사하지 않는다. 지우거나 늘려도 파이프라인은 안 깨진다.
STYLE_EXAMPLES = {
    "jokbo": {
        "label": "족보 중심",
        "text": "족보에서 반복된 개념과 선지를 우선해 카드화하세요. 주변 내용은"
                " 줄이고, 문제 풀이에 필요한 강의록 근거를 함께 담으세요.",
    },
    "cornering": {
        "label": "코너링 중심",
        "text": "핵심 내용뿐 아니라 지엽적인 세부사항과 예외도 빠짐없이 카드화하세요."
                " 서로 헷갈리는 항목은 비교해서 물어보세요.",
    },
    "essay": {
        "label": "서술형 중심",
        "text": "서술형 답안에 필요한 핵심 키워드와 흐름을 중심으로 카드화하세요."
                " 원인, 과정과 결과가 연결되도록 구성하세요.",
    },
    "note": {
        "label": "필기 중심",
        "text": "학생 필기와 표시가 있는 내용을 우선해 카드화하세요. 필기가 가리키는"
                " 본문, 그림과 표의 핵심을 질문으로 바꾸세요.",
        # 이 예시만 코드 거동을 함께 켠다. 위 문장은 "우선해"까지만 말하는데
        # 관리자가 승인한 것은 그보다 세다 — 강의록 급 근거로 올리는 것이다.
        "annotation_as_evidence": True,
    },
}


@dataclass(frozen=True)
class Profile:
    """`runs/<id>/profile.json`의 내용. 없으면 이 기본값이 곧 지금 동작이다."""

    density: str = DENSITY_DEFAULT
    style_note: str = ""
    annotation_as_evidence: bool = False

    @property
    def is_default(self) -> bool:
        return self == Profile()

    @property
    def budget_per_slide(self) -> float:
        return budget_per_slide(self.density)

    def describe(self) -> str:
        bits = [f"밀도 {self.density}({DENSITIES[self.density]['label']})"]
        if self.style_note:
            head = self.style_note.replace("\n", " ")
            bits.append(f"지침 {len(self.style_note)}자 — {head[:28]}…"
                        if len(head) > 28 else f"지침 — {head}")
        else:
            bits.append("지침 없음")
        if self.annotation_as_evidence:
            bits.append("**필기를 근거로 승격**")
        return " | ".join(bits)


def normalize(density: str | None = None, style_note: str | None = None,
               annotation_as_evidence: bool | None = None) -> Profile:
    """값을 다듬어 `Profile`로. 모르는 밀도는 조용히 기본값이 된다."""
    d = str(density or DENSITY_DEFAULT).strip().lower()
    if d not in DENSITIES:
        d = DENSITY_DEFAULT
    note = str(style_note or "").strip()[:STYLE_NOTE_MAX]
    return Profile(density=d, style_note=note,
                   annotation_as_evidence=bool(annotation_as_evidence))


def load(run_dir: str | Path) -> Profile:
    """없으면 기본값. **없는 것이 정상이다** — 지금까지의 모든 편이 그렇다."""
    path = Path(run_dir) / FILENAME
    if not path.exists():
        return Profile()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return normalize(raw.get("density"), raw.get("style_note"),
                     raw.get("annotation_as_evidence"))


def write(run_dir: str | Path, profile: Profile) -> Path:
    path = Path(run_dir) / FILENAME
    path.write_text(json.dumps(asdict(profile), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="프로필을 정한다 (0단계와 0.5단계 사이). 안 부르면 기본값이다")
    parser.add_argument("run_dir")
    parser.add_argument("--density", default=None, choices=sorted(DENSITIES),
                        help="카드 밀도. 기본 normal")
    parser.add_argument("--style-note", default=None,
                        help=f"교수님 맞춤 지침. 자유 텍스트 {STYLE_NOTE_MAX}자까지")
    parser.add_argument("--style-example", default=None, choices=sorted(STYLE_EXAMPLES),
                        help="예시를 --style-note에 붙여넣는다 (--style-note가 이긴다)")
    parser.add_argument("--annotation-as-evidence", dest="ann",
                        action="store_true", default=None,
                        help="필기를 강의록과 같은 자격의 근거로 올린다")
    parser.add_argument("--no-annotation-as-evidence", dest="ann",
                        action="store_false",
                        help="예시가 켠 것을 되돌린다")
    parser.add_argument("--show", action="store_true", help="지금 값만 보여준다")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)

    if args.show:
        print(f"[profile] {load(run_dir).describe()}")
        return 0

    current = load(run_dir)
    example = STYLE_EXAMPLES.get(args.style_example or "")
    note = args.style_note
    if note is None:
        note = example["text"] if example else current.style_note
    ann = args.ann
    if ann is None:
        ann = (example.get("annotation_as_evidence", False) if example
               else current.annotation_as_evidence)

    profile = normalize(args.density or current.density, note, ann)
    path = write(run_dir, profile)

    print(f"[profile] {profile.describe()}")
    print(f"  예산 배수: 슬라이드 × {profile.budget_per_slide}"
          + ("  (관리자 확정)" if profile.density == DENSITY_DEFAULT
             else "  ⚠ 아직 실측 안 된 값이다"))
    print(f"  → {path}")
    if profile.annotation_as_evidence:
        print("  필기 승격이 켜졌다. 효과는 validate의 "
              "「필기만(exam_hit 없음)」 수로 잰다 (밑값 0에 붙어 있다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
