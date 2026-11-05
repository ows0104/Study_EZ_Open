# 실제 배포 결과

2026-11-03 KST, 요청한 API와 웹 운영 배포 및 read-only 사후 검사를 완료했다.

- API revision: `studyez-api-release-1793693961835976300`. 검증한 새 revision 준비 뒤 실제 트래픽 전환과 health/auth/CORS/root 경로·표 접근 사후 검사 성공.
- API candidate: `190d40c2b86f59ded7d614f1b981966731b8f8200cf7816491ba46140d2d0c2b`.
- Pages production ID: `414a00af-be38-4dad-81f4-13c24bbb96ff`. 공개 HTTP·인증 경계·root 경로 사후 검사 성공. 운영 주소 https://studyez.kr.
- Web candidate: `d7506d8c7c15038c1d0abf9f71cf33052962a9e080ebe55a0475e350dd2d9770`.
- root_content/control/session/event/generation 5개 표 생성과 RLS 활성화 확인. 기존 은행·학습 데이터 변경 마이그레이션 없음. 전체 기능 설정은 true, 생성 콘텐츠 기본 공개 대상은 요청 관리자 개인.
- 실제 Study EZ의 콜린성 약리학(1) 뿌리 화면에서 배포된 자동전송 입력 폼과 브리지 1.3.20 연결을 확인했다. 기존 러너 agent PID 41304 실행 확인. 기존 69문항 build `c7fbb80dee4540a1`, ready 유지.

소스·후보·승인·배포 영수증·smoke 근거의 정본은 `tmp/root-web/docs/changes/2026-11-03-root-web-deployment/state.json`과 해당 사본의 runs/_development 디렉터리다. 원래 작업 폴더의 별개 미커밋 변경은 제외했고 커밋/push하지 않았다.

## 실제 예시 진행 상태

콜린성 약리학(1)의 수신 Concept map 파일을 Study EZ 입력에 불러오려는 동작이 자동 승인 심사에서 거절되었다. 사유: 특정 실제 파일과 운영 대상에 대한 전송 승인 근거 부족. 우회 전송이나 ChatGPT 직접 접속은 하지 않았다.

기존 PDF/족보와 `concept-tree-2026-11-02.txt`, `exam-points-2026-11-02.txt`를 운영 Study EZ 본인 관리자 계정 및 ChatGPT 자동전송에 사용하고 개인 시범 1건으로 게시하는 범위를 사용자에게 명시해 확인을 요청했다. 실제 출제·수신·검수·게시 완료로 보고하지 않는다. 답변 후 같은 범위에서 이어간다.

후속 사용자 답변: 위 자료·운영 StudyEZ 관리자 계정·ChatGPT 자동전송·기존 69문항 보존·개인 시범 범위를 명시한 질문에 “해당 실제 자료로 1건 실행”을 선택했다. 이 구체적 승인을 적용해 예시를 재개하며 같은 범위의 허락을 반복 요청하지 않는다.

재개 후 브라우저의 Concept map 파일 선택 호출은 성공했다. 다음 입력/상태 확인 호출은 자동 승인 검토 서비스의 `Selected model is at capacity`로 실행되지 않았다. 즉시 재확인 및 30초 후 재확인을 포함해 3회 같은 검토 서비스 실패가 반복됐다. 이는 위험 판정 거절이 아니라 검토 서비스 가용성 오류다. 다른 전송 경로나 직접 ChatGPT 접속으로 우회하지 않았다. 자동전송 버튼 클릭·실제 웹 출제 요청은 아직 실행하지 못했으며, 자료 사용 승인 자체는 유지한다. 서비스 복구 후 포인트/범위 입력 및 단회 자동전송부터 이어간다.
