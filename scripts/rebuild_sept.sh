#!/usr/bin/env bash
# 2026-09-06 — 09-01~09-04 기생충학 나머지 14편을 새 cloze 프롬프트로 다시 만든다.
# 260901_01 은 앞서 손으로 돌려 봤으므로 여기 없다.
#
# **4개씩 돈다.** 한 편이 재현 검사에서 세션을 7개까지 동시에 띄우므로 그 위에
# 4를 곱한 것이 이 기계가 한 번에 여는 세션 수다. 더 올리기 전에 한도부터 재라.
#
# 한 편이 죽어도 나머지는 간다 — 로그를 편마다 따로 남기고 여기서는 종료 코드만 센다.

set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=/c/Users/ows01/anaconda3/python.exe

IDS="260901_02 260901_03 260902_01 260902_02 260902_03 260902_05 260903_01
     260903_02 260903_03 260903_05 260904_01 260904_02 260904_03 260904_05"

one() {
    id="$1"
    started=$(date +%s)
    "$PY" -m studyez watch 기생충학 --run-id "$id" --build --force --now \
        > "runs/manual.$id.rebuild.log" 2>&1
    rc=$?
    mins=$(( ($(date +%s) - started) / 60 ))
    tail=$(tail -3 "runs/manual.$id.rebuild.log" | tr '\n' ' ')
    echo "[$(date +%H:%M)] $id rc=$rc ${mins}분 — $tail"
}
export -f one
export PY

echo "시작 $(date +%F' '%H:%M) — 14편 · 4개씩"
echo "$IDS" | tr ' ' '\n' | grep -v '^$' | xargs -P 4 -I{} bash -c 'one {}'
echo "끝 $(date +%F' '%H:%M)"
