# web 작업 안내

Study_EZ의 Vite·React·TypeScript 화면이다.
서버 HTTP API를 사용하며 로컬 생성기를 직접 부르지 않는다.

## 수정 위치

| 화면·책임 | 경로 |
|---|---|
| 캘린더·강의 패널 | `src/calendar/` |
| 관리·카드 검토 | `src/admin/`, `src/cards/` |
| 기존 예습·복습 풀이 | `src/lecture/` |
| Quiz Bank | `src/bank/` |
| 공지·이용방법 | `src/notices/` |
| 덱 모아받기 | `src/bundle/` |
| API 데이터 타입 | `src/types/`의 해당 기능 파일 |
| 색·여백 | `src/styles/` |

Quiz Bank의 `BankStudy.tsx`는 진입점이고 시작·풀이·문항 표시를
`BankStart.tsx`·`BankSolve.tsx`·`BankQuestion.tsx`로 나눈다.
생성 프롬프트의 정본은 `../content/prompts/bank/bankPrompt.md`이며 변경 시 버전을 갱신한다.

## 계약

- 기존 퀴즈 복습 간격은 서버 `app/srs.py`, Quiz Bank 문항 선택은 `app/study_engine/`의 책임이다.
- 학생에게는 관리자가 공개한 은행만 보인다.
- 카드 없음·오늘 학습 완료·몰아보기 완료는 다음 행동이 달라 별도로 표시한다.
- 학생용 생성 진행 API는 관리자 API와 다르다. 관리자 응답을 숨겨 그리는 방식으로 바꾸지 않는다.
- 공용 세션 원본은 `../platform/session/session.js`다.
- 학습 현황의 기본 블록은 한국 시간의 시간표·마지막 시험 종료를 기준으로 `src/bank/studyBlocks.ts`에서 고른다. 퀴즈 준비 여부는 전환 조건이 아니다. 토요일은 이전 금요일의 주, 일요일은 다음 월요일의 주다(2026-11-01 사용자 재확인). 같은 기본 블록 안의 수동 선택은 유지하고 기본 블록이 바뀌면 자동 전환한다.
- 버튼·단축키·화면 이름을 바꾸면 `src/notices/GuidePage.tsx`도 확인한다.

## 검사·배포

이 폴더에서 `npm run typecheck`, 필요하면 `npm run build`를 실행한다.
`dev`·`build`는 `scripts/pack-extension.mjs`로 확장 ZIP도 만든다.
확장 코드는 [bridge](../bridge/CLAUDE.md)를 수정한다.

설치·실행은 [README](README.md), 운영 배포는
[Pages 실행서](../docs/cloudflare-pages-runbook.md)를 따른다.
웹 push와 API 배포는 별개이며, API 계약을 같이 바꾸면 배포 순서를 검토한다.

사용자 행동을 추가/변경할 때 [이용현황 행동 등록](../docs/development/usage-actions.md)을 함께 따른다. 이용현황의 행동 이름/단위는 서버 카탈로그를 사용하며 별도 목록을 만들지 않는다.
