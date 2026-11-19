# Main-Quiz 운영자 제공 normalize 가져오기(operator-stage-result/1)와 261109_02 이어 하기 — 설계

## 요구사항과 수용 기준
- R1 기록 파일 `runs/_root-generation/<generation id>/operator-stage-results.json`
  - 놓는 곳은 생성 폴더 옆이다. operator-exclusions.json·operator-resumes.json과 같다.
  - 모양: `{"version":1,"stages":{"normalize":{"file":"<같은 폴더의 파일 이름>","sha256":"<64 hex>","producer":"…","reason":"…","approval":"…","at":"…"}}}`
  - 받는 단계는 `normalize` 하나다. 다른 이름, 빈 칸, 폴더 밖 경로, sha 불일치는 그 단계를 멈춘다(ValueError). 모델은 부르지 않는다.
- R2 NativeJson.file에서 기록에 그 단계가 있으면 모델을 부르지 않고 그 파일을 받는다.
  - 단계 자리(.native/<stage>/work)는 모델 단계와 똑같이 만든다: input.json·acceptance.schema.json·task.md·check_result.py·material 사본.
  - 파일 바이트를 work/result.json에 그대로 둔다.
  - `check_file(stage, work)`가 통과해야 받는다. 실패하면 되돌려 보내지 않고 그 단계가 실패한다. 웹 결과는 사람이 다시 받아 와야 한다.
- R3 영수증 증거(proof)
  - 모델 단계와 같은 칸(policy·stage·inputHash·schemaHash·model·materialHashes·protectedFiles·adapterSha256·outputSha256·rawHash)을 가진다.
  - 여기에 `operatorImport`(policy operator-stage-result/1, 기록 항목 전체, 기록 파일 sha256)를 더한다.
  - `model`은 이 실행의 모델 이름이다. 모델 지정 재개 규칙(_retire_other_model)이 이 단계를 다른 모델 것으로 오인하지 않게 하려는 것이다.
  - 실제 출처는 `operatorImport.entry.producer`다.
  - provider.json·nativeSessionId·providerHash는 없다.
  - usage 정보는 `{"usage":{},"cost_usd":0,"duration_ms":0,"models":[],"operatorImport":…}`이다. 모델이 쓴 토큰·시간은 없다.
- R4 validate_stage
  - `operatorImport`가 있는 영수증은 provider 응답 대신 다음을 확인한다:
    - 기록 파일이 그대로 있고 그 sha256과 항목이 같다.
    - 가리킨 파일의 sha256이 outputSha256과 같다.
    - output.json이 그 바이트다.
    - usage가 R3 값 그대로다.
  - 그 밖의 검사(입력·스키마·자료·raw)는 모델 단계와 같다.
- R5 기록이 없거나 그 단계가 없으면 지금 동작과 바이트 단위로 같다. 이미 완료된 단계는 기록이 있어도 다시 받지 않는다. Stages.run이 먼저 재사용한다.

## 책임·입출력 계약·오류 상태
- 기록 읽기·검사는 새 `runner/operator_stage_results.py`가 맡는다. quizbank는 runner를 import하지 않는다.
- 실패는 ValueError로 그 단계 failed다(Stages.run 규칙). 운영자는 기록이나 파일을 고친 뒤 이어 하기(resume) 이유를 적는다.
- 서버·계약·DB 변경 없음. 서버는 manifest의 단계 해시만 본다.

## 호환성과 데이터 보존
- 기존 실행·영수증·검사는 바뀌지 않는다(R5).
- 261109_02 운영 순서:
  - `runs/page-exclusions.json`의 이 강의 행을 지우고, job 700의 사이드카 둘을 `*.withheld-pages.released.json`으로 옮긴다.
    - 행만 두고 사이드카를 옮기면 freeze가 「이미 자료를 만든 실행」이라고 막는다.
    - 이유·승인은 실행 폴더 `withheld-release.json`에 남긴다.
  - 앞 단계(front)는 이미 완료돼 다시 돌지 않는다. 가린 자료로 만든 그 결과가 그대로 생성 packet이 된다.
  - 생성기 material은 이어 하기 때 원본으로 다시 만들어진다(v4.run이 prepare를 매번 부른다).
- 그다음 operator-stage-results.json과 웹 결과 파일을 두고, job 700 이어 하기 요청 하나를 넣는다.
  - 같은 requestId로 resume=True와 이유를 보낸다.
  - packet의 replacePublished가 그대로라, 게시되면 auto-2bcdcf1f를 교체한다. 사용자의 11-18 「교체한다」와 같은 범위다.
