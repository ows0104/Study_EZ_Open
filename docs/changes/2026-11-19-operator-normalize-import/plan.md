# Main-Quiz 운영자 제공 normalize 가져오기(operator-stage-result/1)와 261109_02 이어 하기 — 구현 계획

## 변경 범위·대상 파일·순서
1. 새 파일 `runner/operator_stage_results.py`
   - `load(out)`: 생성 폴더 옆 기록을 읽고 검사한다.
   - `entry(out, stage)`: 그 단계 항목과 파일 바이트, 기록 sha를 돌려준다.
2. `runner/root_native_json.py`
   - `NativeJson.file` 앞머리: 항목이 있으면 `_imported(...)`로 간다.
     자리 만들기는 공용으로 쓰고, 파일을 넣은 뒤 check_file로 영수증을 쓴다.
   - `validate_stage`: `operatorImport` 갈래 하나.
3. 검사 `tests/runner/test_operator_stage_results.py`
   - 기록 형식 거절
   - 가져오기 성공: 영수증·usage, 모델 미호출
   - check_file 실패 시 단계 실패
   - sha 불일치
   - validate_stage가 기록·파일 변경을 잡는다
   - 기록이 없으면 모델 호출
4. `runner/CLAUDE.md`에 한 문단.
5. 운영: PR(Draft→Ready 한 번) → 병합 → 러너 재설치. 그 뒤 spec의 261109_02 순서대로 한다.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner/test_operator_stage_results.py -q`: 모두 통과.
- `python -m pytest tests/runner tests/quizbank tests/contracts -q`: 기존과 같다.
  알려진 환경 실패는 test_desktop_control의 바로가기 하나다.
- 운영 확인:
  - job 700 generation/.native/normalize/receipt.json에 operatorImport가 있다.
  - material S1 36쪽이 원본 글이다.
  - 게시되면 root_control.revision이 새 판이다. 실패면 그 단계와 이유를 기록한다.

## 위험·복원·승인할 범위
- 위험: 뒤 단계 GPT 거절. 사용자가 알고 골랐다. 두 번째 거절쯤에서 멈추고 알린다.
- 위험: 웹 결과가 가린 쪽을 45곳 인용한다. 앞 단계(가린 자료)와 섞인다. 가린 쪽을 풀어 뒤 단계 자료와는 맞춘다.
- 복원:
  - 코드는 git revert로 되돌린다. 기록 파일을 지우면 그 실행은 모델을 부른다.
  - 사이드카 보관본은 이름을 되돌리면 된다.
- 승인 범위:
  - 코드 구현·PR·병합·러너 재설치
  - 261109_02의 기록 파일 두 개 변경
  - 운영 DB 쓰기는 job 700 이어 하기 요청 하나(사용자 「이걸로 돌려줘」, 공개판 교체는 11-18 「교체한다」)
  - 모델 지정 파일은 건드리지 않는다.
