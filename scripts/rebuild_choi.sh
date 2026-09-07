#!/usr/bin/env bash
# 2026-09-07 — 이미 만들어 둔 최민호 편 넷을 필기 중심으로 다시 만든다.
# 전략은 `watch.PROFESSOR_STRATEGY` 가 붙인다 — 여기서 손으로 주지 않는다.
# 그 표가 실측이 아니라 관리자 판단이라는 것은 `watch.strategy_for` 주석에 있다.
set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=/c/Users/ows01/anaconda3/python.exe
IDS="260903_02 260903_03 260904_01 260904_02"
one() {
    id="$1"; started=$(date +%s)
    "$PY" -m studyez watch 기생충학 --run-id "$id" --build --force --now \
        > "runs/manual.$id.rebuild.log" 2>&1
    rc=$?; mins=$(( ($(date +%s) - started) / 60 ))
    echo "[$(date +%H:%M)] $id rc=$rc ${mins}분 — $(tail -2 "runs/manual.$id.rebuild.log" | tr '\n' ' ')"
}
export -f one; export PY
echo "시작 $(date +%F' '%H:%M) — 4편 · 2개씩"
echo "$IDS" | tr ' ' '\n' | xargs -P 2 -I{} bash -c 'one {}'
echo "끝 $(date +%F' '%H:%M)"
