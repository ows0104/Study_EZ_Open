# 운영 배포·실제 화면 확인 완료

2026-11-01 KST 사용자 “그럼 운영 사이트에도 배포해줘.” 승인 범위로 게시했다.

- 실제 Pages production: dfebb98a-eb9a-4bb6-afb2-942d1bcaa7f7.
- 검증된 고정 후보: 4b13c8c9976d9823668def214b293ac03e2ff2f5fa86bf83fde282542ffdbe91.
- 이전 운영 0ca1ec7b-bdc2-4775-8916-4b1dca98563d를 정확히 재현한 후 이번 아홉 파일만 적용했다. 기존 교수 재확인·이용현황 개선과 나머지 운영 소스를 보존했다.
- 회귀 13개, 격리 브라우저 11가지 동작, 공용 계약 6개 및 TypeScript/production build 통과. 임시 디렉터리 오류 등 초기 미완료 검사는 보존하고 최종 전체 실행 통과를 확인했다.
- 업로드 직전 기준 production ID를 검사했고, 업로드 URL·실제 ID·최신 production 목록의 일치를 확인했다.
- 최신 postcheck: health healthy, API health/CORS/인증 경계 정상, 권한 있는 읽기 전용 강의 원본 조회 정상. 운영 도메인·Pages·고유 게시 주소에서 36개씩 총 108개 HTML/JS/CSS/정본 프롬프트 SHA256이 고정 후보와 일치했다.
- computer-use 스킬의 @oai/sky로 기존 로그인된 Chrome에 확인용 새 탭을 열어 https://studyez.kr/study에 접속했다. 별도 로그인이나 계정/자료/평가 변경 없이 실제 접근성 화면에서 블록 콤보 값이 “감염과 면역”이고 78 / 78 강의, 2026-11-02 예정 강의 및 “준비 전” 표시를 확인했다. 블록 선택을 수동으로 바꾸지 않은 최초 진입 상태다. 기존 캘린더에서도 일요일이 11월 2~6일 주간으로 나타남을 확인했다.
- 서버/API 배포, DB·PDF·문항·학습 기록·개인 설정 변경과 Git push는 없었다. 다른 작업의 미완료 소스를 배포하지 않았다.

정본: output/releases/block-auto-deploy/docs/changes/2026-11-01-block-auto-deploy/state.json 및 같은 소스의 runs/_development/2026-11-01-block-auto-deploy/. 공유 작업 폴더의 state와 로그는 사본이며 verification_root가 정본 경로다.

복원 대상은 직전 운영 0ca1ec7b-bdc2-4775-8916-4b1dca98563d다. 정적 웹만 변경했으므로 DB/API/자료 복원은 필요 없다.
