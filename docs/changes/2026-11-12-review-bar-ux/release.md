# 복습바·로딩 속도·풀이 바·Ctrl+Z — 배포 준비

## 코드 리뷰·검증 결과

실제 데이터 동일성(읽기 전용, 쓰기 없음): 운영 DB를 `SET TRANSACTION READ ONLY`로 읽어 공개 Main-Quiz 23편 문서와
학습 기록이 가장 많은 계정의 이벤트 366건(이전 판 이벤트 37건 포함)을 로컬 파일로 받고, 고정 시각으로
`plan·summary·question_progress·lecture_score·learner_scope·task_tiers·replay` 7개를 계산했다.

| 비교 | 결과 | CPU |
|---|---|---|
| origin/master 코드 + 원본 문서 | 기준 | 12.19 s |
| 이 브랜치 + 원본 문서(지문 지연 계산) | 161/161 같음 | 0.30 s |
| 이 브랜치 + 가벼운 문서 | 161/161 같음 | 2.06 s(가벼운 문서 만들기 포함, 판마다 한 번) |

가벼운 문서 23편 JSON 합계는 원본 96 MB에서 그림 바이트(`png_base64` 85 MB)를 뺀 크기다.

검사:
- server `-m tests` 143/145 통과. 실패 2개(`test_root_map_tree`, `test_root_map_tree_v3`)는 빌려 쓴 venv에
  `pymupdf`/`fitz`가 없어 import 단계에서 멈춘 것(이 변경과 무관, 환경). 새 `test_root_light` 통과.
  기존 `test_root_learning_v4` 7단계(지문으로 이전 판 이력 잇기) 통과.
- web `tsc -b --noEmit` 통과(development.py verify 기록).
- 브라우저(Playwright, headless chrome, 이 worktree의 vite 5196):
  `bank-interactions` 15/15(새 `root-solve-bar`, Ctrl+Z·스페이스 사례를 더한 `root-choice-keys` 포함),
  `preferences` 3/3, `study-blocks` 15/15.
- 이 변경 전부터 실패(origin/master에서도 같은 자리): `calendar-loading`(첫 요청 목록에 `/api/study-plan`이 끼어
  단정 실패 + 시간 초과), `study-management`(약력학 행 「퀴즈 없음」 대기 시간 초과). 이 브랜치에서 캘린더 학습률 요청은
  StrictMode 개발 모드에서도 1번만 나간다(진행 중 요청 공유).
- 풀이 아래 바: 새 규칙을 끄면 짧은 문항에서 바가 화면 아래 40px, 긴 화면에서 16px(24px 움직임). 켜면 짧은 문항·답 연 뒤·
  스크롤 가운데·끝·다음 문항 모두 16px.

리뷰에서 본 것:
- 가벼운 문서는 요청 사이에 나눠 쓴다 → 만들 때 deepcopy로 ORM 행과 떼었다. 계산 함수들은 문서를 고치지 않는다(동일성 검사가 같은 사본을 7번 거쳐도 같음).
- 캐시 키는 (과목, 강의, 판, digest). RootContent는 넣기만 하고 고치지 않는다(코드 전체 확인).
- 그림의 존재·sha256·crop은 남긴다(`has_image` 같은 판단이 바뀌지 않게). 화면에 문항을 그리는 경로는 원본을 쓴다.
- 목록 요약에서 한 강의 실패는 그 강의만 빠진다. 웹은 시간표의 `mastery`로 그 강의 학습률을 그린다.
  근본 원인(계획 계산의 「Prepared prerequisite became unavailable」, 운영 500 계속)은 범위 밖 — 별도 작업.

## 배포 대상 버전·순서·데이터 변경

- master 병합 → GitHub 검사 → API(Cloud Run) → 같은 SHA 확인 뒤 Pages. DB 스키마·데이터 변경 없음.
- 메모리: 인스턴스당 가벼운 문서 최대 32편(LRU).

## 배포 후 확인·롤백·필요한 사람 승인

- Cloud Run 로그로 `GET /api/root-learning`, `GET /api/timetable?start&end&include_cards=false`,
  `POST /api/timetable/study-progress`의 지연을 배포 전(중앙값 11.5 s / 2.4 s / 0.4 s)과 비교. `/api/root-learning` 500이 사라졌는지.
  인스턴스 메모리 사용량.
- 롤백: git revert 후 master, 또는 이전 Cloud Run revision·Pages 배포. 데이터 변경이 없어 되돌릴 것은 코드뿐.
- 사람 승인: 「사람에게 묻는 것」에 닿지 않는다(코드만, 되돌릴 수 있음).
