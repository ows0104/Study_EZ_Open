# Main-Quiz /4 정규화: 성분을 따로 채점할 사실 하나씩 — 구현 계획

## 변경 범위·대상 파일·순서

1. `content/prompts/learning-links/v4/normalize.md` 새 파일(R1). `v4/PROVENANCE.md`에 한 줄.
2. `runner/root_native_json.py`: `task_for(stage, ctx=None)`, `NativeJson.file`이 ctx를 넘긴다(R2).
3. `tests/runner/test_root_native_v3.py`: /4만 v4 지시문, /2·/3·버전 없음은 extract-v2.md.
4. 재생: 261113_01의 `normalize.input.json`으로 normalize(+필요하면 brief-fix)와 첫 누락 점검을
   새 지시문으로 돌린다. 출력은 `C:\Users\ows01\rpl\v4n`(git 밖). 필기·족보가 OpenAI(Codex CLI)로 다시 전송된다(사용자 승인).

## 검사 명령과 성공 조건

```powershell
C:/Users/ows01/anaconda3/python.exe -m pytest tests studyez_contracts -q -p no:cacheprovider
```

- 성공: 새 검사 통과, 회귀 실패 0. 단 `tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`은
  이 PC의 바로가기 설치기 환경 결함으로 pristine master에서도 실패한다(대시보드 2026-11-08 기록).

## 위험·복원·승인할 범위

- 위험: 모델이 지시를 따르지 않거나 component를 지나치게 잘게 나눌 수 있다. 재생으로 한 번 확인한다.
- 복원: 지시문 파일과 `task_for` 분기를 되돌리면 /4도 extract-v2.md로 돌아간다.
- 승인 범위: 위 파일들, 재생 1회. 러너 재설치·운영 재실행·master 병합은 별도.
