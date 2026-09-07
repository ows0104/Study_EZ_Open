#!/usr/bin/env bash
# 2026-09-07 — 사용량 한도(3:10pm 리셋)로 끊긴 마지막 두 편.
#
#   260904_01  수선1 에서 끊겼다. ①②·재현 검사가 다 있으므로 --resume 이 싸다.
#              **--jokbo-dir 을 손으로 준다** — `pdf2anki.run --resume` 이
#              run.config.json 에서 그 값을 안 되살려 기본값 out/jokbo 를 보고
#              「기출 조각을 못 찾았다」로 빌드가 거부한다(오늘 두 번 겪었다).
#              --apkg-name 도 마찬가지라 resume 으로 구운 덱은 이름이 p<id>.apkg 가
#              된다. 그래서 뒤에 `studyez rebuild` 로 규칙대로 다시 굽는다.
#   260904_02  ②카드 에서 끊겼다. 이어붙일 자리가 없어 처음부터 간다.
#              전략은 watch.PROFESSOR_STRATEGY 가 붙인다(최민호 → 필기).
set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=/c/Users/ows01/anaconda3/python.exe

# 한도가 풀릴 때까지 기다린다. 시계가 아니라 **실제로 되는지**로 판정한다 —
# 리셋 시각은 로그에 찍힌 안내일 뿐이고 몇 분 어긋난다.
until "$PY" -c "
import sys; sys.path.insert(0,'.')
from pdf2anki.session import run_blind
run_blind('{\"ok\":true} 만 내라.', timeout=120, label='한도확인')
" >/dev/null 2>&1; do
    echo "[$(date +%H:%M)] 아직 한도. 10분 뒤 다시 본다"
    sleep 600
done
echo "[$(date +%H:%M)] 한도 풀렸다 — 시작"

( "$PY" -m pdf2anki.run --resume runs/260904_01 --jokbo-dir runs/_jokbo/기생충학 \
      > runs/manual.260904_01.resume.log 2>&1 \
  && "$PY" -m studyez rebuild --run-id 260904_01 >> runs/manual.260904_01.resume.log 2>&1
  echo "[$(date +%H:%M)] 260904_01 rc=$? — $(tail -2 runs/manual.260904_01.resume.log | tr '\n' ' ' | cut -c1-90)" ) &

( "$PY" -m studyez watch 기생충학 --run-id 260904_02 --build --force --now \
      > runs/manual.260904_02.rebuild.log 2>&1
  echo "[$(date +%H:%M)] 260904_02 rc=$? — $(tail -2 runs/manual.260904_02.rebuild.log | tr '\n' ' ' | cut -c1-90)" ) &

wait
echo "끝 $(date +%F' '%H:%M)"
