"""CLI-only, optional choice variations authored before all content checks."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import fitz
import jsonschema

from studyez_llm.pdf import render
from .generate import item_quality_guidance
from .points import STR, _array, _object
from .schema import QUESTION
from .session import SessionError

PROMPT = Path(__file__).parent / "prompts" / "option-pools.md"
PROPOSALS = _object({"summary": STR, "proposals": _array(_object({
    "question_id": STR, "option_pools": QUESTION["properties"]["option_pools"], "reason": STR}))})


def enabled(version: str) -> bool:
    match = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.\d+)?", version)
    return bool(match and int(match[1]) == 1 and int(match[2]) >= 43)


def apply(bank: dict, output: dict) -> dict:
    try:
        jsonschema.validate(output, PROPOSALS)
    except jsonschema.ValidationError as cause:
        raise SessionError(f"CLI 보기 풀 작성 형식 오류: {cause.message}") from cause
    if not output["summary"].strip():
        raise SessionError("CLI 보기 풀 작성·생략의 판단 요약이 필요합니다.")
    result = copy.deepcopy(bank)
    eligible = {q["question_id"]: q for q in result["questions"]
                if q["format"] in ("mcq", "multi_select") and not q["option_pools"]}
    seen = set()
    for row in output["proposals"]:
        qid = row["question_id"]
        if qid not in eligible or qid in seen or not row["reason"].strip() or not row["option_pools"]:
            raise SessionError("CLI 보기 풀은 신규 작성 가능한 문항에 고유 ID와 학습 근거가 필요합니다.")
        seen.add(qid)
        q = eligible[qid]
        if any(p["select_count"] != len(q["options"]) for p in row["option_pools"]):
            raise SessionError("CLI 보기 풀은 기존 문항의 선지 수를 유지해야 합니다.")
        q["option_pools"] = row["option_pools"]
    return result


def write(bank: dict, points: list[dict], pdf: Path, title: str, sources: list[dict], out: Path,
          *, jokbo: Path | None = None, model: str | None = None) -> tuple[dict, dict, dict | None]:
    from .coverage import _call
    eligible = [q for q in bank["questions"] if q["format"] in ("mcq", "multi_select") and not q["option_pools"]]
    if not eligible:
        return bank, {"status": "skipped", "augmentedQuestions": 0, "summary": "추가 작성할 객관식 문항이 없습니다."}, None
    work = out / "option-pools"
    work.mkdir(exist_ok=True)
    with fitz.open(pdf) as doc:
        count = len(doc)
        text = "\n\n".join(f"## PDF p.{i + 1}\n{p.get_text()}" for i, p in enumerate(doc))
    images = render(pdf, f"1-{count}", work / "source-pages")
    for name, data in (("bank.json", {**bank, "questions": eligible}), ("point-plan.json", points),
                       ("context.json", {"title": title, "sources": sources, "page_count": count}),
                       ("source-pages.json", [str(p.resolve()) for p in images])):
        (work / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (work / "source-text.md").write_text(text, encoding="utf-8")
    if jokbo:
        (work / "jokbo.md").write_text(jokbo.read_text(encoding="utf-8"), encoding="utf-8")
    output, info = _call(PROMPT.read_text(encoding="utf-8") + "\n\n" + item_quality_guidance(),
                         PROPOSALS, work, model, "CLI 보기 풀 선택적 작성")
    (out / "option-pools.raw.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    candidate = apply(bank, output)
    return candidate, {"status": "authored" if output["proposals"] else "skipped",
                       "augmentedQuestions": len(output["proposals"]), "summary": output["summary"],
                       "changes": [{"question_id": p["question_id"], "reason": p["reason"]} for p in output["proposals"]]}, info
