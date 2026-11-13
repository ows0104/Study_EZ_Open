"""강의별 족보 풀이 자료(jokbo-solve/1)를 만든다.

입력은 amgi에서 이미 정리한 족보 세트다(`data/pastexam/pes_*.json` — 원문·정답표·
교수 구획·반복 연도·그림). 여기서 하는 일은 세 가지뿐이다.

1. 세트를 StudyEZ 강의(시간표 칸 id, 올해 필기의 run_id)에 붙인다.
2. 구획을 StudyEZ의 올해 교수로 다시 판정해 「같은 교수 → 다른 교수 → 미상」으로 세운다.
3. 해설을 얹는다. 해설은 `explain/<setId>.json`에 따로 두고 읽을 때만 합친다 —
   세트를 다시 만들어도 해설이 날아가지 않게 하려는 것이다(amgi와 같은 이유).

문항 원문·선지 순서·정답은 바꾸지 않는다. 족보 원문은 제3자 저작물이라 산출물은
git 밖(`runs/_materials/<과목>/jokbo-solve/`)에만 쓴다.

사용:
    python -m runner.jokbo_solve build
    python -m runner.jokbo_solve status        # 해설이 빠진 문항 수
    python -m runner.jokbo_solve pack <setId>  # 해설 작성용 입력 한 세트
    python -m runner.jokbo_solve check <setId> # 그 세트의 해설·소속만 검사
    python -m runner.jokbo_solve upload [--audience admin|all] [--only 18 "CBL 1"]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any

from studyez_contracts.jokbo import (
    SCHEMA,
    JokboSolveError,
    answer_status,
    validate_explain,
    validate_lecture,
)

REPO = Path(__file__).resolve().parents[1]
SUBJECT = "감염과 면역"
EDITION = "2026-1"
BLOCK = "감염과 면역 1차"
AMGI = Path.home() / "amgi"
TIMETABLE = REPO / "data" / "timetable" / "2026_본1_2학기_시간표.json"
NOTES = Path.home() / "SynologyDrive" / SUBJECT / "필기" / "2026"


def default_root() -> Path:
    # worktree 안에서 돌려도 산출물은 원래 저장소의 runs/에 쌓는다 — worktree는 지워진다.
    repo = REPO
    for parent in REPO.parents:
        if parent.name == "worktrees" and parent.parent.name == ".claude":
            repo = parent.parent.parent
            break
    return repo / "runs" / "_materials" / SUBJECT / "jokbo-solve"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


# ─────────────────────────────────────────────── 강의 붙이기

_EVENT = re.compile(r"^감염과 면역 (\d+|CBL \d+|TBL \d+|실습 \d+)$")
_RUN_ID = re.compile(r"^\[(\d{6})_(\d{1,2})\]")
# 강의 번호가 없는 세트(족보의 CBL·TBL·실습 단원). (붙일 시간표 칸, 세트 제목에 있어야 할 글자).
# 0g는 족보 제목이 「TBL2」지만 42문항 전부 위장관·피부연조직·요로감염·폐렴이다 — 올해 그 주제는
# 「TBL 1」(11/3)이고 「TBL 2」는 심내막염·중추신경계감염이다. 제목이 아닌 내용으로 붙인다(2026-11-13 해설 작성 중 확인).
_SPECIAL = {"0a": ("CBL 1", "CBL 1"), "0b": ("CBL 2", "CBL 2"), "0c": ("CBL 3", "CBL 3"),
            "0e": ("실습 1", "실습"), "0g": ("TBL 1", "TBL2")}


def timetable_events(path: Path) -> dict[str, dict]:
    out = {}
    for e in read_json(path):
        m = _EVENT.match(e.get("title", ""))
        if m:
            out[m.group(1)] = e
    return out


def topic_of(event: dict) -> str:
    lines = [ln.strip() for ln in event.get("details", "").splitlines() if ln.strip()]
    prof = event.get("professor", "").strip()
    if lines and prof and lines[-1] == prof:
        lines = lines[:-1]
    return " ".join(lines)


def run_id_of(pdf: str | None) -> str | None:
    m = _RUN_ID.match(pdf or "")
    return f"{m.group(1)}_{int(m.group(2)):02d}" if m else None


def event_run_id(ev: dict) -> str:
    """시간표 칸의 run_id. 교시는 시작 시각 − 8이다(09:00 → 01, 13:00 → 05) — 필기 파일명과 같은 규칙."""
    y, m, d = ev["date"].split("-")
    return f"{y[2:]}{m}{d}_{int(ev['startTime'][:2]) - 8:02d}"


_NOTE = re.compile(r"^\[(\d{6})_(\d{1,2})\][^(]*\(([^)]*)\)")


def note_professors(notes_dir: Path | None) -> dict[str, list[str]]:
    """올해 필기 파일명에서 run_id → 교수. 파일명이 정본이다(족보 정책: 실제 올해 필기 파일명 우선)."""
    out: dict[str, list[str]] = {}
    if not notes_dir or not notes_dir.is_dir():
        return out
    for f in sorted(notes_dir.iterdir()):
        m = _NOTE.match(unicodedata.normalize("NFC", f.name))
        if m:
            profs = [p.strip() for p in re.split(r"[,，]", m.group(3)) if p.strip()]
            out.setdefault(f"{m.group(1)}_{int(m.group(2)):02d}", profs)
    return out


def lecture_info(key: str, events: dict[str, dict], notes: dict[str, list[str]],
                 lecture_map: dict[str, dict]) -> dict:
    ev = events[key]
    run_id = event_run_id(ev)
    lm = lecture_map.get(f"L{int(key):02d}") if key.isdigit() else None
    if lm and run_id_of(lm.get("pdf")) not in (None, run_id):
        raise ValueError(f"run_id 불일치 {key}: 시간표 {run_id} / amgi {lm.get('pdf')}")
    if not key.isdigit():
        # CBL·TBL·실습은 분반마다 교수가 달라 「올해 교수」가 하나로 서지 않는다.
        profs, source = [], "none"
    elif run_id in notes:
        profs, source = notes[run_id], "notes"
    elif lm and run_id_of(lm.get("pdf")) and lm.get("professor"):
        profs, source = [p.strip() for p in lm["professor"].split(",") if p.strip()], "notes"
    elif ev.get("professor", "").strip():
        profs, source = [p.strip() for p in re.split(r"[,\s]+", ev["professor"]) if p.strip()], "timetable"
    else:
        profs, source = [], "none"
    return {
        "eventId": ev["id"], "runId": run_id, "number": key, "title": topic_of(ev),
        "date": ev["date"], "currentProfessors": profs, "professorSource": source,
    }


def set_targets(s: dict, events: dict[str, dict]) -> list[str]:
    if s["lectures"]:
        return [str(n) for n in s["lectures"] if str(n) in events]
    special = _SPECIAL.get(s["ref"])
    if special and special[1] in (s.get("title") or "") and special[0] in events:
        return [special[0]]
    return []


# ─────────────────────────────────────────────── 문항

def figures_index(fig_dir: Path) -> dict[str, list[dict]]:
    path = fig_dir / "index.json"
    return read_json(path) if path.exists() else {}


def load_explain(dirs: list[tuple[Path, str]], set_id: str) -> dict[str, dict]:
    """앞의 폴더가 이긴다. StudyEZ 해설이 있으면 amgi 해설은 쓰지 않는다."""
    merged: dict[str, dict] = {}
    for d, source in reversed(dirs):
        path = d / f"{set_id}.json"
        if not path.exists():
            continue
        for item_id, x in read_json(path).items():
            if item_id.startswith("_"):
                continue
            merged[item_id] = {**x, "source": source}
    return merged


def load_assign(assign_dir: Path, s: dict, problems: list[str]) -> dict[str, list[str]]:
    """여러 강의를 묶은 세트(7-8, 25-28)의 문항별 소속. 없거나 틀린 문항은 묶음 전체에 남긴다."""
    path = assign_dir / f"{s['id']}.json"
    if len(s["lectures"]) < 2 or not path.exists():
        return {}
    allowed = {str(n) for n in s["lectures"]}
    out = {}
    for item_id, v in read_json(path).items():
        keys = [str(x) for x in (v if isinstance(v, list) else [v])]
        if keys and set(keys) <= allowed:
            out[item_id] = keys
        else:
            problems.append(f"소속 무시 {item_id}: {v}")
    return out


FIX_KEYS = {"note", "evidence", "stemReplace", "choices", "answers", "answerMode", "allCorrect", "figures", "moveTo"}


def load_fixes(fix_dir: Path, set_id: str, problems: list[str]) -> dict[str, dict]:
    """원천의 오류 교정. 문항마다 무엇을(`note`) 무엇을 근거로(`evidence`, 원본 PDF 쪽) 고쳤는지 적는다.

    amgi 원천 파일은 고치지 않는다 — 원천을 다시 만들어도 교정이 남도록 따로 두고 읽을 때 얹는다.
    """
    path = fix_dir / f"{set_id}.json"
    if not path.exists():
        return {}
    out = {}
    for item_id, f in read_json(path).items():
        if item_id.startswith("_"):
            continue
        bad = set(f) - FIX_KEYS
        if bad or not f.get("note") or not f.get("evidence"):
            problems.append(f"교정 무시 {item_id}: note·evidence 필수, 모르는 키 {sorted(bad)}")
            continue
        out[item_id] = f
    return out


def figure_entry(name: str, figs_by_name: dict[str, dict], fix_fig_dir: Path) -> dict | None:
    if name in figs_by_name:
        return figs_by_name[name]
    path = fix_fig_dir / name
    if not path.exists():
        return None
    try:
        import fitz  # PyMuPDF — 저장소가 이미 쓴다
        pix = fitz.Pixmap(str(path))
        return {"file": name, "w": pix.width, "h": pix.height}
    except Exception:
        return {"file": name}


def from_amgi_explain(x: dict) -> dict:
    """amgi 해설(explanation·choiceNotes·caution)을 jokbo-explain/1 꼴로."""
    if "text" in x:
        return x
    return {"text": x.get("explanation", ""), "choiceNotes": x.get("choiceNotes"),
            "caution": x.get("caution"), "basis": {"kind": "notes"},
            "answerCheck": "agree", "source": x.get("source", "amgi")}


def apply_fix(e: dict, fix: dict | None, figs: dict, figs_by_name: dict, fix_fig_dir: Path,
              problems: list[str]) -> tuple[dict, list[dict], dict]:
    """교정을 얹은 원천 문항, 그림, 교정 기록."""
    figures = list(figs.get(e["pastExamItemId"], []))
    if not fix:
        return e, figures, {}
    e = dict(e)
    record: dict[str, Any] = {"correctionNote": fix["note"], "correctionEvidence": fix["evidence"]}
    for a, b in fix.get("stemReplace", []):
        if a not in e["stem"] and a not in (e.get("sharedPrompt") or ""):
            problems.append(f"교정 글자 없음 {e['pastExamItemId']}: «{a}»")
        e["stem"] = e["stem"].replace(a, b)
        if e.get("sharedPrompt"):
            e["sharedPrompt"] = e["sharedPrompt"].replace(a, b)
    if "choices" in fix:
        e["choices"] = list(fix["choices"])
        e.pop("choiceStyles", None)
    if "answers" in fix or "allCorrect" in fix:
        old = list(e.get("answers") or ([] if e.get("answer") is None else [e["answer"]]))
        if "answers" in fix:
            e["answers"] = list(fix["answers"])
            e["answer"] = fix["answers"][0] if fix["answers"] else None
            e.pop("answerText", None)
        if "answerMode" in fix:
            e["answerMode"] = fix["answerMode"]
        if "allCorrect" in fix:
            e["allCorrect"] = bool(fix["allCorrect"])
        if old != e.get("answers"):
            record["originalAnswers"] = old
    if "figures" in fix:
        figures = []
        for name in fix["figures"]:
            entry = figure_entry(name, figs_by_name, fix_fig_dir)
            if entry is None:
                problems.append(f"교정 그림 없음 {e['pastExamItemId']}: {name}")
            else:
                figures.append(entry)
    return e, figures, record


def convert_item(e: dict, set_id: str, figs: dict, explain: dict, problems: list[str],
                 fix: dict | None = None, figs_by_name: dict | None = None, fix_fig_dir: Path | None = None) -> dict:
    e, figures, record = apply_fix(e, fix, figs, figs_by_name or {}, fix_fig_dir or Path("."), problems)
    answers = list(e.get("answers") or ([] if e.get("answer") is None else [e["answer"]]))
    all_correct = bool(e.get("allCorrect")) or (e.get("answerText") or "").replace(" ", "") in ("전원정답", "모두정답")
    if all_correct:
        answers = []
    choices = list(e.get("choices") or [])
    # 답안지 답이 선지 밖이면(0e 037: 선지 4개에 답 5) 답이 없는 것으로 둔다. 원문 답은 answerNote에 남긴다.
    note = e.get("answerNote")
    if any(not 1 <= a <= len(choices) for a in answers) or (not answers and not all_correct and e.get("answerText")):
        raw = ",".join(map(str, answers)) or e.get("answerText")
        note = " ".join(x for x in [note, f"답안지 답 «{raw}»이 선지 범위 밖이라 채점하지 않는다."] if x)
        problems.append(f"{e['pastExamItemId']}: 답안지 답 {raw} / 선지 {len(choices)}개")
        answers = []
    mode = e.get("answerMode") or "one_of"
    item = {
        "id": e["pastExamItemId"],
        "setId": set_id,
        "year": e["year"],
        "yearLabel": e.get("yearLabel") or str(e["year"]),
        "number": e["number"],
        "sharedPrompt": e.get("sharedPrompt"),
        "stem": e["stem"],
        "choices": choices,
        "choiceStyles": e.get("choiceStyles"),
        "answers": answers,
        "answerMode": mode,
        "selectCount": e.get("selectCount") or (len(answers) if mode == "all_of" else 1),
        "answerStatus": answer_status(answers, mode, all_correct),
        "allCorrect": all_correct,
        "answerNote": note,
        "verification": "corrected" if record else e.get("verification", "pending"),
        "correctionNote": " ".join(x for x in [e.get("correctionNote"), record.get("correctionNote")] if x) or None,
        "correctionEvidence": record.get("correctionEvidence"),
        "originalAnswers": record.get("originalAnswers"),
        "repeatYears": e.get("repeatYears"),
        "figures": figures,
        "explanation": None,
    }
    x = explain.get(item["id"])
    if x:
        x = from_amgi_explain(x)
        x = {k: v for k, v in x.items() if v is not None}
        if item["answerStatus"] == "missing":
            x["answerCheck"] = "no-key"
        else:
            x.pop("proposedAnswers", None)
        try:
            validate_explain(x, len(choices), item["id"])
            item["explanation"] = x
        except JokboSolveError as err:
            problems.append(f"해설 무시 {err}")
    return {k: v for k, v in item.items() if v is not None or k == "explanation"}


# ─────────────────────────────────────────────── 구획

def section_kind(professors: list[str], current: list[str]) -> str:
    if not professors or not current:
        return "unknown"
    return "same" if set(professors) & set(current) else "other"


def item_professors(s: dict, item_id: str) -> list[str]:
    """원천 세트 안에서 그 문항이 속한 교수 구획의 교수."""
    groups = s.get("groups") or [{"professors": s.get("professors") or [], "from": 0, "count": len(s["items"])}]
    for g in groups:
        if any(e["pastExamItemId"] == item_id for e in s["items"][g["from"]:g["from"] + g["count"]]):
            return list(g.get("professors") or [])
    return []


def year_professors(sets: list[dict], year: str) -> list[str] | None:
    """옮겨 온 문항의 출제 교수 — 옮겨 간 강의의 세트에서 같은 해 구획의 교수. 모르면 None."""
    for s in sets:
        for g in s.get("groups") or []:
            if year in (g.get("years") or []):
                return list(g.get("professors") or [])
    return None


def build_sections(entries: list[tuple[dict, list[str]]], current: list[str]) -> list[dict]:
    """entries = [(문항, 그 해 출제 교수)]. 올해 교수로 다시 판정해 같은 교수 → 다른 교수 → 미상."""
    by_key: dict[tuple, dict] = {}
    pos = {it["id"]: i for i, (it, _) in enumerate(entries)}
    year_of = {it["id"]: it["yearLabel"] for it, _ in entries}
    for it, profs in entries:
        key = (section_kind(profs, current), tuple(profs))
        sec = by_key.setdefault(key, {"kind": key[0], "professors": list(profs), "years": [], "itemIds": [],
                                      "setIds": []})
        sec["itemIds"].append(it["id"])
        if it["yearLabel"] not in sec["years"]:
            sec["years"].append(it["yearLabel"])
        if it["setId"] not in sec["setIds"]:
            sec["setIds"].append(it["setId"])
    order = {"same": 0, "other": 1, "unknown": 2}
    for sec in by_key.values():
        sec["years"].sort(reverse=True)
        sec["setIds"].sort()
        # 구획 안에서도 최신 연도부터. 같은 해는 원천 순서를 유지한다.
        rank = {y: i for i, y in enumerate(sec["years"])}
        sec["itemIds"].sort(key=lambda i: (rank[year_of[i]], pos[i]))
    return sorted(by_key.values(), key=lambda x: (order[x["kind"]], [-int(y[:4]) for y in x["years"][:1]]))


# ─────────────────────────────────────────────── 빌드

def build(amgi: Path, root: Path, timetable: Path, notes_dir: Path | None = None) -> dict:
    src = amgi / "data" / "pastexam"
    fig_src = amgi / "webapp" / "public" / "pastexam-figures"
    events = timetable_events(timetable)
    notes = note_professors(notes_dir)
    lecture_map = {l["id"]: l for l in read_json(amgi / "data" / "lecture-map.json")["lectures"]}
    figs = figures_index(fig_src)
    explain_dirs = [(root / "explain", "studyez"), (src / "explain", "amgi")]
    out = root / EDITION
    problems: list[str] = []

    sets = [read_json(src / m["file"]) if (src / m["file"]).exists() else read_json(src / Path(m["file"]).name)
            for m in read_json(src / "index.json")["sets"]]
    figs_by_name = {f["file"]: f for fl in figs.values() for f in fl}
    fix_fig_dir = root / "fixes" / "figures"
    targets_of = {s["id"]: set_targets(s, events) for s in sets}
    sets_of_lecture: dict[str, list[dict]] = {}
    for s in sets:
        for key in targets_of[s["id"]]:
            sets_of_lecture.setdefault(key, []).append(s)

    per_lecture: dict[str, list[tuple[dict, list[str]]]] = {}
    unattached = []
    for s in sets:
        explain = load_explain(explain_dirs, s["id"])
        fixes = load_fixes(root / "fixes", s["id"], problems)
        targets = targets_of[s["id"]]
        assign = load_assign(root / "assign", s, problems)
        placed = 0
        for e in s["items"]:
            fix = fixes.get(e["pastExamItemId"])
            it = convert_item(e, s["id"], figs, explain, problems, fix, figs_by_name, fix_fig_dir)
            if fix and fix.get("moveTo"):
                dest = [str(k) for k in fix["moveTo"]]
                if any(k not in events for k in dest):
                    problems.append(f"교정 이동 대상 없음 {it['id']}: {dest}")
                    dest = [k for k in dest if k in events]
                it["movedFrom"] = s["id"]
                for key in dest:
                    profs = year_professors(sets_of_lecture.get(key, []), it["yearLabel"])
                    per_lecture.setdefault(key, []).append((it, profs or []))
                    placed += 1
                continue
            for key in targets:
                if key in assign.get(it["id"], targets):
                    per_lecture.setdefault(key, []).append((it, item_professors(s, it["id"])))
                    placed += 1
        if not placed:
            unattached.append({"setId": s["id"], "title": s.get("title"), "items": len(s["items"])})

    if out.exists():
        shutil.rmtree(out)
    (out / "lectures").mkdir(parents=True)
    used_figs: set[str] = set()
    index = []
    for key, entries in sorted(per_lecture.items(), key=lambda kv: (not kv[0].isdigit(), int(kv[0]) if kv[0].isdigit() else 0, kv[0])):
        lec = lecture_info(key, events, notes, lecture_map)
        sections = build_sections(entries, lec["currentProfessors"])
        items_by_id = {it["id"]: it for it, _ in entries}
        ordered = [items_by_id[i] for sec in sections for i in sec["itemIds"]]
        used = {it["setId"] for it in ordered}
        src_sets = [s for s in sets if s["id"] in used]
        shared = [s["id"] for s in src_sets if len(s["lectures"]) > 1]
        doc = {
            "schema": SCHEMA, "subject": SUBJECT, "block": BLOCK, "edition": EDITION,
            "lecture": lec,
            "sources": [{"setId": s["id"], "ref": s["ref"], "title": s.get("title"),
                         "lectures": [str(n) for n in s["lectures"]]} for s in src_sets],
            "sharedSets": shared,
            "sections": sections,
            "items": ordered,
        }
        validate_lecture(doc)
        write_json(out / "lectures" / f"{lec['eventId']}.json", doc)
        for it in ordered:
            used_figs.update(f["file"] for f in it.get("figures", []))
        count = {k: sum(len(s["itemIds"]) for s in sections if s["kind"] == k) for k in ("same", "other", "unknown")}
        index.append({
            **lec,
            "file": f"lectures/{lec['eventId']}.json",
            "items": len(ordered), **{f"{k}Items": v for k, v in count.items()},
            "explained": sum(1 for it in ordered if it["explanation"]),
            "missingAnswers": sum(1 for it in ordered if it["answerStatus"] == "missing"),
            "doubts": sum(1 for it in ordered if (it["explanation"] or {}).get("answerCheck") == "doubt"),
            "figures": sum(len(it.get("figures", [])) for it in ordered),
            "sharedSets": shared,
        })

    (out / "figures").mkdir()
    for name in sorted(used_figs):
        shutil.copy2(fig_src / name if (fig_src / name).exists() else fix_fig_dir / name, out / "figures" / name)

    items_total = sum(len(s["items"]) for s in sets)
    summary = {
        "schema": "jokbo-solve-index/1", "subject": SUBJECT, "block": BLOCK, "edition": EDITION,
        "source": {"amgi": str(src), "timetable": timetable.name},
        "lectures": index,
        "unattachedSets": unattached,
        "totals": {
            "sets": len(sets), "items": items_total,
            "explained": len({it["id"] for es in per_lecture.values() for it, _ in es if it["explanation"]}),
            "corrected": len({it["id"] for es in per_lecture.values() for it, _ in es if it["verification"] == "corrected"}),
            "figures": len(used_figs),
        },
        "problems": sorted(set(problems)),
    }
    write_json(out / "index.json", summary)
    return summary


def status(amgi: Path, root: Path) -> dict:
    src = amgi / "data" / "pastexam"
    rows = []
    for m in read_json(src / "index.json")["sets"]:
        s = read_json(src / Path(m["file"]).name)
        explain = load_explain([(root / "explain", "studyez"), (src / "explain", "amgi")], s["id"])
        missing = [e["pastExamItemId"] for e in s["items"] if e["pastExamItemId"] not in explain]
        rows.append({"setId": s["id"], "items": len(s["items"]), "missing": len(missing)})
    return {"sets": rows, "missing": sum(r["missing"] for r in rows),
            "items": sum(r["items"] for r in rows)}


def _fixed_items(amgi: Path, root: Path, set_id: str, problems: list[str], with_explain: bool) -> tuple[dict, list[dict], dict]:
    src = amgi / "data" / "pastexam"
    s = read_json(src / f"{set_id}.json")
    figs = figures_index(amgi / "webapp" / "public" / "pastexam-figures")
    figs_by_name = {f["file"]: f for fl in figs.values() for f in fl}
    fixes = load_fixes(root / "fixes", set_id, problems)
    explain = load_explain([(root / "explain", "studyez")], set_id) if with_explain else {}
    items = [convert_item(e, set_id, figs, explain, problems, fixes.get(e["pastExamItemId"]), figs_by_name,
                          root / "fixes" / "figures") for e in s["items"]]
    return s, items, fixes


def check(amgi: Path, root: Path, set_id: str) -> dict:
    """한 세트의 해설·소속·교정만 검사한다. 빌드 폴더를 건드리지 않아 여러 작성자가 동시에 돌려도 된다."""
    problems: list[str] = []
    s, items, fixes = _fixed_items(amgi, root, set_id, problems, True)
    explain = load_explain([(root / "explain", "studyez")], set_id)
    assign = load_assign(root / "assign", s, problems)
    missing = [it["id"] for it in items if not it["explanation"]]
    unknown = sorted((set(explain) | set(fixes)) - {it["id"] for it in items})
    unassigned = [it["id"] for it in items if len(s["lectures"]) > 1 and it["id"] not in assign
                  and not (fixes.get(it["id"]) or {}).get("moveTo")]
    return {"setId": set_id, "items": len(items), "missingExplain": missing, "unknownIds": unknown,
            "unassigned": unassigned, "fixed": sorted(fixes), "problems": problems,
            "doubts": [it["id"] for it in items if (it["explanation"] or {}).get("answerCheck") == "doubt"]}


def pack(amgi: Path, root: Path, set_id: str) -> dict:
    """해설 작성자에게 줄 한 세트: 교정을 얹은 문항·그림 경로·강의 필기 경로·이미 쓴 해설."""
    problems: list[str] = []
    s, items, _ = _fixed_items(amgi, root, set_id, problems, False)
    explain = load_explain([(root / "explain", "studyez")], set_id)
    lecture_map = {l["id"]: l for l in read_json(amgi / "data" / "lecture-map.json")["lectures"]}
    notes = []
    for n in s["lectures"]:
        lm = lecture_map.get(f"L{n:02d}") or {}
        bundle = lm.get("bundle") or lm.get("prevBundle")
        if bundle and (amgi / bundle).exists():
            notes.append(str(amgi / bundle))
    fig_dirs = [amgi / "webapp" / "public" / "pastexam-figures", root / "fixes" / "figures"]

    def fig_path(name: str) -> str:
        for d in fig_dirs:
            if (d / name).exists():
                return str(d / name)
        return name

    keep = ("id", "year", "number", "sharedPrompt", "stem", "choices", "answers", "answerMode", "answerStatus",
            "answerNote", "repeatYears", "correctionNote", "originalAnswers")
    return {
        "setId": s["id"], "title": s.get("title"), "lectures": s["lectures"], "notes": notes,
        "items": [{**{k: it.get(k) for k in keep},
                   "figures": [fig_path(f["file"]) for f in it.get("figures", [])],
                   "existingExplanation": explain.get(it["id"])} for it in items],
        "problems": problems,
    }


def upload(root: Path, base: str, token: str, audience: str, only: list[str] | None = None) -> dict:
    """빌드 산출물을 서버에 올린다. 그림 먼저(크기가 같으면 건너뜀), 그다음 강의 문서.

    서버가 jokbo-solve/1 계약과 그림 존재를 다시 검사한다. `audience=admin`이면 관리자에게만 보인다.
    """
    import urllib.parse
    import urllib.request

    from runner.transport import Client

    out = root / EDITION
    index = read_json(out / "index.json")
    client = Client(base, token)
    lectures = [l for l in index["lectures"] if not only or l["eventId"] in only or l["number"] in only]
    names = sorted({f["file"] for l in lectures for it in read_json(out / l["file"])["items"]
                    for f in it.get("figures", [])})
    sent = skipped = 0
    for name in names:
        path = out / "figures" / name
        q = urllib.parse.quote(name)
        if client.call("GET", f"/api/admin/jokbo/figures/{q}").get("size") == path.stat().st_size:
            skipped += 1
            continue
        req = urllib.request.Request(f"{client.base}/api/admin/jokbo/figures/{q}", data=path.read_bytes(), method="PUT",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"})
        client._open(req)
        sent += 1
    done = []
    for l in lectures:
        doc = read_json(out / l["file"])
        r = client.call("PUT", f"/api/admin/jokbo/events/{urllib.parse.quote(l['eventId'])}?audience={audience}", doc)
        done.append({"number": l["number"], "items": r["items"], "audience": r["audience"]})
    return {"figuresSent": sent, "figuresSkipped": skipped, "lectures": done}


def runner_token(cli: str | None) -> str:
    import os
    token = (cli or os.getenv("STUDYEZ_RUNNER_TOKEN", "")).strip()
    env = REPO / "server" / ".env"
    if not token and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("RUNNER_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"')
    return token


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m runner.jokbo_solve")
    p.add_argument("command", choices=["build", "status", "pack", "check", "upload"])
    p.add_argument("set_id", nargs="?")
    p.add_argument("--amgi", type=Path, default=AMGI)
    p.add_argument("--root", type=Path, default=None)
    p.add_argument("--timetable", type=Path, default=TIMETABLE)
    p.add_argument("--notes", type=Path, default=NOTES, help="올해 필기 폴더(파일명으로 교수 확인)")
    p.add_argument("--api", default=None, help="API 주소(기본: STUDYEZ_API_BASE_URL 또는 운영)")
    p.add_argument("--token", default=None)
    p.add_argument("--audience", choices=["admin", "all"], default="admin",
                   help="admin: 관리자에게만(기본) · all: 학생에게도")
    p.add_argument("--only", nargs="*", help="올릴 강의 번호(18, 'CBL 1') 또는 eventId")
    a = p.parse_args(argv)
    root = a.root or default_root()
    if a.command == "build":
        r = build(a.amgi, root, a.timetable, a.notes)
        print(json.dumps({"out": str(root / EDITION), "totals": r["totals"], "lectures": len(r["lectures"]),
                          "unattached": r["unattachedSets"], "problems": r["problems"]}, ensure_ascii=False, indent=1))
    elif a.command == "upload":
        import os
        from runner.transport import DEFAULT_API_BASE
        token = runner_token(a.token)
        if not token:
            p.error("러너 토큰이 없다: --token, STUDYEZ_RUNNER_TOKEN, 또는 server/.env의 RUNNER_TOKEN")
        base = (a.api or os.getenv("STUDYEZ_API_BASE_URL") or DEFAULT_API_BASE).rstrip("/")
        print(json.dumps(upload(root, base, token, a.audience, a.only), ensure_ascii=False, indent=1))
    elif a.command == "status":
        print(json.dumps(status(a.amgi, root), ensure_ascii=False, indent=1))
    else:
        if not a.set_id:
            p.error(f"{a.command} 에는 setId가 필요하다")
        fn = pack(a.amgi, root, a.set_id) if a.command == "pack" else check(a.amgi, root, a.set_id)
        print(json.dumps(fn, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
