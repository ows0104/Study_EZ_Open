# Main-Quiz 자료 충돌 배지 — 검증

- `tsc -b --noEmit` 통과, `npm run build` 통과.
- 고정물 `root-conflict-badge` 10개 검사 통과: 기록된 충돌 → 배지·판단 줄만·답 위 위치, 상세 비교는 접힌 기록에 남음,
  Quiz Bank 경로는 배지 없이 기존 비교 그대로, 충돌 없음·공백 → 없음, 근거 상태 「자료 충돌」만 → 배지(reason),
  다른 근거 상태 → 없음, 옛 자유 서술 충돌 → 첫 줄.
- 회귀: `choice-explanations`·`root-solve-bar`·`root-choice-keys` 통과.
- 밝은·어두운 화면 420px 스크린샷 확인(배지·태그 대비 정상).
- 미확인: 운영 데이터. 사용자가 본 Influenza B 문항은 판 문서에 충돌 기록(conflict_id)이 있어야 배지가 뜬다.
  기록이 없다면 이 변경으로는 보이지 않으며, 출제기의 충돌 기록 누락은 별도 작업이다.

## 배포
- 웹만, DB 변경 없음. 병합(=자동 배포) 후 Main-Quiz 답 화면에서 충돌 문항 확인. 롤백: PR revert.
