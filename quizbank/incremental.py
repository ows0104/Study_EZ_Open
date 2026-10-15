"""Reuse item judgments only inside one run; always repeat global source checks."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import fitz
import jsonschema

from studyez_llm import codex
from studyez_llm.pdf import render
from server.app.bank_validation import pool_checks

from . import coverage, explain, priority, review, web_audit, web_priorities
from .generate import item_quality_guidance, lecture_scope
from .session import SessionError

PROMPT = Path(__file__).parent / "prompts" / "incremental-source.md"
POLICY_VERSION = 1
DELTA_REPORT = copy.deepcopy(web_audit.REPORT)
DELTA_REPORT["properties"]["reviewed_question_ids"] = {"type": "array", "items": {"type": "string"}}
DELTA_REPORT["required"].append("reviewed_question_ids")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class Reviews:
    """A new instance starts with no trusted judgments, including resumed jobs.

    Wrong/doubt judgments are reused unchanged too. Reuse is never a way to turn a
    finding into a pass. Missing/invalid records are not inserted into the cache.
    """

    def __init__(self, out: Path, title: str, sources: list[dict], pdf: Path,
                 jokbo: Path | None, model: str | None, prompt_version: str):
        self.out, self.title, self.sources = out, title, copy.deepcopy(sources)
        self.pdf, self.jokbo, self.model = pdf, jokbo, model
        self.prompt_version = prompt_version
        self.entries: dict[str, dict[str, dict]] = {k: {} for k in ("explain", "source", "answer")}
        self.calls = Counter()

    @classmethod
    def create(cls, out, title, sources, pdf, jokbo, model, prompt_version):
        # Incomplete provenance falls back to the existing full-review pipeline.
        if pdf is None or not sources or any(not all(s.get(k) for k in ("id", "kind", "filename")) for s in sources):
            return None
        return cls(out, title, sources, pdf, jokbo, model, prompt_version)

    def context(self, bank: dict, points: list[dict] | None, raw: str, stage="answer") -> str:
        files = (self.pdf, self.jokbo, explain.PROMPT, review.PROMPT, web_audit.PROMPT, PROMPT)
        return digest({"policy": POLICY_VERSION, "title": self.title, "sources": self.sources,
            "model": codex.model_name(self.model), "promptVersion": self.prompt_version,
            "files": [hashlib.sha256(p.read_bytes()).hexdigest() if p else None for p in files],
            "guidance": item_quality_guidance(), "raw": raw if stage == "source" else None,
            "contracts": [review.SYSTEM, review.REVIEW_REPORT, explain.REPORT, web_audit.REPORT, DELTA_REPORT],
            "bankContext": {k: v for k, v in bank.items() if k not in ("questions", "audit_summary", "warnings")}})

    def keys(self, bank: dict, points, raw, *, context=None, stage="answer") -> dict[str, str]:
        context = context or self.context(bank, points, raw, stage)
        questions = {q["question_id"]: q for q in bank["questions"]}
        if len(questions) != len(bank["questions"]):
            raise SessionError("증분 검수: 중복 문항 ID는 재사용할 수 없습니다.")
        result = {}
        for qid, question in questions.items():
            # Invalidate dependents when a referenced question changes, including
            # transitive prerequisites and other questions in the same conflict.
            pending, seen = list(question.get("prerequisites", [])), {qid}
            if question.get("conflict_id"):
                pending += [key for key, q in questions.items() if q.get("conflict_id") == question["conflict_id"]]
            while pending:
                pid = pending.pop()
                if pid in seen:
                    continue
                seen.add(pid)
                if pid in questions:
                    pending.extend(questions[pid].get("prerequisites", []))
                    conflict = questions[pid].get("conflict_id")
                    if conflict:
                        pending.extend(key for key, q in questions.items() if q.get("conflict_id") == conflict)
            plan = None
            if stage == "source":
                linked = set(self.entries["source"].get(qid, {}).get("pointIds", []))
                sid = next((s["id"] for s in self.sources if s["kind"] == "notes_current"), "S1")
                pages = {p for ref in question["source_refs"] if ref["source_id"] == sid
                         for p in web_audit.authored_pages(f"{sid} {ref['locator']}", sid)}
                plan = [p for p in (points or []) if p["point_id"] in linked
                        or pages.intersection(web_audit.authored_pages(p["source_refs"], sid))
                        or (not pages and not linked)]
                plan = sorted(plan, key=lambda p: p["point_id"])
            result[qid] = digest([context, question, plan,
                                 {pid: questions.get(pid) for pid in sorted(seen - {qid})}])
        return result

    def select(self, stage, bank, points, raw):
        keys = self.keys(bank, points, raw, stage=stage)
        cache = self.entries[stage]
        reused = {qid for qid, key in keys.items() if cache.get(qid, {}).get("key") == key}
        return keys, reused

    def related(self, bank, targets):
        questions = {q["question_id"]: q for q in bank["questions"]}
        seen, pending = set(), list(targets)
        while pending:
            qid = pending.pop()
            if qid in seen or qid not in questions:
                continue
            seen.add(qid)
            q = questions[qid]
            pending.extend(q.get("prerequisites", []))
            if q.get("conflict_id"):
                pending.extend(pid for pid, other in questions.items() if other.get("conflict_id") == q["conflict_id"])
        return [copy.deepcopy(q) for qid, q in questions.items() if qid in seen and qid not in targets]

    def record(self, stage, bank, keys, reused, report, *, output=None):
        event = {"stage": stage, "checkedAt": datetime.now(UTC).isoformat(),
                 "inputBankHash": coverage.bank_hash(bank), "keys": keys,
                 "checkedQuestionIds": [qid for qid in keys if qid not in reused],
                 "reusedQuestionIds": [qid for qid in keys if qid in reused],
                 "globalSourceCheck": stage == "source",
                 "priorJudgments": {qid: self.entries[stage][qid]["checkedAt"] for qid in keys if qid in reused}}
        if output is not None:
            event["outputBankHash"] = coverage.bank_hash(output)
        report["incremental"] = event
        with (self.out / "review-reuse.jsonl").open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(event, ensure_ascii=False) + "\n")
        label = {"explain": "해설", "source": "원본·문항", "answer": "정답"}[stage]
        print(f"  증분 검수 {label}: 새 검수 {len(keys) - len(reused)}문항 · 재사용 {len(reused)}문항", flush=True)
        return event["checkedAt"]

    def explanations(self, bank, points, raw, *, pdf_source="S1"):
        subset = {**bank, "questions": explain.targets(bank)}
        # Dependency keys use the whole bank, not just explanation target types.
        target_ids = {q["question_id"] for q in subset["questions"]}
        keys = {qid: key for qid, key in self.keys(bank, points, raw, stage="explain").items() if qid in target_ids}
        reused = {qid for qid, key in keys.items() if self.entries["explain"].get(qid, {}).get("key") == key}
        todo = {**bank, "questions": [q for q in subset["questions"] if q["question_id"] not in reused]}
        fresh, info = {"annotations": []}, {"seconds": 0}
        self.calls["explain"] += 1
        if todo["questions"]:
            work = self.out if not self.entries["explain"] else self.out / "incremental-explain" / str(self.calls["explain"])
            work.mkdir(parents=True, exist_ok=True)
            # Authoring history belongs to the global audit, not the independent
            # item explanation task. It must not churn otherwise identical items.
            item_input = {**todo, "audit_summary": {"summary": "", "changes": [], "rejected_candidate_count": 0}, "warnings": []}
            _, fresh, info = explain.write(item_input, self.pdf, self.title, work,
                pdf_source=pdf_source, jokbo=self.jokbo, model=self.model,
                related_questions=self.related(bank, {q["question_id"] for q in todo["questions"]}))
        rows = {r["question_id"]: copy.deepcopy(r) for r in fresh["annotations"]}
        rows.update({qid: copy.deepcopy(self.entries["explain"][qid]["row"]) for qid in reused})
        merged = {"annotations": [rows[qid] for qid in keys if qid in rows]}
        updated, report = explain.apply(bank, merged)  # Completeness and immutable-content checks stay in force.
        checked_at = self.record("explain", bank, keys, reused, report, output=updated)
        context = self.context(bank, points, raw, "explain")
        for question in updated["questions"]:
            qid = question["question_id"]
            if qid not in keys or qid in reused:
                continue
            # Bind authored explanations to their output; changed dependencies are
            # not silently certified by this item's explanation generation.
            own_output = {**bank, "questions": [question if q["question_id"] == qid else q for q in bank["questions"]]}
            self.entries["explain"][qid] = {"key": self.keys(own_output, points, raw, context=context, stage="explain")[qid],
                "row": copy.deepcopy(rows[qid]), "checkedAt": checked_at}
        return updated, report, {**info, "checked_questions": len(todo["questions"]), "reused_questions": len(reused)}

    def answers(self, bank, points, raw):
        keys, reused = self.select("answer", bank, points, raw)
        todo = {**bank, "questions": [q for q in bank["questions"] if q["question_id"] not in reused]}
        fresh, info = {"summary": "", "reviews": [], "pool_checks": []}, {"seconds": 0}
        if todo["questions"]:
            fresh, info = review.review(todo, self.title, model=self.model,
                related_questions=self.related(bank, {q["question_id"] for q in todo["questions"]}))
        cache = self.entries["answer"]
        rows = [copy.deepcopy(cache[qid]["row"]) for qid in keys if qid in reused] + copy.deepcopy(fresh["reviews"])
        checks = [copy.deepcopy(r) for qid in keys if qid in reused for r in cache[qid]["checks"]] + copy.deepcopy(fresh.get("pool_checks", []))
        pool_coverage, _ = pool_checks.assess(bank, checks)
        known = set(keys)
        counts = Counter(r["verdict"] for r in rows)
        if pool_coverage["status"] != "verified":
            for row in rows:
                row.pop("option_pool_hash", None)
        report = {"summary": fresh["summary"] or "동일 문항의 기존 독립 정답 검수 판정을 보존했습니다.",
                  "reviews": sorted(rows, key=lambda r: list(keys).index(r["question_id"])),
                  "counts": {v: counts[v] for v in review.VERDICTS},
                  "missing": [qid for qid in keys if qid not in {r["question_id"] for r in rows}],
                  "poolCoverage": pool_coverage, "pool_checks": checks,
                  "requiresRevision": pool_coverage["status"] != "verified" or bool(fresh.get("requiresRevision")),
                  "reviewed_at": datetime.now(UTC).isoformat()}
        checked_at = self.record("answer", bank, keys, reused, report)
        for qid in known - reused:
            matching = [r for r in rows if r["question_id"] == qid]
            qchecks = [r for r in checks if r.get("question_id") == qid]
            q = next(q for q in bank["questions"] if q["question_id"] == qid)
            valid, _ = pool_checks.assess({"questions": [q]}, qchecks)
            if len(matching) == 1 and qid not in fresh.get("missing", []) and valid["status"] == "verified" \
                    and pool_coverage["status"] == "verified":
                cache[qid] = {"key": keys[qid], "row": copy.deepcopy(matching[0]),
                              "checks": copy.deepcopy(qchecks), "checkedAt": checked_at}
        return report, {**info, "checked_questions": len(todo["questions"]), "reused_questions": len(reused)}

    def source(self, bank, raw, points, *, defer_structure=False):
        points = web_audit.parse_points(raw) if points is None else points
        keys, reused = self.select("source", bank, points, raw)
        self.calls["source"] += 1
        if not reused:
            work = self.out if self.calls["source"] == 1 else self.out / "incremental-source" / f"full-{self.calls['source']}"
            work.mkdir(parents=True, exist_ok=True)
            report, usage = web_audit.inspect(bank, raw, self.pdf, self.title, self.sources, work,
                jokbo=self.jokbo, model=self.model, points=points, defer_structure=defer_structure)
        else:
            report, usage = self._source_delta(bank, raw, points, keys, reused, defer_structure)
        checked_at = self.record("source", bank, keys, reused, report)
        raw_report = report["webAudit"]
        # Global checks can discover a new interaction involving an unchanged
        # item. Retain that finding even if a later global pass does not repeat it.
        for qid in keys:
            if qid not in reused:
                continue
            self.entries["source"][qid]["issues"] = copy.deepcopy(
                [r for r in raw_report["question_issues"] if r["question_id"] == qid and r["issue"] != priority.ISSUE])
            self.entries["source"][qid]["pointIds"] = [r["point_id"] for r in raw_report["checks"] if qid in r["question_ids"]]
        # The existing full review contract covers every question. Delta calls
        # additionally attest each requested item ID, checked below.
        for qid in set(keys) - reused:
            q = next(q for q in bank["questions"] if q["question_id"] == qid)
            checks = [r for r in raw_report.get("pool_checks", []) if r.get("question_id") == qid]
            valid, _ = pool_checks.assess({"questions": [q]}, checks)
            if valid["status"] == "verified" and report.get("poolCoverage", {}).get("status") == "verified":
                self.entries["source"][qid] = {"key": keys[qid], "checkedAt": checked_at,
                    "pointIds": [r["point_id"] for r in raw_report["checks"] if qid in r["question_ids"]],
                    "issues": copy.deepcopy([r for r in raw_report["question_issues"]
                                             if r["question_id"] == qid and r["issue"] != priority.ISSUE]),
                    "modes": copy.deepcopy([r for r in raw_report["classifications"] if r["question_id"] == qid]),
                    "checks": copy.deepcopy(checks)}
                self.entries["source"][qid]["key"] = self.keys(bank, points, raw, stage="source")[qid]
        for name, data in (("coverage.json", report), ("web-audit.json", report["webAudit"]),
                           ("classification.json", report["classification"])):
            (self.out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return report, usage

    def _source_delta(self, bank, raw, points, keys, reused, defer_structure):
        work = self.out / "incremental-source" / str(self.calls["source"])
        work.mkdir(parents=True, exist_ok=True)
        todo = {**bank, "questions": [q for q in bank["questions"] if q["question_id"] not in reused]}
        with fitz.open(self.pdf) as doc:
            count = len(doc)
            source_text = "\n\n".join(f"## PDF p.{i + 1}\n{p.get_text()}" for i, p in enumerate(doc))
        images = render(self.pdf, f"1-{count}", work / "source-pages")
        for name, data in (("bank.json", bank), ("item-review-bank.json", todo), ("point-plan.json", points),
                           ("source-pages.json", [str(p.resolve()) for p in images]),
                           ("pool-candidates.json", pool_checks.candidates(todo)),
                           ("web-priorities.json", web_priorities.reference(raw)),
                           ("review-scope.json", {"review_question_ids": [q["question_id"] for q in todo["questions"]],
                            "reused_question_ids": sorted(reused), "defer_structure": defer_structure}),
                           ("context.json", {"title": self.title, "sources": self.sources, "page_count": count,
                                             "lecture_scope": lecture_scope(self.title, self.sources)})):
            (work / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        (work / "source-text.md").write_text(source_text, encoding="utf-8")
        (work / "web-response.md").write_text(raw, encoding="utf-8")
        if self.jokbo:
            (work / "jokbo.md").write_text(self.jokbo.read_text(encoding="utf-8"), encoding="utf-8")
        output, info = coverage._call(PROMPT.read_text(encoding="utf-8") + "\n\n" + item_quality_guidance(),
                                     DELTA_REPORT, work, self.model, "원본 전체 대조·변경 문항 검수")
        jsonschema.validate(output, DELTA_REPORT)
        reviewed = output.pop("reviewed_question_ids")
        expected = set(keys) - reused
        if set(reviewed) != expected or len(reviewed) != len(expected):
            raise SessionError("증분 원본 검수: 변경 문항의 검토가 빠지거나 중복됐습니다.")
        modes = [r["question_id"] for r in output["classifications"]]
        expected_modes = {q["question_id"] for q in todo["questions"] if q["format"] in ("mcq", "multi_select")}
        if set(modes) != expected_modes or len(modes) != len(expected_modes):
            raise SessionError("증분 원본 검수: 변경 객관식의 분류가 빠지거나 중복됐습니다.")
        cache = self.entries["source"]
        for qid in keys:
            if qid not in reused:
                continue
            output["classifications"].extend(copy.deepcopy(cache[qid]["modes"]))
            output["pool_checks"].extend(copy.deepcopy(cache[qid]["checks"]))
            for issue in cache[qid]["issues"]:
                if issue not in output["question_issues"]:
                    output["question_issues"].append(copy.deepcopy(issue))
        order = {qid: i for i, qid in enumerate(keys)}
        output["classifications"].sort(key=lambda r: order.get(r["question_id"], len(order)))
        pdf_source = next((s["id"] for s in self.sources if s.get("filename") == self.pdf.name), "S1")
        report = web_audit.shape_report(output, bank, points, count, pdf_source=pdf_source)
        report.update(sourceFilename=self.pdf.name, sourceSha256=hashlib.sha256(self.pdf.read_bytes()).hexdigest())
        return report, [{"step": "원본·포인트·중복 검수", **info,
                         "checked_questions": len(expected), "reused_questions": len(reused)}]
