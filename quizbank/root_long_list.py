"""Main-Quiz 판의 긴 나열 답을 판정한다(`long-list-judge/1`, docs/changes/2026-11-25-long-list-answers).

답 단위가 많은 나열 문항(`studyez_contracts/roots/long_list.py` `eligible`)마다 근거 쪽 원본 그림을 붙여 Codex에 묻는다.
- grouped: 원본 묶음, 그리고 좁혀 갈 묶음을 받는다.
- ungrouped: 원본 강조가 가리키는 대표와 의학적 갈래를 받는다.

코드가 번호·쪽·덮음을 검사한 줄만 결과에 담는다(`contract.check`).
판·문항·학습 기록·운영 DB는 읽기만 한다. 결과는 고칠 방법의 제안이고, 사람이 확인한 뒤에 채우기 요청으로 넘긴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from studyez_contracts.roots import long_list as contract

from .root_mcq import _call, _stage

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "content/prompts/learning-links/long-list/judge.md"
POLICY = "long-list-judge/1"
BATCH = 6          # 문항 수. 문항마다 근거 쪽 그림이 붙는다.
MAX_IMAGES = 14    # 한 호출에 붙이는 그림 상한. 넘으면 묶음을 더 작게 자른다.
DPI = 110
_STR = {"type": "string"}
_INTS = {"type": "array", "items": {"type": "integer"}}
JUDGMENTS = {"type": "object", "additionalProperties": False, "required": ["judgments"], "properties": {"judgments": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["question_id", "kind", "groups", "keep_group", "representatives",
                                            "representative_basis", "branches", "note", "basis"],
                               "properties": {
                                   "question_id": _STR, "kind": {"type": "string", "enum": list(contract.KINDS)},
                                   "groups": {"type": "array", "items": {
                                       "type": "object", "additionalProperties": False,
                                       "required": ["name", "unit_indices", "page"],
                                       "properties": {"name": _STR, "unit_indices": _INTS, "page": {"type": "integer"}}}},
                                   "keep_group": {"type": "integer"},
                                   "representatives": _INTS, "representative_basis": _STR,
                                   "branches": {"type": "array", "items": {
                                       "type": "object", "additionalProperties": False, "required": ["axis", "unit_indices"],
                                       "properties": {"axis": _STR, "unit_indices": _INTS}}},
                                   "note": _STR, "basis": _STR}}}}}


def sources(generation_dir: Path) -> dict[str, Path]:
    """source_id → 원본 PDF. 생성 기록(packet.json)의 localPath, 없으면 같은 폴더의 source-N.pdf."""
    packet = json.loads((generation_dir / "packet.json").read_text(encoding="utf-8"))
    found = {}
    for n, s in enumerate(packet.get("sources") or []):
        local = Path(s["localPath"]) if s.get("localPath") else None
        found[s["id"]] = local if local and local.exists() else generation_dir / f"source-{n}.pdf"
    return found


def render(pdfs: dict[str, Path], wanted: list[tuple[str, int]]) -> dict[tuple[str, int], bytes]:
    import fitz

    out = {}
    for sid in sorted({s for s, _ in wanted}):
        path = pdfs.get(sid)
        if not path or not path.exists():
            continue
        with fitz.open(path) as doc:
            for s, page in wanted:
                if s == sid and 0 < page <= doc.page_count:
                    out[(s, page)] = doc[page - 1].get_pixmap(dpi=DPI).tobytes("png")
    return out


def batches(targets: list[dict]) -> list[list[dict]]:
    """문항 BATCH개씩, 그림이 MAX_IMAGES를 넘지 않게."""
    out, cur, pages = [], [], set()
    for q in targets:
        mine = set(contract.cited(q))
        if cur and (len(cur) >= BATCH or len(pages | mine) > MAX_IMAGES):
            out.append(cur)
            cur, pages = [], set()
        cur.append(q)
        pages |= mine
    if cur:
        out.append(cur)
    return out


def batch_input(batch: list[dict], images: dict[tuple[str, int], bytes]) -> tuple[dict, dict[str, bytes]]:
    files, rows = {}, []
    for q in batch:
        pages = []
        for sid, page in contract.cited(q):
            body = images.get((sid, page))
            name = f"pages/{sid}-p{page}-{hashlib.sha256(body).hexdigest()[:8]}.png" if body else ""
            if body:
                files[name] = body
            pages.append({"source_id": sid, "page": page, "image": name})
        rows.append({"question_id": q["question_id"], "question": q.get("question", ""),
                     "units": [{"index": i, "text": u} for i, u in enumerate(contract.units(q))], "pages": pages})
    return {"questions": rows}, files


def apply(batch: list[dict], output: dict) -> tuple[dict, dict]:
    by_id = {q["question_id"]: q for q in batch}
    rows, dropped = {}, {}
    for got in output.get("judgments") or []:
        qid = got.get("question_id")
        if qid not in by_id or qid in rows or qid in dropped:
            continue
        try:
            rows[qid] = contract.check(by_id[qid], got)
        except ValueError as cause:
            dropped[qid] = str(cause)
    for qid in by_id:
        if qid not in rows and qid not in dropped:
            dropped[qid] = "판정 없음"
    return rows, dropped


def build(document: dict, out: Path, *, generation_dir: Path, model: str | None = None, call=_call) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    targets = [q for q in document["bank_snapshot"]["questions"] if contract.eligible(q)]
    images = render(sources(generation_dir), sorted({p for q in targets for p in contract.cited(q)}))
    prompt = PROMPT.read_text(encoding="utf-8")
    rows, dropped, usage, failed = {}, {}, [], 0
    for n, batch in enumerate(batches(targets)):
        data, files = batch_input(batch, images)
        output, error = _stage(out / f"judge-{n}", "judge", prompt, JUDGMENTS, data, model, "긴 나열 판정", call, usage,
                               images=files)
        if output is None:
            failed += 1
            dropped.update({q["question_id"]: f"판정 호출 실패: {error}" for q in batch})
            continue
        got, bad = apply(batch, output)
        rows.update(got)
        dropped.update(bad)
    by_id = {q["question_id"]: q for q in targets}
    previews = {qid: contract.answer_preview(by_id[qid], r) for qid, r in rows.items() if r["kind"] == "ungrouped" and r["fixable"]}
    kinds = [r["kind"] for r in rows.values()]
    result = {"schema": contract.SCHEMA, "revision": document["revision"], "title": document.get("title"),
              "createdAt": datetime.now(UTC).isoformat(), "policy": POLICY,
              "counts": {"eligible": len(targets), "grouped": kinds.count("grouped"),
                         "ungrouped": sum(1 for r in rows.values() if r["kind"] == "ungrouped" and r["fixable"]),
                         "unfixable": sum(1 for r in rows.values() if not r["fixable"]),
                         "dropped": len(dropped), "failedBatches": failed},
              "judgments": rows, "previews": previews, "dropped": dropped}
    (out / "long-list.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "usage.jsonl").open("a", encoding="utf-8") as log:
        for entry in usage:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return result


def summary(result: dict) -> str:
    c = result["counts"]
    return (f"긴 나열 대상 {c['eligible']}문항 · 원본 묶음 {c['grouped']} · 대표/갈래 {c['ungrouped']} · "
            f"고칠 방법 없음 {c['unfixable']} · 버림 {c['dropped']} · 실패 묶음 {c['failedBatches']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--document", type=Path, required=True, help="root_content 문서 JSON")
    ap.add_argument("--generation-dir", type=Path, help="원본 PDF가 있는 생성 폴더(기본: runs/_root-generation/<revision의 gid>)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model")
    args = ap.parse_args(argv)
    document = json.loads(args.document.read_text(encoding="utf-8"))
    gen = args.generation_dir or ROOT / "runs" / "_root-generation" / document["revision"].removeprefix("auto-")
    result = build(document, args.out, generation_dir=gen, model=args.model)
    print(summary(result), flush=True)
    return 1 if result["counts"]["failedBatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
