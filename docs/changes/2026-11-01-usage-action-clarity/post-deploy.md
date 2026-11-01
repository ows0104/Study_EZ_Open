# 운영 반영 및 사후 확인

2026-11-01 KST 운영 반영 완료.

- DB: 17:55 public.asset_grab.request_stats JSON NOT NULL DEFAULT '{}' 추가. 같은 트랜잭션에서 기존 316행의 count 합계·최초/최종 시각과 RLS 보존 확인. schema-receipt.json 참조. 기존 학습/대화/권한 변경 없음.
- API: studyez-api-release-1793523763317944700. 새 revision Ready 및 실제 100% 트래픽을 배포 도구가 확인. 최신 사후 검사는 18:06 KST healthy, 인증 경계/공개 웹 smoke exit 0.
- 웹: Cloudflare Pages production a0edf1f4-981e-4568-8b5a-7c2ad1e54617. 최종 고정 후보 bcb69fa47fdf87fd955cf63a7fab76c4b2bb52c567f3fa40485d1486cfd36c3d, 업로드 ID와 실제 production 목록 일치. 18:09 KST 사후 health/smoke 통과.
- 실제 https://studyez.kr/admin/usage 관리자 화면에서 새 카탈로그 열과 대상 계정을 읽기 전용 확인했다. 최근 18강의 모두 개인 예습 링크 저장, 링크/퀴즈 기록 없음, 파일 목적 미상이며 직접 다운로드로 잘못 표시하지 않는다. 전체 기간의 기존 예습 129문항·복습 카드 98문항·공용 링크 5강의도 그대로 표시된다. 과거 만들기 시도를 추정 생성하지 않았다.
- 신규 행동 등록 회귀 검사: 16 PASS. 실제 가상 브라우저에서 서버에 새 테스트 행동을 추가하자 웹 코드를 고치지 않아도 요약·상세에 표시됨을 확인했다. 개발 지침과 컴포넌트 안내에 동시 기록/등록/검사 의무를 연결했다.
- 생산 UI 증거: runs/_development/2026-11-01-usage-action-clarity/production-ui.json 및 usage-production.png. 개인 대화 URL/본문을 수집하거나 노출하지 않았다. 운영 계정에 가짜 활동을 생성하지 않았다.

## 경로 문제 및 실패 보존
앞선 서버 업로드는 Windows 긴 경로와 임시 호출 전달 문제로 실제 버전 생성 전에 실패했다. 기존 서비스/트래픽 유지 확인 후 동일 후보의 DOS 짧은 경로가 같은 디렉터리이고 전체 manifest가 같음을 검증해 공식 gcloud PowerShell 실행기로 전달했다. 실패 영수증은 삭제하지 않았다. API 완료 뒤 최초 smoke는 실행 파일의 상대 경로 때문에 시작되지 않아 127로 기록됐으며, 배포를 반복하지 않고 문서화된 postcheck만 올바른 작업 경로에서 재실행해 통과했다. 웹 첫 시도는 Wrangler 임시 경로의 EISDIR 처리에서 업로드 전에 중단됐고 production ID 유지 확인 후 같은 산출물·작업 디렉터리의 짧은 경로 표기로 완료했다. 최종 API/웹 모두 성공 영수증과 최신 사후 검사 통과를 확인했다.

검증과 배포 정본은 격리 사본의 state.json이다. 공유 폴더에는 다른 작업의 프롬프트 수정이 있어 직접 배포하지 않았으며, 이번 작업 파일과 결과만 주 작업 폴더에 동기화했다.
