"""해부학 문항의 표집 가중치를 기출빈도 워크북에서 다시 계산한다.

    uv run --python 3.13 --with pandas --with openpyxl python \
        scripts/update_exam_trends.py <워크북.xlsx> --db-dir <폴더>

가중치는 `sqrt(n + 1)` 이다(`n` 은 기출 횟수). 0회인 구조물도 뽑히되 드물게 뽑히고,
10회짜리가 1회짜리의 열 배가 아니라 2.3배가 된다. 영역 편중을 막는 것은 여기가
아니라 화면 쪽이다(`web/anatomy/_template.html` 의 `selected_items`).

## 2026-09-14 에 배포본에서 회수했다

**원본이 배포 저장소에만 있었다.** 해부학 `index.html` 넷이 그랬던 것과 같은
모양이다. 게다가 배포본 루트에 있어서 `spotter.studyez.kr/update_exam_trends.py`
로 **누구나 받아 갈 수 있었다.**

옮기면서 경로를 인자로 뺐다. 그 전에는 자기 폴더를 기준으로 `<과목>/quiz_db.js`
를 찾고 워크북을 `../outputs/<uuid>/…` 에서 찾았는데, **둘 다 지금은 없는 자리다.**

## 문항 DB 는 이 저장소에 없다

2026-09-06 에 배포 저장소에서 걷어 냈다 — 배포본 루트는 공개로 서빙되므로 거기
있으면 로그인 없이 문항이 통째로 나간다. 지금은 R2 에 있고 로그인한 사람에게만
서명 URL 로 간다(`scripts/upload_subject.py`).

그래서 이 스크립트는 **손에 든 사본**을 고친다. 고친 뒤 올리는 것은 따로다.

    python scripts/update_exam_trends.py <워크북> --db-dir <폴더>   가중치 다시 계산
    python scripts/upload_subject.py <폴더>/exam1                    R2 로 올린다

2026-09-14 기준으로 사본과 워크북이 있는 자리는 여기다. 기생충학 쪽 `build/` 와
같은 이유로 저장소에 안 넣는다.

    ../BellExam_Neuro/neuro-spotter-pages/<과목>/quiz_db.js
    ../BellExam_Neuro/outputs/019f615f-…/인체해부학_차시별_구조물_기출빈도.xlsx

`neuro` 는 대상이 아니다. 워크북이 1·2·3차 시트만 들고 있다.
"""

import argparse
import json
import math
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
# 문항 DB 사본이 놓이는 기본 자리. 기생충학의 `build/` 와 같은 칸이고 같이 무시된다.
DEFAULT_DB_DIR = ROOT / "build" / "anatomy"
TARGETS = {
    "exam1": "1차",
    "trunk": "2차",
    "head-neck": "3차",
}

ABBREVIATIONS = [
    (r"\brt\.?\b", "right"), (r"\blt\.?\b", "left"),
    (r"\bant\.?\b", "anterior"), (r"\bpost\.?\b", "posterior"),
    (r"\bsup\.?\b", "superior"), (r"\binf\.?\b", "inferior"),
    (r"\bmed\.?\b", "medial"), (r"\blat\.?\b", "lateral"),
    (r"\bint\.?\b", "internal"), (r"\bext\.?\b", "external"),
    (r"\bcomm\.?\b", "common"), (r"\blig\.?\b", "ligament"),
    (r"\baa\.?\b", "arteries"), (r"\ba\.?\b", "artery"),
    (r"\bvv\.?\b", "veins"), (r"\bv\.?\b", "vein"),
    (r"\bnn\.?\b", "nerves"), (r"\bn\.?\b", "nerve"),
    (r"\bmm\.?\b", "muscles"), (r"\bm\.?\b", "muscle"),
    (r"\bbr\.?\b", "branch"),
]


def normalize_korean(value: object) -> str:
    text = "" if pd.isna(value) else str(value).lower()
    text = text.replace("첫째", "1").replace("둘째", "2").replace("셋째", "3")
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def normalize_english(value: object, drop_laterality: bool = False) -> str:
    text = "" if pd.isna(value) else str(value).lower()
    for pattern, replacement in ABBREVIATIONS:
        text = re.sub(pattern, replacement, text)
    text = text.replace("peroneus", "fibularis").replace("peroneal", "fibular")
    text = text.replace("gall bladder", "gallbladder")
    text = text.replace("primary bronchus", "main bronchus")
    text = text.replace("principal bronchus", "main bronchus")
    text = text.replace("bicuspid valve", "mitral valve")
    text = text.replace("profunda femoral", "deep femoral")
    text = re.sub(r"\bteniae\b|\btaeniae\b", "taenia", text)
    text = re.sub(r"\b(the|of|muscle|muscles)\b", " ", text)
    tokens = re.findall(r"[a-z0-9]+", text)
    singular = {"arteries": "artery", "veins": "vein", "nerves": "nerve", "ligaments": "ligament"}
    tokens = [singular.get(token, token) for token in tokens]
    if drop_laterality:
        tokens = [token for token in tokens if token not in {"left", "right"}]
    return "|".join(sorted(tokens))


def year_sort_key(value: str) -> tuple[int, int]:
    match = re.match(r"(19|20)(\d{2})(?:\((\d+)\))?", value)
    if not match:
        return (0, 0)
    return (int(match.group(1) + match.group(2)), int(match.group(3) or 0))


def combine_rows(rows: list[dict]) -> dict:
    years = sorted(
        {year for row in rows for year in row["years"]},
        key=year_sort_key,
        reverse=True,
    )
    return {
        "frequency": max([len(years), *[row["frequency"] for row in rows]]),
        "years": years,
    }


def load_lookup(workbook_path: Path, sheet_name: str) -> tuple[dict, dict, list[tuple[str, dict]]]:
    frame = pd.read_excel(workbook_path, sheet_name=sheet_name, header=3)
    rows = []
    for _, row in frame.iterrows():
        korean = "" if pd.isna(row.get("해부 구조물 국문")) else str(row.get("해부 구조물 국문")).strip()
        english = "" if pd.isna(row.get("해부 구조물 영문")) else str(row.get("해부 구조물 영문")).strip()
        if not korean and not english:
            continue
        frequency = int(float(row.get("출제빈도", 0) or 0))
        years = re.findall(r"(?:19|20)\d{2}(?:\(\d+\))?", str(row.get("출제년도", "")))
        rows.append({"korean": korean, "english": english, "frequency": frequency, "years": years})

    ko_groups: dict[str, list[dict]] = {}
    en_groups: dict[str, list[dict]] = {}
    for row in rows:
        ko_key = normalize_korean(row["korean"])
        en_key = normalize_english(row["english"])
        if ko_key:
            ko_groups.setdefault(ko_key, []).append(row)
        if en_key:
            en_groups.setdefault(en_key, []).append(row)

    ko_lookup = {key: combine_rows(group) for key, group in ko_groups.items()}
    en_lookup = {key: combine_rows(group) for key, group in en_groups.items()}
    fuzzy_candidates = list(en_lookup.items())
    return ko_lookup, en_lookup, fuzzy_candidates


def find_match(item: dict, ko_lookup: dict, en_lookup: dict, fuzzy_candidates: list[tuple[str, dict]]):
    ko_key = normalize_korean(item.get("answer_ko", ""))
    if ko_key and ko_key in ko_lookup:
        return ko_lookup[ko_key], "korean"

    en_values = [item.get("answer_en", ""), item.get("raw_label", "")]
    for value in en_values:
        en_key = normalize_english(value)
        if en_key and en_key in en_lookup:
            return en_lookup[en_key], "english"
        en_base_key = normalize_english(value, drop_laterality=True)
        if en_base_key and en_base_key != en_key and en_base_key in en_lookup:
            return en_lookup[en_base_key], "english-base"
        without_parenthetical = re.sub(r"\s*\([^)]*\)", "", str(value)).strip()
        parent_key = normalize_english(without_parenthetical)
        if parent_key and parent_key != en_key and parent_key in en_lookup:
            return en_lookup[parent_key], "english-parent"

    query = normalize_english(item.get("answer_en", ""))
    if len(query) < 7:
        return None, "none"
    ranked = sorted(
        ((SequenceMatcher(None, query, key).ratio(), key, record) for key, record in fuzzy_candidates),
        reverse=True,
    )
    if not ranked:
        return None, "none"
    best_score, _, best_record = ranked[0]
    next_score = ranked[1][0] if len(ranked) > 1 else 0
    if best_score >= 0.96 and best_score - next_score >= 0.02:
        return best_record, "fuzzy"
    return None, "none"


def load_quiz_db(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig").strip()
    match = re.match(r"^const\s+QUIZ_DB\s*=\s*(\[.*\])\s*;?\s*$", text, re.S)
    if not match:
        raise ValueError(f"QUIZ_DB 형식을 읽을 수 없습니다: {path}")
    return json.loads(match.group(1))


def save_quiz_db(path: Path, items: list[dict]) -> None:
    # Keep the repository's existing PowerShell-style JSON layout so refreshing
    # frequency metadata changes values without rewriting every line.
    layouts = {
        "exam1": (4, (",", ":  ")),
        "trunk": (2, (",", ": ")),
        "head-neck": (4, (",", ": ")),
    }
    indent, separators = layouts.get(path.parent.name, (2, (",", ": ")))
    payload = json.dumps(items, ensure_ascii=False, indent=indent, separators=separators)
    path.write_text(f"const QUIZ_DB = {payload};\n", encoding="utf-8")


def update_target(directory: str, sheet_name: str, workbook_path: Path, db_dir: Path) -> dict:
    db_path = db_dir / directory / "quiz_db.js"
    items = load_quiz_db(db_path)
    ko_lookup, en_lookup, fuzzy_candidates = load_lookup(workbook_path, sheet_name)

    methods = Counter()
    unmatched = Counter()
    weighted = 0
    for item in items:
        match, method = find_match(item, ko_lookup, en_lookup, fuzzy_candidates)
        methods[method] += 1
        if match:
            frequency = int(match["frequency"])
            years = match["years"]
            weighted += int(frequency > 0)
        else:
            frequency = 0
            years = []
            unmatched[str(item.get("answer_en") or item.get("answer_ko") or "(빈 정답)")] += 1

        item["past_count"] = frequency
        item["exam_years"] = ", ".join(years)
        item["recent_year"] = str(max((year_sort_key(year)[0] for year in years), default=""))
        item["exam_weight"] = math.sqrt(frequency + 1)

    save_quiz_db(db_path, items)
    return {
        "directory": directory,
        "sheet": sheet_name,
        "questions": len(items),
        "matched": len(items) - methods["none"],
        "weighted": weighted,
        "methods": dict(methods),
        "top_unmatched": unmatched.most_common(12),
    }


def validate_formula(db_dir: Path) -> None:
    for directory in TARGETS:
        items = load_quiz_db(db_dir / directory / "quiz_db.js")
        for item in items:
            expected = math.sqrt(max(float(item.get("past_count", 0)), 0) + 1)
            if not math.isclose(float(item.get("exam_weight", 0)), expected, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"가중치 검증 실패: {directory} / {item.get('quiz_id')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="해부학 기출빈도를 문항 DB의 √(n+1) 가중치로 반영")
    parser.add_argument("workbook", type=Path, help="기출빈도 워크북 (.xlsx)")
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR,
                        help=f"<과목>/quiz_db.js 가 든 폴더 (기본: {DEFAULT_DB_DIR})")
    args = parser.parse_args()

    workbook_path = args.workbook.resolve()
    if not workbook_path.exists():
        raise SystemExit(f"워크북이 없습니다: {workbook_path}")

    db_dir = args.db_dir.resolve()
    # **없는 폴더를 만들어 주지 않는다.** 만들면 「대상 0개」로 조용히 끝나고,
    # 화면에는 성공처럼 보인다. 이 저장소가 「없다로 읽히는 0」이라 부르는 것이다.
    missing = [d for d in TARGETS if not (db_dir / d / "quiz_db.js").is_file()]
    if missing:
        raise SystemExit(
            f"문항 DB 를 못 찾았습니다: {', '.join(missing)}\n"
            f"  본 자리: {db_dir}/<과목>/quiz_db.js\n"
            "  문항 DB 는 저장소에 없다(공개로 서빙되는 자리를 피한다). 손에 든 사본을\n"
            "  --db-dir 로 지정해라. 2026-09-14 기준 사본은\n"
            "  ../BellExam_Neuro/neuro-spotter-pages/ 에 있다."
        )

    report = [update_target(directory, sheet, workbook_path, db_dir)
              for directory, sheet in TARGETS.items()]
    validate_formula(db_dir)
    print(json.dumps({"workbook": str(workbook_path), "db_dir": str(db_dir),
                      "formula": "sqrt(n + 1)", "targets": report},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
