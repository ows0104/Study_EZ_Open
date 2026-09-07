"""마스터 종/표본 테이블 병합 · 검증 · CSV 내보내기.

    uv run --python 3.13 python scripts/build_master.py

data/species/*.json -> data/species.json
data/specimens/*.json -> data/specimens.json
+ data/species.csv, data/specimens.csv (엑셀 검토용)
"""

import csv
import glob
import json
import os
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):  # 윈도우 콘솔 cp949 대응
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

SPECIES_REQUIRED = [
    "id", "scientific_name", "name_ko", "group", "transmission_mode",
    "transmission_route", "infective_stage", "habitat", "exam_notes",
]
SPECIMEN_REQUIRED = [
    "id", "species_id", "specimen_type", "label_ko", "label_en", "key_features",
]
SPECIMEN_TYPES = {"충란", "충체", "조직", "gross", "혈액도말"}
GROUPS = {"선충", "흡충", "조충", "원충", "말라리아", "의용곤충"}


def load_dir(subdir):
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA, subdir, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            chunk = json.load(fh)
        for row in chunk:
            row["_file"] = os.path.basename(path)
        rows.extend(chunk)
    return rows


def validate(species, specimens):
    errors, warnings = [], []

    sp_ids = [s["id"] for s in species]
    for sid, n in Counter(sp_ids).items():
        if n > 1:
            errors.append(f"species id 중복: {sid} ({n}회)")
    sp_ids = set(sp_ids)

    names = [s["scientific_name"] for s in species]
    for name, n in Counter(names).items():
        if n > 1:
            errors.append(f"학명 중복: {name} ({n}회)")

    for s in species:
        for field in SPECIES_REQUIRED:
            if not s.get(field):
                errors.append(f"[{s.get('id')}] 필수 필드 누락: {field}")
        if s.get("group") not in GROUPS:
            errors.append(f"[{s['id']}] 알 수 없는 group: {s.get('group')}")

    spec_ids = [x["id"] for x in specimens]
    for xid, n in Counter(spec_ids).items():
        if n > 1:
            errors.append(f"specimen id 중복: {xid} ({n}회)")
    spec_ids = set(spec_ids)

    for x in specimens:
        for field in SPECIMEN_REQUIRED:
            if not x.get(field):
                errors.append(f"[{x.get('id')}] 필수 필드 누락: {field}")
        if x.get("species_id") not in sp_ids:
            errors.append(f"[{x['id']}] species_id가 종 테이블에 없음: {x.get('species_id')}")
        if x.get("specimen_type") not in SPECIMEN_TYPES:
            errors.append(f"[{x['id']}] 알 수 없는 specimen_type: {x.get('specimen_type')}")
        for ref in x.get("confusable_with", []):
            if ref not in spec_ids and ref not in sp_ids:
                warnings.append(f"[{x['id']}] confusable_with 미해결 참조: {ref}")

    covered = {x["species_id"] for x in specimens}
    for s in species:
        if s["id"] in covered and s.get("distractor_only"):
            errors.append(f"[{s['id']}] distractor_only인데 표본이 연결됨")
        if s["id"] not in covered and not s.get("distractor_only"):
            warnings.append(f"[{s['id']}] {s['name_ko']} - 연결된 표본이 없음. distractor_only 지정 필요")

    return errors, warnings


def to_csv(rows, path, columns):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            out = []
            for col in columns:
                val = row.get(col, "")
                if isinstance(val, list):
                    val = " | ".join(str(v) for v in val)
                elif isinstance(val, bool):
                    val = "O" if val else "X"
                elif val is None:
                    val = ""
                out.append(val)
            writer.writerow(out)


def main():
    species = load_dir("species")
    specimens = load_dir("specimens")

    errors, warnings = validate(species, specimens)

    with open(os.path.join(DATA, "species.json"), "w", encoding="utf-8") as fh:
        json.dump(species, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA, "specimens.json"), "w", encoding="utf-8") as fh:
        json.dump(specimens, fh, ensure_ascii=False, indent=2)

    to_csv(species, os.path.join(DATA, "species.csv"), [
        "id", "scientific_name", "name_ko", "group", "subgroup", "size",
        "transmission_mode", "transmission_route", "source", "infective_stage",
        "intermediate_host", "definitive_host", "habitat", "lung_migration",
        "disease_ko", "disease_en", "symptoms", "diagnosis", "treatment",
        "epidemiology", "vector_for", "exam_notes", "aliases",
    ])
    to_csv(specimens, os.path.join(DATA, "specimens.csv"), [
        "id", "species_id", "specimen_type", "stage", "label_ko", "label_en",
        "size_um", "size_group", "stain", "magnification", "key_features",
        "structures", "confusable_with", "note",
    ])

    print(f"종        {len(species):3d}건")
    print(f"표본      {len(specimens):3d}건")
    print()
    print("─ 분류군별 종 수")
    for g, n in Counter(s["group"] for s in species).most_common():
        print(f"    {g:<8} {n:3d}")
    print()
    print("─ 표본 유형별")
    for t, n in Counter(x["specimen_type"] for x in specimens).most_common():
        print(f"    {t:<8} {n:3d}")
    print()
    structures = Counter()
    for x in specimens:
        structures.update(x.get("structures", []))
    print(f"─ indicator 문제로 낼 수 있는 구조물: {len(structures)}종")
    print("    " + ", ".join(sorted(structures)))
    print()

    if warnings:
        print(f"경고 {len(warnings)}건")
        for w in warnings:
            print(f"    ! {w}")
        print()
    if errors:
        print(f"오류 {len(errors)}건")
        for e in errors:
            print(f"    X {e}")
        return 1
    print("검증 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
