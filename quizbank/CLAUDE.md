# quizbank 작업 안내

관리자가 만든 ChatGPT 답을 서버에서 쓸 문제은행으로 정리한다.
최초 문항 생성 프롬프트는 `../web/src/bank/bankPrompt.md`다.

| 단계 | 코드 | 역할 |
|---|---|---|
| 실행 | `run.py` | 정리·검증·검토·슬라이드 연결 |
| 정리 | `organize.py` | 응답을 `schema.py` 형태로 옮김 |
| 검증 | `validate.py` | 구조 확인·오류 문항 제거 |
| 외부지식 검토 | `review.py` | 정답 검토 결과를 표시 |
| 근거 이미지 | `slides.py` | 인용한 PDF 쪽을 PNG로 생성 |

실행: `python -m quizbank.run --help`.
검사: `python -m pytest tests/quizbank`.
운영 실행·업로드는 `runner/bank.py`가 맡는다.

## 유지할 계약

- `validate_dropping`은 문항 ID에 귀속되는 오류만 해당 문항 제거로 처리한다.
- 제거된 문항의 선행 관계를 정리하고 다시 검사한다. 전역 구조 오류는 전체를 막는다.
- 제거 원문·이유는 `validation.dropped`, 제거 전 은행은 `bank.raw.json`에 남긴다.
- 외부지식 검토는 정답을 몰래 바꾸지 않고 표시로 전달한다.
- 출처 충돌은 합친 문항과 충돌 기록으로 보존한다.
- 자료 밖 내용은 `EXT`·`external_knowledge`로 표시한다.
- 과거 형식도 읽을 수 있어야 한다. 프롬프트 변경만으로 옛 은행을 무효화하지 않는다.
- 러너·quizgen을 import하지 않는다. 러너가 하위 프로세스로 실행한다.

결정 배경은 [변경 전 기록](../docs/archive/2026-10-06-originals/quizbank/CLAUDE.md)에 있다.
