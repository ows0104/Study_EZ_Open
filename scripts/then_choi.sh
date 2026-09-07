#!/usr/bin/env bash
# 앞의 2편이 끝나면 최민호 넷을 이어 시작한다. 겹쳐 돌리지 않으려고 기다린다 —
# 한 편이 빈 세션을 7개까지 띄우므로 6편을 겹치면 그 배수가 된다.
set -u
cd "$(dirname "$0")/.."
while tasklist /FI "IMAGENAME eq python.exe" 2>/dev/null | grep -qi python; do sleep 60; done
echo "앞 2편 끝났다 $(date +%H:%M) — 최민호 넷 시작"
bash scripts/rebuild_choi.sh
