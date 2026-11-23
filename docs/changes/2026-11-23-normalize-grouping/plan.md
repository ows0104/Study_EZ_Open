# Main-Quiz /4 정규화: 포인트를 강의 뼈대로 묶어 목표를 짠다 — 구현 계획

## 변경 범위·대상 파일·순서
1. `content/prompts/learning-links/v4/normalize.md`: R1 문단 추가, R2 한 문장 수정.
2. `content/prompts/learning-links/v4/PROVENANCE.md`: 한 문단.
3. `tests/runner/test_root_native_v3.py`: /4 지시문에 R1 문장이 있는지.
4. 재생: 261118_05 `generation/normalize.input.json`·`material/`을 `C:\sez\ng\`에 복사하고
   이 worktree 코드로 `NativeJson(out)('normalize', ctx, material, model)` 한 번(모델 호출 1회, 약 6분).
   이전 CLI 결과·Work 결과와 역할 분포·포인트–목표 대응·관계 kind·답 조각 개념·cue 틀·component 분포를 비교한다.
5. 회귀 검사 → release.md → Draft PR.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner/test_root_native_v3.py -q`: 통과.
- `python -m pytest tests studyez_contracts -q`: 기존과 같다. 알려진 환경 실패는 test_desktop_control 바로가기 하나.
- 재생: intent의 성공 기준을 release.md에 표로 남긴다. 기준에 못 미치면 그대로 적고 지시문을 다시 본다(재생은 최대 2회).

## 위험·복원·승인할 범위
- 위험: 묶은 목표가 넓어져 누락 점검에서 partial이 늘 수 있다. 재생은 normalize만 보므로 확인되지 않는다 → release.md에 남긴다.
- 위험: 지시문 해시 변경으로 진행 중 /4 실행 이어 가기에 `--resume`가 필요하다. 병합·러너 재설치는 러너 담당 세션과 맞춘다.
- 복원: 커밋 되돌리기. 이미 만든 판에는 영향 없다.
- 승인 범위: 사용자 2026-11-23 「CLI normalize도 Work처럼 묶게 고쳐줘」 — 지시문·검사·문서 변경, 재생 1~2회, Draft PR.
  master 병합·러너 재설치·운영 재실행·끝까지 돌리는 비교는 포함하지 않는다.
