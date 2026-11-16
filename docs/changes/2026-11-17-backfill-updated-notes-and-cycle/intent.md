# 보강: 필기를 교체한 판 이어받기 · 선행 간선이 문항 선행과 순환하지 않게

## 무슨 일이 났나

2026-11-17 보강에서 감염과 면역/261112_03(간염바이러스, job 670)만 끝까지 가지 못했다.
첫 멈춤(「too few entries」)은 PR #212가 고쳤다. 그 자리를 넘기자 조립에서 두 번 더 멈췄다.
실패한 판을 복사해 저장된 단계 출력으로 재현했다(`C:\sez\rp\c`, 모델 호출·운영 쓰기 없음).

### ① stimuli: source/page mismatch

이 강의의 공개판(a296fa10)은 필기를 v1 → v4로 교체한 판이다(notes-update/1,
`docs/changes/2026-11-16-replace-updated-notes`). 그 설계는 「brief·판정·그림은 이전 파일 그대로,
공개 문서만 새 파일을 가리킨다」이다. 그림 문항 다섯 개(Q032·Q113·Q174·Q175·Q178)는 v1에서 자른 그림과
그 sha(7fe1cf7f…)를 유지한다.

보강은 이 사정을 몰랐다.

- 새 문항을 합칠 때마다 은행의 **모든** 그림을 packet의 파일(v4, 3b242e3d…)로 다시 렌더했다.
  공개 문항의 그림이 새 파일 지문을 달게 되고, brief(v1)와 대조하는 조립 검사에서 멈췄다.
  멈추지 않았더라도 17쪽처럼 고쳐진 쪽의 그림은 바이트가 달라져 문항 지문이 바뀌고 학습 기록이 끊긴다.
- 조립한 문서에 교체 기록을 적용하지 않았다. 결과 manifest는 공개판의 `unplacedOnly.sourceUpdate`를 그대로
  물려받고 서버 검증(`_judgments4`)은 그 기록으로 문서를 교체해 대조하므로, 그림 문제가 없었어도
  「the document is not the assembly」로 거절됐을 것이다.

### ② prerequisites: combined target/question cycle

```
Q068@T062 ← Q071@T064   [목표 간선 PRE-c332633f1a6b]
Q071@T064 ← Q068@T062   [문항 선행]
  Q068 | HDV가 숙주로 전파·감염되기 위해 필요로 하는 HBV 단백은?
  Q071 | HBV 백신으로 HDV의 어떤 감염 형태를 예방할 수 있는가?   (선행 문항: Q068)
```

둘 다 공개 문항이다. 공개판에서 Q071은 Q068을 선행 문항으로 둔다. 전제 판정이 만든 「존재 목표 먼저」
간선은 반대로 T064 → T062였다. 목표 간선은 「뒤 목표의 모든 과제가 앞 목표의 모든 과제를 기다린다」이므로
두 문항이 서로를 기다린다. `presuppose.order_edges`·`discriminate.order_edges`의 순환 방지는 목표 그래프와
개념 그래프만 보고 문항 선행(`questions[].prerequisites`)은 보지 않았다. 필기 교체와 무관하고 어느 강의에서나
날 수 있다.

## 고침

1. `connection_presuppose.run` — 공개판에 `unplacedOnly.sourceUpdate`가 있으면
   - 교체된 원본에 그림이 있는 공개 문항은 **공개된 그림을 그대로** 둔다(`_render_keeping`).
     새 문항이 그 원본의 그림을 달면 이유를 적고 멈춘다 — 이전 파일은 packet에 없다(261112_03의 새 문항 39개는 그림 없음).
   - 승계 연결 뒤에 `v4.apply_source_update`를 적용한다. 서버 검증과 같은 순서다.
2. `presuppose.closes_task_cycle` — 간선 before → after를 놓기 전에, before의 과제가 문항 선행과 지금까지의
   목표 간선을 따라 after의 과제를 이미 기다리는지 본다. 그러면 그 간선은 놓지 않는다.
   두 `order_edges`가 `question_deps`(문항 → 선행 문항)를 받고 `make_document`가 넘긴다.

**기존 판의 검증은 달라지지 않는다.** 지금 통과하는 문서에는 순환이 없고, 순환 없는 그래프의 일부에도
순환이 없으므로 이 방지는 그 문서의 간선을 하나도 건너뛰지 않는다. 이 PC에 있는 /4 결과 67개를 새 계약과
이전 계약(master dce19b3f)으로 각각 다시 검증해 대조했다: 양쪽 모두 66개 통과, 1개 실패. 실패한 하나
(261105_05 c71577f1, 11-16 01:35의 보강 시범판)는 이전 계약 네 판(4d50fc68·d00c7991·72d2f1a5·dce19b3f)에서도
같은 이유로 실패한다 — 이 고침과 무관하다. 스크립트는 저장소 밖 `C:/sez/rp/revalidate.py`.

## 확인

- 261112_03 재현: 조립 통과, 과제 165 → 201, 승계 161/161 · 165/165, `replaced_sources` 유지.
  의학 검토만 가짜(전부 ok)로 채워 끝까지 돌리면 `validate_result`가 통과하고 생성 문서와 서버 재조립이 같다.
  공개 문항 179개는 그림까지 그대로다.
- 261106_06·261105_03(이미 #211로 통과하는 판)도 같은 코드로 다시 통과.
- 검사: `test_order_edges_do_not_cross_a_question_prerequisite`, `test_discriminate`의 같은 경우,
  `test_a_revision_with_replaced_notes_is_continued`(고침 없이는 「not the assembly」로 실패),
  `test_published_figures_of_replaced_notes_are_kept_and_new_ones_refused`.

## 바꾸지 않는 것

- 프롬프트·DB·API. 서버는 계약만 같이 배포된다.
- 필기 교체 판에서 새 문항이 그림을 달 수 있게 하는 일(이전 파일을 packet에 실어야 한다) — 지금은 멈추고 알린다.
- 건너뛴 간선의 학습 순서: 그 두 문항은 공개판의 문항 선행 순서를 따른다.
