"""ChatGPT 의 표·블록 응답 → 스키마에 맞는 문제은행 JSON.

정리는 모델이 한다(2026-10-03 관리자: 「정리는 LLM이 하긴 해야 할 것 같아」). 이 단계는
문항과 전체 제목을 옮기고 고치지 않는다 — 고칠 만한 것은 warnings 로, 의학적 정오는 review.py 로.
graph_title만 원래 제목을 근거로 짧게 요약할 수 있다. 그래프 표시용이며 학습 내용은 그대로다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import session
from .schema import BANK, SCHEMA_VERSION, without_retired

PROMPT = Path(__file__).parent / "prompts" / "organize.md"
SYSTEM = "You convert a supplied study-bank response into the requested JSON. Follow the user message exactly."
COMPLETE_MARK = "STUDYEZ_BANK_COMPLETE"

# ChatGPT 가 첨부 파일을 인용할 때 본문에 심는 표식 — runner/preview.py 와 같은 것.
#     U+E200 filecite U+E202 turn0file0 U+E202 L6-L13 U+E201
# 그대로 두면 정리기가 이것을 출처로 읽는다.
_CITATION_RE = re.compile(".*?", re.S)
_PUA_RE = re.compile("[-]")


def clean_response(raw: str) -> str:
    """인용 표식·사용자 영역 문자·끝의 완료 표시를 걷는다."""
    text = _CITATION_RE.sub("", raw)
    text = _PUA_RE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text).strip()
    text = re.sub(r"\**\s*" + COMPLETE_MARK + r"\s*\**\s*$", "", text).rstrip()
    return text


def expected_schema(raw: str, lecture: dict) -> str:
    """Keep old banks old and bind new authoring checks to prompt metadata."""
    version = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.\d+)?", lecture.get("prompt_version", ""))
    if version and tuple(map(int, version.groups())) >= (1, 26):
        return SCHEMA_VERSION
    if re.search(r"^#{1,6}\s+(?:[0-9.]+\s+)?Option Pools\s*$", raw, re.M | re.I):
        return SCHEMA_VERSION
    return "3.0"


def organizer_prompt(raw: str, lecture: dict) -> str:
    from .question_first import enabled
    meta = {"title": lecture["title"], "sources": lecture["sources"], "prompt_version": lecture.get("prompt_version", "")}
    fill = {"schema_version": expected_schema(raw, lecture),
            "lecture": json.dumps(meta, ensure_ascii=False),
            "raw": json.dumps(clean_response(raw), ensure_ascii=False)}
    template = PROMPT.read_text(encoding="utf-8")
    if enabled(lecture.get("prompt_version", "")) or lecture.get("defer_learning_structure"):
        template = template.replace("\nLECTURE_METADATA_DATA\n", "\n문항 우선 출력 계약\n"
            "이 버전은 웹에 포인트·개념도·회상 계획·선행 관계가 없는 것이 정상이다. "
            "누락 경고를 만들거나 이를 추정·작성하지 않는다. concepts와 retrieval_plan은 빈 배열, "
            "각 문항의 concept_id는 빈 문자열, prerequisites는 빈 배열로 저장한다. "
            "문항별 블록 또는 기존 Questions의 13열과 모든 상세 표를 question_id로 연결해 보존한다. "
            "사후 학습 구조는 내용 검수 뒤 별도 CLI가 작성한다.\n\nLECTURE_METADATA_DATA\n")
    return re.sub(r"\{\{(schema_version|lecture|raw)\}\}", lambda m: fill[m.group(1)], template)


# `L1:M1` · `A: cAMP 감소` · `R2) PLC` — ChatGPT 가 짝짓기·순서 항목에 붙이는 라벨.
_LABEL_RE = re.compile(r"^\s*([A-Z]\d{0,2}|\d{1,2})\s*[:.)]\s*(.+?)\s*$")


def _unlabel(items: list[str]) -> dict[str, str] | None:
    """항목마다 라벨이 붙어 있으면 {라벨: 본문}. 하나라도 없거나 라벨이 겹치면 None."""
    found = [_LABEL_RE.match(x) for x in items]
    if not items or not all(found):
        return None
    labels = {m.group(1): m.group(2) for m in found}
    return labels if len(labels) == len(items) else None


def _resolve(side: str, labels: dict[str, str]) -> str | None:
    """정답 짝의 한쪽을 항목 본문으로. 꼬리표만(`1`·`A`)이어도, 꼬리표+글(`A. 과거 비만 사용`)이어도 꼬리표로 찾는다.

    **글은 보지 않는다.** 261002_03 Q046 은 정답 짝에 보기 글을 줄여 써서(「과거 비만 사용/중독」) 글로는
    짝이 안 맞았다. 프롬프트 v1.3 부터 왼쪽 1·2·3, 오른쪽 A·B·C 를 붙이고 짝을 `1. … - A. …` 로 적게 했다
    (2026-10-05 관리자 제안 — 「컴퓨터, 인간 모두 읽을 수 있게」).
    """
    if side in labels:
        return labels[side]
    found = _LABEL_RE.match(side)
    return labels.get(found.group(1)) if found else None


def tidy_labels(bank: dict) -> list[str]:
    """정답이 라벨(`L1`·`B`)만 가리키면 라벨을 떼고 본문으로 맞춘다. 고친 문항 ID 를 돌려준다.

    261002_02 실측(2026-10-04): 같은 응답을 두 번 정리했더니 한 번은 라벨을 풀고 한 번은 안 풀었다 —
    안 푼 쪽에서 matching 4 · sequence 2 문항이 「참조 오류」로 떨어졌다. 모델에 맡기지 않는다.
    """
    fixed = []
    for q in bank.get("questions", []):
        if q.get("format") == "matching":
            left, right = _unlabel(q["matching_left"]), _unlabel(q["matching_right"])
            pairs = q["answer_pairs"]
            resolved = [(_resolve(p["left"], left), _resolve(p["right"], right)) for p in pairs] if left and right else []
            if resolved and all(a and b for a, b in resolved):
                q["matching_left"], q["matching_right"] = list(left.values()), list(right.values())
                q["answer_pairs"] = [{"left": a, "right": b} for a, b in resolved]
                fixed.append(q["question_id"])
        if q.get("format") == "sequence":
            items = _unlabel(q["sequence_items"])
            if items and all(x in items for x in q["correct_order"]):
                q["sequence_items"] = list(items.values())
                q["correct_order"] = [items[x] for x in q["correct_order"]]
                fixed.append(q["question_id"])
    return fixed


# `AD10–AD14` · `C3-C5` — ChatGPT 가 관련 개념을 범위로 적는다.
_RANGE_RE = re.compile(r"^\s*([A-Za-z]+)(\d+)\s*[–—~-]\s*(?:[A-Za-z]+)?(\d+)\s*$")


def tidy_related(bank: dict) -> list[str]:
    """관련 개념의 범위 표기를 풀고, 없는 개념을 가리키는 연결은 뺀다. 고친 내용을 돌려준다.

    261002_03 의 같은 응답(6-sol)을 두 번 정리했더니 한 번은 `AD10–AD14` 를 풀고 한 번은 그대로 두었다
    (2026-10-05) — 그대로 둔 쪽은 「related_concepts 오류」로 은행 전체가 막혔다. 모델에 맡기지 않는다.
    관련 개념은 개념 지도의 선으로만 쓰는 값이라, 못 찾는 연결은 그 하나만 뺀다.
    """
    concepts = bank.get("concepts") or []
    ids = {c.get("concept_id") for c in concepts if isinstance(c, dict)}
    notes = []
    for c in concepts:
        if not isinstance(c, dict) or not isinstance(c.get("related_concepts"), list):
            continue
        out: list[str] = []
        for ref in c["related_concepts"]:
            found = _RANGE_RE.match(ref) if isinstance(ref, str) and ref not in ids else None
            if found:
                prefix, lo, hi = found.group(1), found.group(2), found.group(3)
                width = len(lo)
                expanded = [f"{prefix}{n:0{width}d}" for n in range(int(lo), int(hi) + 1)]
                if expanded and all(x in ids for x in expanded):
                    out += expanded
                    notes.append(f"{c['concept_id']}: {ref} → {', '.join(expanded)}")
                    continue
            if ref in ids and ref != c.get("concept_id"):
                out.append(ref)
            else:
                notes.append(f"{c['concept_id']}: 없는 관련 개념 {ref} 를 뺐다")
        deduped = list(dict.fromkeys(out))
        if deduped != c["related_concepts"]:
            c["related_concepts"] = deduped
    return notes


def tidy_prerequisites(bank: dict) -> list[str]:
    """합쳐 옮긴 선행 ID를 실제로 존재하는 ID들로만 분리한다.

    약물수송체 은행에서 `DT-C20; DT-C17`을 하나의 ID로 옮겨 정상 문항까지
    검증에서 빠졌다. 본문 추정 없이 모든 조각이 실제 ID일 때만 복원한다.
    """
    questions = bank.get("questions") or []
    ids = {q.get("question_id") for q in questions if isinstance(q, dict)}
    notes = []
    for q in questions:
        if not isinstance(q, dict) or not isinstance(q.get("prerequisites"), list):
            continue
        out = []
        changed = False
        for ref in q["prerequisites"]:
            if isinstance(ref, str) and ref not in ids:
                parts = [p.strip() for p in re.split(r";|<br\s*/?>", ref)]
                if len(parts) > 1 and all(p in ids for p in parts):
                    out.extend(parts)
                    changed = True
                    notes.append(f"{q['question_id']}: {ref} → {', '.join(parts)}")
                    continue
            out.append(ref)
        if changed:
            q["prerequisites"] = list(dict.fromkeys(out))
    return notes


def tidy_matching_choices(bank: dict) -> list[str]:
    """Remove identical right-hand choices while preserving many-to-one answers."""
    fixed = []
    for q in bank.get("questions", []):
        if q.get("format") != "matching":
            continue
        right = q.get("matching_right", [])
        unique = list(dict.fromkeys(right))
        if unique != right:
            q["matching_right"] = unique
            fixed.append(q["question_id"])
    return fixed


def organize(raw: str, lecture: dict, *, model: str | None = None, out: Path | None = None) -> tuple[dict, dict]:
    """`(bank, info)`. lecture = {title, sources: [{id, kind, filename}]}."""
    from .web_audit import enabled
    from .compact import deduplicate_repeats, read_blocks, restore
    prepared, repeated = deduplicate_repeats(clean_response(raw))
    blocks = read_blocks(prepared)
    if out is not None and enabled(lecture.get("prompt_version", "")):
        from .file_organize import convert
        bank, info = convert(prepared, organizer_prompt(prepared, lecture), out, model=model)
    else:
        bank, info = session.run_structured(organizer_prompt(prepared, lecture), BANK, system=SYSTEM,
                                            label="정리", timeout=1200, model=model)
    bank = without_retired(bank)   # 옛 응답을 다시 정리해도 뺀 칸은 남기지 않는다
    bank["build_meta"]["schema_version"] = expected_schema(raw, lecture)
    restore(bank, blocks)
    if repeated and isinstance(bank.get("warnings"), list):
        bank["warnings"].append(f"[중복 기록] 내용이 같은 문항 블록 {len(repeated)}회를 한 번만 저장했다: {', '.join(repeated)}")
    fixed = tidy_labels(bank)
    matching = tidy_matching_choices(bank)
    if matching and isinstance(bank.get("warnings"), list):
        bank["warnings"].append(f"[정리] 동일한 짝짓기 보기를 합쳤다: {', '.join(matching)}")
    if fixed and isinstance(bank.get("warnings"), list):
        bank["warnings"].append(f"[정리] 짝짓기·순서 라벨을 떼고 본문으로 맞췄다: {', '.join(fixed)}")
    related = tidy_related(bank)
    if related and isinstance(bank.get("warnings"), list):
        bank["warnings"].append(f"[정리] 관련 개념을 맞췄다: {'; '.join(related)}")
    prerequisites = tidy_prerequisites(bank)
    if prerequisites and isinstance(bank.get("warnings"), list):
        bank["warnings"].append(f"[정리] 합쳐진 선행 문항 ID를 분리했다: {'; '.join(prerequisites)}")
    if out is not None:
        from studyez_contracts.bank.slide_focus import authored_hash
        questions = {q["question_id"]: q for q in bank["questions"]}
        evidence = {block["question_id"]: {"authoredHash": authored_hash(questions[block["question_id"]]),
                    "evidence": block["source_evidence"]} for block in blocks if block.get("source_evidence")}
        out.mkdir(parents=True, exist_ok=True)
        if repeated:
            (out / "repeated-blocks.json").write_text(json.dumps({"repeatedIds": repeated,
                "policy": "exact content only; original raw response preserved"}, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "authored-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return bank, info
