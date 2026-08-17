"""빌드한 덱의 대장(臺帳). runs/INDEX.md 와 runs/index.json.

한 학기에 강의는 수십 편이고, 어느 강의를 이미 덱으로 만들었는지는 runs/ 밑의
디렉터리 이름만 봐서는 알 수 없다. 카드가 몇 장이었는지, 족보 검토 플래그가
붙은 게 있었는지, 다시 돌려야 할 강의가 무엇인지는 더더욱 그렇다.

빌드가 끝날 때마다 여기에 한 줄씩 쌓는다. 다시 빌드하면 같은 줄을 덮어쓴다.
"""

from __future__ import annotations

import json
from pathlib import Path

INDEX_JSON = "index.json"
INDEX_MD = "INDEX.md"

_HEADER = """# 빌드한 Anki 덱

`quiz/build.py`가 자동으로 갱신한다. 손으로 고치지 말 것 — 다음 빌드에 덮어쓰인다.

"""

_COLUMNS = [
    ("lecture_id", "강의"),
    ("lecture_title", "제목"),
    ("item_count", "카드"),
    ("sources", "강의록/족보"),
    ("occlusion", "오클루전"),
    # 족보 정오 플래그 / 자료 주의 경고. 둘은 다른 것이다 - 앞은 족보 문항의 정답을
    # 의심한 것이고 뒤는 자료 자체가 의심스러운 것이다(item-rules §4.5).
    ("review_flagged", "검토"),
    ("source_warned", "자료주의"),
    ("uncovered", "빈 슬라이드"),
    ("built_at", "빌드"),
]


def _row_values(entry: dict) -> list[str]:
    sources = entry.get("sources") or {}
    unused = entry.get("slides_unused") or []
    return [
        str(entry.get("lecture_id", "")),
        str(entry.get("lecture_title", ""))[:40],
        str(entry.get("item_count", "")),
        f"{sources.get('lecture', 0)}/{sources.get('jokbo', 0)}",
        str(entry.get("occlusion", 0)) or "0",
        str(entry.get("review_flagged", 0)),
        str(entry.get("source_warned", 0)),
        str(len(unused)),
        str(entry.get("built_at", ""))[:16].replace("T", " "),
    ]


def render_markdown(entries: list[dict]) -> str:
    lines = [_HEADER.rstrip() + "\n"]
    lines.append("| " + " | ".join(label for _, label in _COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(_COLUMNS)) + "|")
    for entry in entries:
        lines.append("| " + " | ".join(_row_values(entry)) + " |")

    lines.append("")
    lines.append("## 덱 이름과 파일")
    lines.append("")
    for entry in entries:
        apkg = entry.get("apkg", "")
        name = Path(apkg).name if apkg else "-"
        lines.append(f"- `{entry.get('lecture_id')}` — {entry.get('deck_name')} → `{name}`")

    flagged = [e for e in entries if e.get("review_flagged")]
    if flagged:
        lines.append("")
        lines.append("## 족보 정오 검토가 붙은 덱")
        lines.append("")
        for entry in flagged:
            lines.append(
                f"- `{entry.get('lecture_id')}` — {entry['review_flagged']}장. "
                "카드 뒷면 경고 박스를 직접 확인할 것")

    empty = [e for e in entries if e.get("slides_unused")]
    if empty:
        lines.append("")
        lines.append("## 카드가 없는 슬라이드")
        lines.append("")
        for entry in empty:
            lines.append(f"- `{entry.get('lecture_id')}` — {entry['slides_unused']}")

    return "\n".join(lines) + "\n"


def update_index(runs_root, meta: dict) -> Path:
    """meta 한 건을 대장에 반영한다. 같은 lecture_id는 덮어쓴다."""
    runs_root = Path(runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    json_path = runs_root / INDEX_JSON

    entries: list[dict] = []
    if json_path.exists():
        try:
            entries = json.loads(json_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            entries = []

    entry = {key: meta.get(key) for key in (
        "lecture_id", "lecture_title", "deck_name", "apkg", "built_at",
        "item_count", "sources", "review_flagged", "source_warned",
        "slides_unused", "occlusion",
    )}
    entries = [e for e in entries if e.get("lecture_id") != entry["lecture_id"]]
    entries.append(entry)
    entries.sort(key=lambda e: str(e.get("lecture_id") or ""))

    json_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = runs_root / INDEX_MD
    md_path.write_text(render_markdown(entries), encoding="utf-8")
    return md_path
