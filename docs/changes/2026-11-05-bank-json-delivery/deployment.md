# JSON 문제은행 배포 기록

사용자 승인: 이 채팅에서 “배포하자.”라고 명시적으로 요청했다. 대상은 기존 StudyEZ의 API·웹·새 프롬프트 1.82와 JSON 수집 호환 코드이며, 운영 DB/기존 은행/학습 기록 교체는 하지 않는다.

후보: PR #6, f60b74915251081f53f9eb5910066378d9bff0f7. 로컬 필수 검사 5종과 코드 리뷰가 완료돼 있다. 저장소의 승인된 일반 코드 자동 경로(원격 검사→master 병합→master 검사→API→동일 SHA Pages)를 사용한다. 수동 후보 배포 경로를 우회 실행하지 않는다.

배포 전: PR 원격 전체 검사를 확인 중이다. 로컬 러너의 바탕화면 바로가기는 원래 Study_EZ_Open 작업 폴더를 가리키며 현재 실행 중인 runner agent/desktop 프로세스는 발견되지 않았다. 이 폴더의 기존 `_pairs/감염과 면역.json` 변경과 feedback-schema-compat 작업 폴더는 보존한다.

운영 반영/검증 결과는 완료 후 아래에 추가한다. 브라우저 확장 설치 상태는 소스/ZIP 버전만으로 적용됐다고 간주하지 않는다.

## 실제 반영 결과

- PR #6 전체 원격 검사 성공 후 master에 병합: a3f67d1321f5df8ac5764bd222cb5baaad8c996d.
- master 전체 검사와 운영 API 배포 성공: https://github.com/ows0104/Study_EZ_Open/actions/runs/42049760657 . 배포 영수증은 로컬 runs/_development/2026-11-05-bank-json-delivery/production-receipt에 보관했다.
- 실제 운영 API /api/health의 status=ok, environment=production, revision=a3f67d1321f5df8ac5764bd222cb5baaad8c996d를 확인했다. /api/timetable 및 /api/spotter/db의 무인증 401을 확인했다.
- Cloudflare Pages production 배포 def61194-ca93-4b75-b8b1-4fc802a1e874, Source=a3f67d1 성공을 확인했다. 브라우저에서 https://studyez.kr/bank-prompt.json 을 열어 실제 version=1.82와 복원된 6개 원칙, 제외 요청한 추가 recall_first 문장 미포함을 확인했다.
- 실제 로컬 러너 작업 폴더도 a3f67d13에 고정했다. 기존 codex/professor-aware-preview 브랜치는 보존했다. 매칭 파일 때문에 단순 전환이 막혀 해당 파일만 로컬 Git stash에 보존한 뒤 복원했다. Git 줄바꿈 정규화 차이는 원래 SHA-256과 일치하는 CRLF 바이트로 되돌렸으며 최종 지문 일치를 확인했다. 미추적 feedback-schema-compat 작업도 보존했다. 실제 라이브 경로의 JSON 변환 모듈을 불러와 합성 6문항을 변환했다. 원래 러너가 실행 중이지 않아 자동 작업 실행/재시작은 하지 않았다.

## 남은 사용자 조작

사용 중인 StudyEZ 탭의 data-studyez-ai-extension은 1.3.22였다. 새 JSON 수집에는 1.3.23 업데이트가 필요하다. 브라우저 도구가 chrome://extensions 접근을 보안 정책으로 거절하여 확장 관리 화면을 자동 조작하지 않았다. 사이트의 브리지 설치·업데이트를 적용한 뒤 StudyEZ와 ChatGPT 탭을 새로고침해야 한다. 설치·업데이트 완료로 표시하지 않는다.

일반 HTTP 클라이언트의 정적 파일 조회는 403으로 차단되어, 웹 프롬프트 버전 확인에는 사용자의 실제 브라우저를 이용했다. 배포 확인 중 기존 콘텐츠·사용자 학습 기록을 쓰는 검사는 수행하지 않았다.
