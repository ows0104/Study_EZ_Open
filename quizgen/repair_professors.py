"""원본 교수표를 다시 읽어 저장된 족보 조각의 교수 메타데이터만 갱신한다."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import fitz

from . import jokbo as J

_EDITIONS: dict[tuple, dict] = {}


def edition_for(path: Path) -> dict:
    key = (str(path.resolve()), path.stat().st_mtime_ns)
    if key not in _EDITIONS:
        with fitz.open(path) as doc:
            _EDITIONS[key] = J.parse_edition(doc)
    return copy.deepcopy(_EDITIONS[key])


def signature(q: dict) -> str:
    return json.dumps({k: v for k, v in q.items() if k not in ("src", "by", "reference", "body", "span", "bank")},
                      ensure_ascii=False, sort_keys=True)


def content_digest(payload: dict) -> str:
    return hashlib.sha256("\n".join(sorted(signature(q) for q in payload["questions"])).encode()).hexdigest()


def section(payload: dict) -> J.Section:
    sec = J.Section(lecture_key=payload["lecture_key"], title=payload["title"],
                    may_contain=[(m["lecture_key"], m["title"]) for m in payload.get("may_contain", [])])
    fields = set(J.Question.__dataclass_fields__) - {"body", "span", "bank"}
    sec.questions = [J.Question(**{k: v for k, v in q.items() if k in fields}) for q in payload["questions"]]
    return sec


def repair_payload(payload: dict, profs: dict, authors: dict[int, dict[str, list[str]]]) -> tuple[dict, int]:
    repaired = copy.deepcopy(payload)
    key = payload["lecture_key"]
    stats = repaired["stats"]
    stats["professors_by_year"] = profs.get(key, stats.get("professors_by_year", {}))
    absorbed = {}
    for m in payload.get("may_contain", []):
        for col, names in profs.get(m["lecture_key"], {}).items():
            absorbed[col] = list(dict.fromkeys(absorbed.get(col, []) + names))
    if absorbed or "absorbed_professors_by_year" in stats:
        stats["absorbed_professors_by_year"] = absorbed
    count = 0
    for q in repaired["questions"]:
        author = authors.get(q.get("src"), {}).get(signature(q))
        if author is not None and q.get("by") != author:
            q["by"] = author
            count += 1
    updated = J.repeat_stats(section(repaired), {key: stats["professors_by_year"]})
    for name in ("professor_2026", "professor_changed_2026", "jokbo_weight_hint"):
        stats[name] = updated[name]
    assert content_digest(payload) == content_digest(repaired), "교수 갱신 중 문항 내용 변경"
    return repaired, count


def repair_cut(cut: Path, *, backup: Path | None = None) -> dict:
    index_path = cut / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    cut_info = json.loads((cut / "cut.json").read_text(encoding="utf-8")) if (cut / "cut.json").is_file() else {}
    source = cut_info.get("source", {}).get("path") or index.get("source_path")
    if not source or not Path(source).is_file():
        return {"cut": str(cut), "skipped": "등록된 원본 PDF 없음"}
    edition = edition_for(Path(source))
    authors, evidence, merges = {}, [], []
    for number, old in enumerate(index.get("older_sources") or cut_info.get("older_sources") or []):
        path = Path(old["path"])
        older = edition_for(path)
        evidence.append({"source": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "lectures": len(older["profs"]), "warning": older["warn"]})
        authors[number] = {}
        for sec in older["sections"]:
            for q in sec.questions:
                fields = {k: v for k, v in asdict(q).items() if k not in ("body", "span", "bank")}
                # 조각에는 None 기본값이 생략돼 있을 수 있다. 실제 저장 형식과 맞춘다.
                fields = {k: v for k, v in fields.items() if not (k in ("src", "by", "reference") and v is None)}
                authors[number][signature(fields)] = J._older_author(sec, older["profs"], q.year, J._n_lectures(sec.lecture_key))
        merges.append(J.merge_older(edition["sections"], edition["lectures"], edition["profs"], older, number))
    changed, authored, affected = [], 0, []

    def write(path: Path, text: str):
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            return
        changed.append(str(path))
        if backup is None:
            return
        target = backup / cut.parent.name / cut.name / path.relative_to(cut)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and not target.exists():
            target.write_bytes(path.read_bytes())
        tmp = path.with_name(path.name + ".professors.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    for entry in index["lectures"]:
        base = cut / (entry["file"] + ".json")
        if not base.is_file():
            continue
        original = json.loads(base.read_text(encoding="utf-8"))
        if original["lecture_key"] == "PRAC":
            continue
        repaired, count = repair_payload(original, edition["profs"], authors)
        if repaired == original:
            continue
        authored += count
        affected.append({"key": original["lecture_key"], "title": original["title"], "authorsUpdated": count,
                         "questions": len(original["questions"]), "contentPreserved": True})
        write(base, json.dumps(repaired, ensure_ascii=False, indent=2))
        write(base.with_suffix(".md"), J.to_markdown(section(repaired), repaired["stats"]))
        for derivative in sorted((cut / "교수별").glob("*/" + base.name)):
            old = json.loads(derivative.read_text(encoding="utf-8"))
            professors = old.get("stats", {}).get("professor_filter", {}).get("professors") or derivative.parent.name.split("·")
            own_repaired, _ = repair_payload(old, edition["profs"], authors)
            filtered, _ = J.split_by_professor(own_repaired, professors)
            assert content_digest(old) == content_digest(filtered), "교수별 조각 문항 내용 변경"
            if old == filtered:
                continue
            write(derivative, json.dumps(filtered, ensure_ascii=False, indent=2))
            write(derivative.with_suffix(".md"), J.to_markdown(section(filtered), filtered["stats"]))
        for key in ("professor_changed_2026", "jokbo_weight_hint"):
            entry[key] = repaired["stats"][key]
    if affected:
        index["professor_table_revision"] = hashlib.sha256(json.dumps(edition["profs"], sort_keys=True,
                                                                       ensure_ascii=False).encode()).hexdigest()
        index["professor_table_repair"] = {"evidence": evidence, "lectures": affected}
        write(index_path, json.dumps(index, ensure_ascii=False, indent=2))
    return {"cut": str(cut), "changedFiles": changed, "affectedLectures": affected,
            "authorsUpdated": authored, "sources": evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("materials", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup", type=Path, help="지정하면 백업 후 적용. 생략하면 읽기 전용 대조")
    args = parser.parse_args()
    rows = [repair_cut(p.parent, backup=args.backup) for p in sorted(args.materials.glob("*/*/index.json"))]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cuts": len(rows), "changedFiles": sum(len(r.get("changedFiles", [])) for r in rows),
                      "lectures": sum(len(r.get("affectedLectures", [])) for r in rows),
                      "authorsUpdated": sum(r.get("authorsUpdated", 0) for r in rows),
                      "skipped": [r for r in rows if r.get("skipped")]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
