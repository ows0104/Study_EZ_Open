"""Observe outputs of the exact live CLI attempt when its console log is quiet."""
from __future__ import annotations

import json
from pathlib import Path

from .status import option, tail

OUTPUTS = {
    "bank.json": "문항 파일 저장됨",
    "option-pools.json": "보기 풀 저장됨",
    "explanations.json": "정답·해설 저장됨",
    "validation.json": "구조 검증 결과 저장됨",
    "coverage.json": "원본·출제 포인트 대조 결과 저장됨",
    "review.json": "정답 검토 결과 저장됨",
    "learning-structure.json": "학습 구조 결과 저장됨",
    "authored-evidence.json": "핵심 근거 저장됨",
    "checkpoint.json": "검수 체크포인트 저장됨",
    "result.json": "최종 처리 결과 저장됨",
}


def observe(runs: Path, run_id: str, children: list[dict], log: Path, now: float):
    for child in children:
        command = child.get("CommandLine") or ""
        if "quizbank.run" not in command and "quizbank.independent" not in command:
            continue
        value = option(command, "--out")
        if not value:
            continue
        out = Path(value).resolve()
        if not out.is_relative_to((runs / run_id / "bank").resolve()):
            continue
        observations = []
        for name, label in OUTPUTS.items():
            try:
                observations.append(((out / name).stat().st_mtime, label, name))
            except OSError:
                pass
        usage = out / "usage.jsonl"
        for line in reversed(tail(usage, 3)):
            try:
                entry = json.loads(line)
                if isinstance(entry.get("step"), str) and isinstance(entry.get("t"), (int, float)):
                    observations.append((min(now, entry["t"]), f"{entry['step']} 완료 기록", "usage.jsonl"))
                    break
            except (ValueError, AttributeError):
                continue
        if not observations:
            return None
        updated, label, filename = max(observations, key=lambda item: item[0])
        try:
            if log.stat().st_mtime >= updated:
                return None  # Fresh stage output takes priority over saved artifacts.
        except OSError:
            pass
        return f"산출물 확인 · {label}", (f"현재 시도 {out.name} · 관측 파일 {filename}",), max(0, int(now - updated))
    return None
