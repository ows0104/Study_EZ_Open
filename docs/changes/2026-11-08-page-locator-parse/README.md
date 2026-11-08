# 감염병리1 Main-Quiz 참고 슬라이드 복구 — 쪽 표기 파서

## Intent
2026-11-08 사용자: 「감염병리1에 참고 슬라이드가 안 붙어 있다」 → 원인 보고 후 「파서 고쳐줘」.

## 원인(운영 DB 읽기만으로 확인)
- 감염과 면역 261104_02 활성 판이 `main-quiz-reviewed-…`(98문항)에서 `map-tree-26110803`(79문항)으로 바뀌었다.
- Main-Quiz 정답의 참고 슬라이드는 `server/app/root_learning/evidence.py`가 `source_refs[].locator`를
  `studyez_contracts/bank/pages.py`의 `pages_of`로 읽어 쪽을 고른다.
- `pages_of`는 `p.8`·`slide 8`·`8쪽`만 읽었다. 옛 판은 `physical PDF p.3` 꼴이라 전부 읽혔고,
  Map 판은 `physical PDF page 8`·`page 7, 9, 11` 꼴(`studyez_contracts/bank/importance.py`가 쓰는 표기)이라
  S1 참조 84개가 하나도 읽히지 않았다. 결과: 79문항 중 69문항 0장, 10문항 1장.

## Spec
- `page N` / `pages N`과 그 뒤 쉼표 목록·범위(`page 7, 9, 11`, `pages 4–6`)를 읽는다.
- 기존 표기의 결과는 바꾸지 않는다. 범위 상한 `MAX_RANGE`는 그대로 적용한다.
- 문항·근거·학습 기록·공개 범위·DB는 바꾸지 않는다(코드만).

## 영향 범위
`pages_of`의 호출처: Main-Quiz 근거(evidence.py), Quiz Bank 학습 순서(study_engine/ordering.py),
카탈로그(bank_catalog.py), 업로드할 슬라이드 선택(quizbank/slides.py).
운영 전체 측정: `page N` 표기는 261104_02 map-tree 판의 89개뿐. 운영 Quiz Bank 40편의 참조 5,084개 중
옛/새 파서 결과가 달라지는 것은 0개 → 기존 은행의 순서·슬라이드 선택 불변.

## 검사
- 새 케이스 6개 포함 쪽 번호 18개 통과. tests/contracts + tests/quizbank 800 통과.
- 운영 데이터 재측정(읽기만, 새 코드): 261104_02 79문항 전부 1장 이상(1장 55·2장 17·3장 6·4장 1).
- 서버 전체 `-m tests`(PYTHONPATH=.. 로 이 브랜치 계약 사용): 128개 전부 통과.

## 남은 것(이 변경 밖)
족보(S2) 참조는 대부분 `2023 김지은 79번` 같은 문항 번호 표기라 쪽이 없어 족보 쪽 슬라이드는 붙지 않는다.
일부 S2 참조에 `S1 34쪽`처럼 다른 출처 쪽이 섞여 있다(S2 27쪽 밖이라 걸러진다).

## 배포·롤백
일반 코드 PR. master 병합 → API·웹 자동 배포. 데이터 변경 없음. 롤백은 이 PR revert.
배포 후 확인: 운영 health SHA, 감염병리1 정답 공개 시 참고 슬라이드 표시.
