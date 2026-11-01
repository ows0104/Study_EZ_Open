# StudyEZ 전체 개발·유지보수 루프

이 절차는 이번 리팩토링뿐 아니라 StudyEZ의 이후 기능 추가·수정·장애 대응에 적용한다.
아이디어나 장애에서 새 작업을 시작하고, 사람의 구현 승인과 중요한 운영 승인을 거친다.

검사 근거 버전 2, 고정 배포 후보, 실제 배포/사후 검사와 사건 종료 명령은
[배포 후보·사후 확인·사건 종료](release-and-incidents.md)를 따른다.
2026-10-26 보강 작업의 구현 승인은 실제 운영 배포를 포함하지 않는다.

## 매 작업의 흐름

1. **Intent:** 사용자와 문제·원하는 효과·범위를 구체화해 작업 폴더의 `intent.md`에 쓴다.
2. **Spec:** AI가 계약·동작·수용 기준·데이터 보존을 `spec.md`에 쓴다.
3. **Implementation Plan:** 변경 파일·순서·검사·복원을 `plan.md`로 제안하고 사람에게 해당 범위를 승인받는다.
4. **Build:** 승인받은 Implementation Plan의 범위만 구현한다.
5. **Test:** AI가 실제 검사를 실행하고 실패 원인을 고쳐 재검증한다. 실패·미실행·기존 결함을 구분한다.
6. **Review:** 코드 리뷰와 `release.md`를 준비한다.
7. **Deploy:** 중요 운영 변경을 사람에게 승인받고 배포한다. 배포 후 확인한다.
8. **Maintain:** 관측·제보를 분석하고 새로운 작업의 intent/spec/plan으로 연결한다. 같은 사건을 중복 생성하지 않는다.

단계 명칭은 위 영어 용어를 사용한다. `plan.md`는 Implementation Plan이며 Intent를 뜻하는 Plan과 혼용하지 않는다.
이 용어 정리는 기존 승인·검사·출시 근거 요건이나 도구의 `--phase build/release/deploy` 값을 바꾸지 않는다.

작업 폴더는 `docs/changes/<id>/`다. 전역 문서 한 개에 모든 이력을 누적하지 않는다.
작은 수정의 문서도 짧게 쓰되, 승인 범위·검사·기록 보존 조건은 생략하지 않는다.

## 시작과 승인 확인

저장소 루트에서 실행한다. `python`은 프로젝트 의존성이 있는 런타임을 사용한다.

```powershell
python scripts/development.py new 2026-10-26-example --title "기능 변경" --area site --checks web regression
```

AI는 생성된 intent/spec/plan의 `<TODO>`를 실제 내용으로 채운다. `state.json`의 required_checks는
계획의 검증 목록과 맞춘다. 승인 후 사용자의 실제 발언과 승인 범위를 기록한다.

```powershell
python scripts/development.py approve 2026-10-26-example --phase build --evidence "사용자 승인 발언과 채팅/시각" --scope "승인된 파일·기능·로컬 구현 범위"
python scripts/development.py check 2026-10-26-example --phase build
```

기록 명령은 승인 요청을 대신하지 않는다. AI가 스스로 승인을 만들거나 제보 문구를 사용자 승인으로
취급하면 안 된다. intent/spec/plan이 바뀌면 해시가 달라져 기존 구현 승인이 유효하지 않게 된다.
다만 오탈자 등의 정리가 실질 범위를 바꾸지 않았다면 이미 받은 승인의 적용 여부를 판단해 근거와 함께
갱신한다. 기존에 승인된 작업에 대해 불필요하게 같은 허락을 반복 요청하지 않는다.

## 실제 검사와 리뷰

```powershell
python scripts/development.py verify 2026-10-26-example --check regression -- python -m pytest tests/contracts -q
python scripts/development.py review 2026-10-26-example --summary "검토한 경계·발견/수정한 문제·남은 위험과 검토 근거"
python scripts/development.py check 2026-10-26-example --phase release
```

`verify`는 shell 없이 지정한 실제 검사 명령을 실행하고 종료 코드·영역별 코드/입력·계획 지문·로그를 남긴다.
로그는 `runs/_development/<id>/`, 요약은 작업의 state.json에 있다. 관련 코드나 설계가 달라지면 이전 검사는
배포 근거로 사용할 수 없다. 같은 체크의 최근 실패가 예전 성공으로 가려지지 않는다.
통과 코드만으로 충분하지 않다. 테스트가 실제 실행되었는지, 필요한 범위인지 AI가 로그와 수를 확인한다.
테스트 파일별 격리가 필요한 서버는 기존 `server/.venv/Scripts/python.exe -m tests <필터>`를 따른다.

재검증은 변경된 범위와 연결된 계약을 중심으로 한다. 같은 실패를 반복하면서 무제한 실행하지 않고,
진전이 없으면 근거·시도·남은 문제를 적어 사용자 판단을 받는다. 출제의 기존 검수 상한은 별도 유지한다.

## 배포 준비와 중요 승인

release.md에 실제 대상 revision, 테스트 결과, 코드 리뷰, DB 변경 유무, 배포 순서, 관측과 롤백을 쓴다.
검사 결과에 대응하는 고정 후보를 prepare한 뒤 사람 승인과 deploy 승인을 기록하고 `check --phase deploy`로 확인한다.
development.py 자체가 배포를 실행하지는 않는다. publish-web과 server/deploy.ps1은 실제 운영 명령이다.
운영 DB·권한·공개 범위·학습 기록·내용 교체, 운영 배포, 파괴적 정리는 구체적 범위의 중요 승인 대상이다.
이미 받은 사용자의 명시적 승인이 해당 변경을 포함하면 그 근거를 적용한다.

코드/설계/후보/배포 계획이 바뀌면 기존 배포 승인은 재사용되지 않는다. 이 검사는 사고 방지용 작업 도구이며
Git 서버나 클라우드의 접근 통제를 대체하지 않는다. 직접 배포 명령을 실행할 수 있는 권한 자체를 막지는 않는다.
운영 배포 명령에서도 이 절차를 확인하고, 배포 후 read-only 확인 결과를 release.md에 남긴다.

## Maintain → 새 개발 작업

기존 매시간 “Study EZ 오류·사이트 피드백 검토” 자동화를 유지하며 다음 관측을 추가한다.

```powershell
python scripts/maintenance.py
```

- 공개 웹의 응답과 API `/api/health`를 관측한다. 인증정보와 응답 본문은 저장하지 않는다.
- 설정은 `monitor.json`, 상태는 `runs/_maintenance/state.json`이다.
- 두 번 연속 비정상/관측 실패 시 사건별 개발 폴더와 intent 초안을 만든다. 같은 사건에는 하나만 만든다.
- `unknown`은 네트워크 등 관측 실패이며 서비스 장애로 단정하지 않는다. 정상 관측 복구는 별도 이벤트다.
- 기존 피드백 ledger를 기술 관측으로 대체하지 않는다. 같은 문제면 기존 change ID와 연결한다.
- AI는 새 사건을 읽고 관련 로그/코드만 조사해 spec/plan을 작성한다. 새 수정의 구현 승인은 사람에게 받는다.
- 변경 없는 정상 상태·동일 대기 사항은 알리지 않는다. 새 사건·복구·의미 있는 실패·판단 필요 때만 보고한다.
- 잠금이 남으면 중복 실행하지 않는다. 실제 실행 프로세스가 없는지 확인한 뒤 잠금 복구를 검토한다.

현재 탐지는 웹/API의 가용성에 한정한다. 브라우저 동작, 로그인 후 학습 저장, DB 건강, 큐 지연,
로컬 러너 생존까지 정상임을 뜻하지 않는다. 이러한 관측은 권한과 기대 실행 시간을 확정한 후 확장한다.
러너가 의도적으로 꺼져 있는 상태를 장애로 처리하지 않는다.

로컬 자동화에는 PC와 앱의 실행이 필요하다. 실행되지 못한 시간대를 연속 관측했다고 간주하지 않는다.
[공식 실행 조건](https://learn.chatgpt.com/docs/automations?surface=app).

## 읽기 범위

작업 지도에서 site/generation/integration/contracts/spotter/operations를 고르고 해당 코드·검사만 읽는다.
공유 계약을 바꿀 때는 생산자와 소비자를 함께 검사한다. 생성 자료·과거 작업은 경로를 지정해 필요할 때만 읽는다.
신규 작업을 별도 채팅으로 자동 생성하지 않는다. 작업은 우선 저장소의 작업 폴더이며 채팅 생성은 사용자 요청에 따른다.
