#!/usr/bin/env bash
# 2026-09-07 — 9월 재생성의 마지막 두 편. 앞서 사용량 한도로 ②에서 끊겼던 것들이다.
#
# **전략이 편마다 다르다.**
#   260904_03 말라리아(2)(최민호)          → 필기 중심 (관리자 지시)
#   260904_05 감염의 기초 실습 4 - 조충류(송현범) → 기본
#
# 최민호 편을 필기 중심으로 가는 것은 **실측 근거가 아니라 관리자의 판단이다.**
# 2026-09-07 에 「강의록에 없는 것을 낸다」는 썰을 2025 기출 20문항(그의 강의 7편)으로
# 재 봤는데 「강의록에 없다」가 0개였고, 지면을 눈으로 본 판정에서도 그가 0.83 으로
# 대조군(송현범 0.80 · 홍성태 0.67)보다 높았다. 썰은 지지되지 않았다.
# 그런데도 이쪽으로 가는 것은 안전 쪽으로 기운 선택이다 — 나중에 이 줄을 보고
# 「실측으로 정해졌다」고 읽지 마라.

set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=/c/Users/ows01/anaconda3/python.exe

one() {
    id="$1"; shift
    started=$(date +%s)
    "$PY" -m studyez watch 기생충학 --run-id "$id" --build --force --now "$@" \
        > "runs/manual.$id.rebuild.log" 2>&1
    rc=$?
    mins=$(( ($(date +%s) - started) / 60 ))
    echo "[$(date +%H:%M)] $id rc=$rc ${mins}분 — $(tail -3 "runs/manual.$id.rebuild.log" | tr '\n' ' ')"
}
export -f one
export PY

echo "시작 $(date +%F' '%H:%M) — 2편 동시"
{
    bash -c 'one 260904_03 --strategy 필기' &
    bash -c 'one 260904_05' &
    wait
}
echo "끝 $(date +%F' '%H:%M)"
