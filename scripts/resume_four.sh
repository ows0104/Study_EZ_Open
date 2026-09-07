#!/usr/bin/env bash
# 2026-09-06 — 09-01 2교시부터 4편. 넷 다 뒷정리 버그로 죽은 것들이라 **이어서 간다**.
#
# `--force` 로 통째로 다시 만들지 않는 이유: ①② 가 오늘 17:38~17:51 에 새 프롬프트로
# 이미 나와 있다(`items.checked.json`). 다시 돌리면 편당 $13 쯤을 같은 자리에 또 쓴다.
# 죽은 자리는 그다음인 재현 검사이고, 그 원인은 커밋 b94efa2 에서 고쳤다.
#
# `pdf2anki.run --resume` 은 덱까지 굽지만 `run.meta.json` 은 안 쓴다 — 그건
# `studyez rebuild` 가 모델 없이 몇 초에 한다(거기서 `deck.contract` 가 돈다).

set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=/c/Users/ows01/anaconda3/python.exe

IDS="260902_01 260902_02"

one() {
    id="$1"
    started=$(date +%s)
    "$PY" -m pdf2anki.run --resume "runs/$id" --jokbo-dir runs/_jokbo/기생충학 > "runs/manual.$id.resume.log" 2>&1
    rc=$?
    if [ $rc -eq 0 ]; then
        # run.meta.json 을 여기서 쓴다. 이게 없으면 문지기도 publish 도 이 편을 못 본다.
        "$PY" -m studyez rebuild --run-id "$id" >> "runs/manual.$id.resume.log" 2>&1
        rc=$?
    fi
    mins=$(( ($(date +%s) - started) / 60 ))
    echo "[$(date +%H:%M)] $id rc=$rc ${mins}분 — $(grep -c . "runs/manual.$id.resume.log" >/dev/null; tail -2 "runs/manual.$id.resume.log" | tr '\n' ' ' | cut -c1-110)"
}
export -f one
export PY

echo "시작 $(date +%F' '%H:%M) — 2편 동시"
echo "$IDS" | tr ' ' '\n' | xargs -P 4 -I{} bash -c 'one {}'
echo "끝 $(date +%F' '%H:%M)"
