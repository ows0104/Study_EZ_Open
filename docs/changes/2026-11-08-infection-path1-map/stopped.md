# 중단 기록 (2026-11-08)

사용자 결정: "여기서 멈추기". 이 작업은 결과(`result.json`) 없이 멈췄다. 성공이 아니다.

## 멈춘 지점

실행 폴더: `runs/_e2e/26110801/` (메인 체크아웃, git 밖)

| 단계 | 상태 |
|---|---|
| Map /3 추출 | 완료. 개념 68·뿌리 7·최대 깊이 3·관계 31 |
| 출제 포인트 | 완료. 75개. 최종 감사 `needs_revision`(4건)은 기록만 했다 |
| 문항 생성·원본 대조·독립 정답 검수 | 수정 3/3 소진. 최종 83문항. source-2 ok 78·doubt 5, medical-2 ok 76·doubt 7·wrong 0 |
| 정규화 개념 트리 | 개념 143(부모 있음 136), 목표 root 1·branch 26·leaf 74, 계층 결함 0 |
| 조립 | 실패. source-1·source-2가 목표 101개 전부를 `unknown`으로 둬서 과제 0개. 원인은 중요도 `unreviewed` |
| 중요도 보완(승인됨) | 1차: 단일 호출 2400초 초과. 2차: 갈래 7개 묶음은 끝났고 최종 source-3 대조가 2400초 초과 |

ledger 신원 `811c33f3…9312a69`, `importanceReview` 기록 없음. 문항·이전 검수·수정 예산은 그대로다.
자동 재시도는 하지 않았다. 로그: `importance.log`, `importance-2.log`.

## 결함과 수정

2차 실행 당시 `runner/root_importance_review.py`는 중요도 묶음 결과를 최종 원본 대조가 끝난 뒤에만
저장했다. 그래서 7개 묶음 결과·사용량이 디스크에 남지 않았다. 중단 뒤 PR 준비에서 고쳤다(모델 호출 없음):

1. 묶음마다 끝나는 즉시 `.importance-review-chunks/<갈래>.json`에 저장한다. 같은 lineage brief·
   목표 집합이면 다음 실행에서 다시 호출하지 않는다. 실패한 묶음·대조는 `failed-*`·`source-failed-*`로 남긴다.
2. 최종 원본 대조 시한은 5400초다. `call_model`의 기본 2400초는 그대로다.

검사: `tests/quizbank/test_importance_chunks.py`. 이 수정으로 다시 실행하지는 않았다.

## 브랜치에 남은 것

`claude/infection-path1-map`(미병합). 다음 생성에 그대로 쓸 수 있는 엔진 수정:
Map /3 `parent_id` 트리와 계층 보존 검사, 큰 그림 단계적 축소와 재호출 없는 렌더 복구,
독립 정답 검수의 문항별 판정 강제와 재검수 1회, PDF 판정의 localPath 확인과 순차 런타임 재검증,
트리 전용(container) 개념의 은행 투영과 지문 재결합, 중요도 보완 도구(위 결함 있음).

운영 등록·학생 공개·master 병합은 하지 않았다. 각각 별도 승인이 필요하다.
