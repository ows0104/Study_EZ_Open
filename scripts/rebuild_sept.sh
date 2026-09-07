#!/usr/bin/env bash
# 2026-09-06 — 09-01~09-04 기생충학을 새 cloze 프롬프트로 다시 만든다. 남은 10편.
# 앞의 다섯(260901_01~03 · 260902_01~02)은 이미 새 판이 나왔다.
#
# **2개씩 돈다.** 한 편이 재현 검사에서 세션을 7개까지 동시에 띄우므로 그 위에 2를
# 곱한 것이 이 기계가 한 번에 여는 세션 수다. 4로 돌렸을 때 죽은 것은 임시폴더
# 뒷정리였고 그건 커밋 b94efa2 에서 고쳤다 — 다만 4가 버티는지는 아직 안 재 봤다.
#
# **--resume 을 쓰지 않는다.** 260902_03·260903_03 은 items.raw.json 만 09-06 것이고
# items.reproduced.json 은 09-02/09-04 옛것이라, 이어 붙이면 재현 검사를 건너뛰고
# (`[건너뜀] 재현 검사 (items.reproduced.json 이미 있음)`) 옛 카드를 그대로 굽는다.
# --force 가 그 자리를 다시 만든다.
#
# 한 편이 죽어도 나머지는 간다 — 로그를 편마다 따로 남기고 여기서는 종료 코드만 센다.

set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=/c/Users/ows01/anaconda3/python.exe

IDS="260902_03 260902_05 260903_01 260903_02 260903_03
     260903_05 260904_01 260904_02 260904_03 260904_05"

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

echo "시작 $(date +%F' '%H:%M) — 10편 · 2개씩"
echo "$IDS" | tr ' ' '\n' | grep -v '^$' | xargs -P 2 -I{} bash -c 'one {}'
echo "끝 $(date +%F' '%H:%M)"
