# 실제 배포와 실증 진행 — 2026-11-05 KST

정본 실행 공간: `tmp/rp5`. 기존 운영 기준의 정확한 재빌드를 확인한 후 승인된 공통 보호장치만 배포했다.

## 운영 배포

- web / c5263691-6f48-46e2-a9b8-7f2e785a55c3 / succeeded / 후보 859a9f1c6e87eda7f9276e7e0028c594db2ba2bfa1cb158fc6e24f136c9c936f / 사후검사 True
- server / studyez-api-release-1793840010009136700 / succeeded / 후보 89d8541c36f4cd6041b0c5df4a5cd08e3dfe18afc792865e4d2de60088f05c73 / 사후검사 True
- server / studyez-api-release-1793840260420597100 / succeeded / 후보 7c19e7b26102bbdb48e5d4d25297ebba4f62b62b74780d08269790319788ae17 / 사후검사 True

최초 API는 health/auth 통과 후 전송 전에 기존 기능 플래그 누락을 발견했다. 기존 revision의 일반 환경과 대조한 차이는 root enabled 키 하나뿐이었고, 기존 true 설정을 복원한 새 후보를 배포했다. 최종 API 사후 검사는 실제 revision에서 이 true 값도 검증한다. DB/문항/학습 데이터 변경은 없다.

## 실제 한 건

- 강의: 감염과 면역 / 261102_03 / 감염병의 진단(김택수).
- StudyEZ의 뿌리 학습 자동전송 버튼을 10:00 KST경 1회 실행. ChatGPT 탭에 직접 접속하지 않음.
- generation: 45ba26d191dc468a800360a366c39a55 / job544. source-assessment/2, privatePilot=true.
- 원본: 올해 필기 21,953,699바이트, 2026-S3-족보-김택수.pdf 455,091바이트. SHA와 입력 지문은 probes에 보관.
- 10:01 KST 읽기 확인: dispatched=true, received=false, held/ChatGPT 응답 대기. 실제 회수/검수/게시/학습은 아직 완료로 세지 않는다.
- 원래 콜린성 은행은 build c7fbb80dee4540a1 / ready / 학생 공개 상태를 유지한다. 시험 강의의 기존 Main-Quiz 행은 없다.

## 검증 기록

동일 source421cc3b5904bf3fa9a341d0d476d88ea7c0d5f117674691e5c6f5f497188bafc / plana3b2cd6cf6ae97223a0ee82b55fb5877c26cb00ffcd51d8831eea1e0991ece69에서 contracts116, generator497, runner32, server19파일, web 실제 로컬 통합1건 및 typecheck/build 통과. 웹 artifact64b1557306e7aa5200367787ce1493f4d6a640d4940842b9017eaf9fcb329524. 운영 HTML/ZIP 3origin과 JS/CSS38개 파일 일치. 로컬 실행기/생성기/모델 어댑터가 검증 사본과 같은 파일임도 확인했다.

## 10:15 KST 이후 확인

아직 received=false / held / ChatGPT 응답 대기이며 검수·게시·학습 화면 실증은 미완료다. StudyEZ HTML DOM의 설치 브리지 버전은1.3.21이며, 실제 로컬 러너의 Anaconda Python에서 새 생성기/공유계약(/2)/PDF 모듈 import가 성공했다. 새 대화의 제목만 확인했으며 ChatGPT 본문에는 접속하지 않았다. 사용자에게 생성 중/오류 또는 확인 요청/응답 파일 완료 중 어느 상태인지 질문했고 답변을 기다린다. 재전송·상한 초기화·임의 내용 수정은 하지 않았다.

확장 관리 페이지는 브라우저 도구 정책상 차단되어 접근하지 않았다. 이를 우회하지 않고 StudyEZ 자체 DOM에 공개된 버전 속성을 읽어 연결 버전만 확인했다. 직접 ChatGPT를 확인하지 않는 사용자 조건 아래 대화 내부의 상태를 단정하지 않는다.

## 12:57 KST 현재 — 배포 완료, 실제 학습 실증 미완료

사용자 응답·파일 생성 완료 확인 후 실제 자동회수를 확인했다. 원문76문항, 필기66쪽·족보16쪽, 웹 응답 SHA561828550e9ba8815a7dc2636ce051a41c5ac74613b4f0b3ed8c59d2632c3728. ChatGPT 직접 조작/수동 업로드/새 웹 전송은 없었다.

실제 초기 지도에서 선행 관계종류/끝점 오류가 발견돼 공통 초기지도 교정 경로를 구현·검증·배포했다. 현재 API studyez-api-release-1793844015758744700, 후보06fea6c5d6e4547f985c43b7ba7d519ac73e60b9cdd16c3b1bffb36d4607742c, 실제 revision/기존 기능설정/health/auth 사후 확인 통과. 웹은 c5263691-6f48-46e2-a9b8-7f2e785a55c3를 유지한다. 해당 수정은 ../2026-11-05-root-initial-map-repair/deployment.md에 기록했다.

완료된 normalize 모델 출력과 원래 실패 이력을 재검증하여 재사용하고, 첫 generate는 같은 총3회 중1회를 소비했다. 첫 generate가40분 제한에 걸렸으며, 엄격한 동일세션1회 계속을 contracts125/runner72 검사·리뷰 후 실행했으나 추가40분도 완료하지 못했다. 원래 ledger/input/runtime/원본/84개 자료 파일과 사본을 보존했고, 원래 실패 서버 job544는 재등록하지 않았다. 원격 published=false, 결과/학습 문항 없음. 기존69문항 콜린성 은행은 같은 build c7fbb80dee4540a1로 보존됐다.

실제 최종 UI 화면은 live-blocked.png, 호출/보존 근거와 남은 공통 관측 문제는 ../2026-11-05-root-authoring-continuation/live.md다. 자동수신 성공과 배포 성공을 실제 문항 검수·게시·학습 성공으로 세지 않는다. 지연 세부 원인은 아직 미확정이며 시간 초과만 반복해 해결됐다고 표시하지 않는다.
