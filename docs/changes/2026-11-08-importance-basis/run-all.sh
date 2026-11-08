#!/usr/bin/env bash
# 감염병리1 재생성 — importance-basis/1(2026-11-08 사용자 「고친 뒤 다시」). 실패하면 그 자리에서 멈춘다 — 자동 재시도 없음.
# 실행 코드: 이 worktree(= 병합된 master). 실행 폴더: <main>/runs/_e2e/26110803 (git 밖).
#   bash docs/changes/2026-11-08-importance-basis/run-all.sh [points|generate|importance|assemble|all]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
MAIN="$(cd "$ROOT/../.." && pwd)"
PY="$MAIN/.venv/Scripts/python.exe"
OUT="$MAIN/runs/_e2e/26110803"
GEN="$OUT/generation"
export PYTHONIOENCODING=utf-8
cd "$ROOT"
step() { echo; echo "=== $(date '+%H:%M:%S') $*"; }
run() { "$PY" "$HERE/run.py" "$@"; }

points() {
  step prepare; run prepare
  step "point (Map reused from 26110802)"
  run point > "$OUT/point.log" 2>&1 || { echo "point failed"; cat "$OUT/point.log"; exit 1; }
  tail -2 "$OUT/point.log"
  step audit; run audit
  issues=$("$PY" -c "import json,sys;print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['issues']))" "$OUT/audit/audit.json")
  echo "audit issues: $issues"
  if [ "$issues" != "0" ]; then step repair; run repair; step final-audit; run final-audit; fi
  step verify-points; run verify-points
  step packet; run packet
}
generate() { step "root-generation/2"; "$PY" -m runner.root_native_json --packet "$GEN/packet.json" --out "$GEN"; }
importance() {
  step "importance review"
  "$PY" -m runner.root_importance_review --packet "$GEN/packet.json" --out "$GEN" \
    --reason "2026-11-08 사용자 「생성 시작」: 감염병리1 재생성(26110802)의 목표 중요도 작성과 최종 원본 대조 1회"
}
assemble() { step "assemble"; "$PY" -m runner.root_native_json --packet "$GEN/packet.json" --out "$GEN"; step results; run results; }

case "${1:-all}" in
  points) points ;;
  generate) generate ;;
  importance) importance ;;
  assemble) assemble ;;
  all) points; generate; step results; run results ;;
esac
step done
