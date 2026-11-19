# 결과와 반영 순서

## 만든 것 (이 PC, 2026-11-20)

- `fixes/pes_infection-immunity-1-2026_0c.json`(git 밖)에 29문항 `moveTo`. 기존 그림·선지 교정 4건은 그대로 두고 사유만 덧붙였다.
  `add_moves.py`로 같은 파일이 다시 만들어진다(바이트 동일 확인, 두 번 돌려도 같음).
- 재빌드: 45세트·519문항·해설 519 그대로, 강의 49 → 51, 붙지 않은 세트 0, problems 0.

| 강의 | runId | 이전 | 이후 | 같은 문제 합침 | 변형 묶음 | 그림 |
|---|---|---|---|---|---|---|
| CBL 3 | 261113_03 | 31 | 3 | 0 | 0 | 4 |
| CBL 4 | 261116_07 | 없음 | 17 (18문항, 2023-19 = 2025-66) | 1 | 4 | 17 |
| CBL 5 | 261118_03 | 없음 | 11 | 0 | 2 | 11 |

- 원본 정답표(p.116-117)와 29문항 정답 전부 일치(2025-64 전원정답 포함). 그림 0개 문항(2025-66, 2022-46, 2021-6, 2020-72, 2020-65)은
  원본 p.85-92를 렌더해 그림 없는 지문형임을 확인했다.
- 다른 강의 문서는 올해 필기가 들어와 `professorSource`가 timetable → notes로만 바뀌었다(교수·문항 동일). 이번에 올리지 않는다.
- `move_marks.py`는 격리된 임시 SQLite에서 시험했다: CBL 4·5 문항 3행만 event_id가 바뀌고 CBL 3 문항·밴드·횟수는 그대로.

## 운영 반영 (러너 PC, 사용자 승인 후)

이 PC에는 server/.env·러너 토큰이 없어 업로드와 운영 DB 조회를 하지 않았다. 아래는 아직 **미실행**이다.

```bash
python docs/changes/2026-11-20-cbl45-jokbo/add_moves.py          # 러너 PC 교정 파일에 이동 얹기
python -m runner.jokbo_solve build                               # CBL 3 = 3, CBL 4 = 17, CBL 5 = 11 확인
python -m runner.jokbo_solve upload --audience all --only "CBL 3" "CBL 4" "CBL 5"
python docs/changes/2026-11-20-cbl45-jokbo/move_marks.py         # 옮길 기록 수만 본다
python docs/changes/2026-11-20-cbl45-jokbo/move_marks.py --apply # 기존 오답노트 기록을 CBL 4·5로
```

업로드와 기록 이전 사이에는 CBL 3에서 표시한 CBL 4·5 문항이 오답노트에서 잠깐 빠진다(기록은 남아 있다).
되돌리기: 이전 빌드의 CBL 3 문서를 다시 올리고, `move_marks.py`의 대상·원래 event_id를 바꿔 역으로 돌린다.
