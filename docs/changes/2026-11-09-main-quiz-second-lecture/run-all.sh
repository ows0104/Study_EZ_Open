#!/usr/bin/env bash
# 사슬알균(261105_01) Main-Quiz 생성 시범 — 2026-11-09 사용자 「사슬알균」·「승인」. 실패하면 그 자리에서 멈춘다 — 자동 재시도 없음.
# 실행 코드: 이 worktree(= 병합된 master). 실행 폴더: <main>/runs/_e2e/26110901 (git 밖).
#   bash docs/changes/2026-11-09-main-quiz-second-lecture/run-all.sh [points|generate|resume|importance|assemble|all]
#   resume: GEN_DIR 폴더의 성공한 단계를 살리고 실패·달라진 단계부터 이어 간다 (REASON 필수, RERUN="source-2" 처럼 다시 돌릴 완료 단계 지정 가능).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
MAIN="$(cd "$ROOT/../.." && pwd)"
PY="$MAIN/.venv/Scripts/python.exe"
OUT="$MAIN/runs/_e2e/26110901"
GEN="$OUT/${GEN_DIR:-generation}"
export PYTHONIOENCODING=utf-8
cd "$ROOT"
step() { echo; echo "=== $(date '+%H:%M:%S') $*"; }
run() { "$PY" "$HERE/run.py" "$@"; }

points() {
  step prepare; run prepare
  step map; run map > "$OUT/map.log" 2>&1 || { echo "map failed"; cat "$OUT/map.log"; exit 1; }; tail -2 "$OUT/map.log"
  step point
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
resume() {
  : "${REASON:?REASON=<재개 이유> 가 필요하다}"
  extra=(); for s in ${RERUN:-}; do extra+=(--rerun "$s"); done
  step "root-generation/2 resume ${RERUN:-}"; "$PY" -m runner.root_native_json --packet "$GEN/packet.json" --out "$GEN" --resume "$REASON" "${extra[@]}"
}
importance() {
  step "importance review"
  "$PY" -m runner.root_importance_review --packet "$GEN/packet.json" --out "$GEN" \
    --reason "2026-11-09 사용자 「사슬알균」·「승인」: 사슬알균 생성 시범(26110901)의 목표 중요도 작성과 최종 원본 대조 1회"
}
assemble() { step "assemble"; "$PY" -m runner.root_native_json --packet "$GEN/packet.json" --out "$GEN"; step results; run results; }

case "${1:-all}" in
  points) points ;;
  generate) generate ;;
  resume) resume ;;
  importance) importance ;;
  assemble) assemble ;;
  all) points; generate; step results; run results ;;
esac
step done
