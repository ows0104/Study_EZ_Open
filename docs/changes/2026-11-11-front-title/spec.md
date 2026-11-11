# Main-Quiz 앞 단계 'Different title' 보류 수정 — 설계

## 요구사항과 수용 기준
- `runner/root_front.py` `Front.accept`: 결과를 읽고 title이 다르면 원문 보존 → title 교체 → 저장 → 기존 `validate`.
- 교체된 파일의 해시가 state의 fileSha256·textSha256이 되고, derive·서버 재유도는 교체된 파일로 진행한다.
- 남은 `validate`의 title 검사는 안전망으로 두고 메시지에 두 값을 보인다.

## 책임·입출력 계약·오류 상태
- 입력 보존 검사(call 안)는 교체 전에 끝난다. 원문 바이트는 `model-concept-map.json`/`model-exam-points.json`.
- 검사 실패: failure.json(type·message), failure.txt, state.json {status: failed, inputHashes}. 이어 하기는 기존대로 `--resume <이유>`.

## 호환성과 데이터 보존
- 이미 완료된 단계 폴더는 그대로 재사용한다(새 키 modelTitle은 선택).
- 서버·DB·프롬프트·스키마 변경 없음. 모델 원문을 지우지 않는다.
