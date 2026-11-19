# Main-Quiz 운영자 제공 normalize 가져오기(operator-stage-result/1)와 261109_02 이어 하기 — 배포 준비

## 코드 리뷰·검증 결과
- `tests/runner/test_operator_stage_results.py`: 12 통과.
  - 가져오기와 모델 미호출
  - 기록·파일 변경과 기록 삭제를 재검증이 잡는다
  - 검사 실패와 한글 깨짐은 그 단계 실패
  - 기록 형식 5종
  - 기록이 없을 때는 지금과 같다
- 실데이터 마른 확인(`C:\sez\rp\i700_check.py`, job 700 사본, 모델 호출 없음):
  - 가리지 않은 PDF로 다시 만든 normalize 입력 지문이 job 700 원장 값과 같다.
  - S1 36쪽이 원본 글이다.
  - 웹 결과 `result_바실루스포함_깨짐수정.json`을 가져오면 검사를 통과한다(개념 196·목표 108·포인트 83, 사용량 0).
- 전체 묶음(`tests/runner tests/quizbank tests/contracts`, 11-19 로컬): 2434 통과·1 건너뜀·1 실패.
  실패는 알려진 환경 실패 `test_desktop_control::test_shortcut_installer_supports_korean_filename_in_windows_powershell`이다(11-18 기록과 같음).
- `development.py verify --check regression`: 새 검사와 native·v3·Claude 공급자·콘텐츠 제한 검사 묶음, 종료 0.
- 리뷰에서 본 경계:
  - 모델 단계의 영수증과 검사는 그대로다. provider 갈래는 들여쓰기만 바뀌었다.
  - 가져온 단계에는 모델 세션 증거를 만들지 않는다.
  - quizbank는 runner를 import하지 않는다.

## 배포 대상 버전·순서·데이터 변경
- 대상은 이 PR의 병합 커밋이다. 서버·웹·DB 변경은 없다. 러너는 `.runtime/main-quiz-<sha12>`로 새로 설치한다.
- 그 뒤 운영 데이터 순서(261109_02):
  1. `runs/page-exclusions.json`에서 `감염과 면역/261109_02` 행을 지운다.
  2. job 700 실행 폴더의 `source-0.pdf.withheld-pages.json`·`source-1.pdf.withheld-pages.json`을 `*.withheld-pages.released.json`으로 옮긴다.
     이유는 `withheld-release.json`에 적는다.
  3. `operator-stage-results.json`과 `operator-normalize.json`(웹 결과 바이트 그대로)을 실행 폴더에 둔다.
  4. job 700 이어 하기 요청 하나를 넣는다. 같은 requestId로 resume=True와 이유를 보낸다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인:
  - 새 에이전트의 PYTHONPATH가 새 설치본이다.
  - `generation/.native/normalize/receipt.json`에 operatorImport가 있다.
  - `generation/material/S1.md` 36쪽이 원본이다.
  - 게시되면 root_control.revision이 새 판이다.
- 롤백: 코드는 git revert로 되돌린다. 기록 파일을 지우면 모델 호출로 돌아간다. 사이드카는 이름을 되돌린다.
- 승인: 11-19 사용자 「이걸로 돌려줘」 「가져오기 + 뒤 단계 GPT」 「가린 쪽 풀기」, 11-18 「교체한다」. 모델 지정 파일은 쓰지 않는다.
