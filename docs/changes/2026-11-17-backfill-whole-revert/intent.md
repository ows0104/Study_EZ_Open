# 보강: 한 회차의 고치기가 전부 나빠지면 회차를 통째로 되돌린다

## 무슨 일이 났나

2026-11-17 03:53 보강 job 670(감염과 면역/261112_03 간염바이러스)이 멈췄다.

> 연결 자동출제 보류: v3 fix output.questions: too few entries

모델 호출은 전부 끝난 뒤였다(`v4-review-presuppose-2`까지 completed). 올리기 전이라 공개판은 그대로다.

## 원인

고치기 회차의 재검토가 그 회차의 수정을 **전부** 더 나쁘다고 판정하면 남길 수정이 없다.
본 출제(`connection_generate_v4.py`·`_v3.py`)는 이 경우를 따로 다룬다.

```python
if reverted and not kept:
    S.bank, S.conflicts, S.stimuli, S.basis = before     # 회차를 통째로 되돌림
elif reverted:
    part = v3.fixes_of(plain, kept) ...                  # 남길 것만 다시 합침
```

보강(`connection_presuppose.py`)은 이 코드를 옮기면서 첫 갈래를 빠뜨렸다. 주석은
「(the whole round when every fix of it was worse)」라고 적혀 있지만, 실제로는 빈 목록을
`merge_fixes`에 넘겼고 그 함수의 출력 모양 검사(문항 1개 이상)가 멈췄다.

## 고침

보강에도 같은 갈래를 둔다. 전부 되돌릴 때는 회차 전의 은행·그림·중요도 근거·충돌 기록으로 돌아간다.
일부만 되돌리는 경로는 손대지 않았다.

## 확인

- `tests/quizbank/test_connection_presuppose.py::test_a_round_whose_every_fix_is_worse_is_undone_as_a_whole` —
  고침 없이 돌리면 위와 같은 오류로 실패하고, 고침을 넣으면 끝까지 가서 서버 검증(`validate_result`)도 통과한다.
- 실제 판(261112_03)의 재현은 이 자리를 넘어가지만, 그 강의는 아래 별개의 사정으로 조립에서 다시 멈춘다.

## 같이 본 것 (이번 고침 아님)

261112_03의 공개판은 필기 PDF가 교체된 판이다(`unplacedOnly.sourceUpdate`, notes-update/1,
`docs/changes/2026-11-16-replace-updated-notes`). brief는 옛 파일(7fe1cf7f…)을, packet은 새 파일(3b242e3d…)을
가리킨다. 보강은 새 문항을 합칠 때마다 은행의 모든 그림을 packet의 파일로 다시 렌더하므로, 공개 문항
다섯 개(Q032·Q113·Q174·Q175·Q178)의 그림이 새 파일 지문을 달게 되고 조립의 `validate_images`가
「stimuli: source/page mismatch」로 멈춘다. 보강이 notes-update 판을 이어받는 길은 아직 없다.
11-17 기준 보강 대상 가운데 이런 판은 이 한 편이다.
