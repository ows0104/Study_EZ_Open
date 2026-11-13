# Main-Quiz 자료 충돌 배지 — 설계

## 요구사항과 수용 기준
- `AnswerBody`가 `reviewInline={false}`(Main-Quiz, 검토 기록을 접어 따로 두는 화면)일 때만 답 맨 위에 `SourceConflictBadge`를 그린다.
- 표시 조건: 서버가 준 `answer.conflict`(판 문서 `bank_snapshot.source_conflicts`의 설명)가 비어 있지 않거나
  `evidenceStatus.category === "source_conflict"`. 화면이 충돌을 추측하지 않는다.
- 내용: 「자료 충돌」 태그 + 「자료끼리 설명이 다른 문항입니다. 시험 정답은 이 답과 다를 수 있습니다.」,
  판단 한 줄(구조화된 설명의 `판단:` 줄, 없으면 설명의 첫 줄, 근거 상태만 있으면 그 reason), 상세 위치 안내.
- 색: 기존 `--warn`·`--warn-soft`·`--warn-line` 토큰(밝은·어두운 화면 모두 정의됨).

## 호환성과 데이터 보존
- 서버 응답·DB·학습 기록 불변. 옛 판에 conflict가 없으면 배지가 없다(지금과 같음).
- Quiz Bank(`reviewInline` 기본 true)는 기존 「자료 비교」 접기를 그대로 그린다.
