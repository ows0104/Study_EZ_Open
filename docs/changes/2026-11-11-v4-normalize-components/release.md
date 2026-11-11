# Main-Quiz /4 정규화: 성분을 따로 채점할 사실 하나씩 — 배포 준비

사용자 2026-11-11 「계획 승인」. 브랜치 `claude/v4-normalize-components`, 기준 master `c5e43715`.

## 코드 리뷰·검증 결과

### 바뀐 것
- `content/prompts/learning-links/v4/normalize.md`(새 파일, R1), `v4/PROVENANCE.md` 한 문단
- `runner/root_native_json.py`: `task_for(stage, ctx=None)`. 단계 `normalize`이고 `_pipeline_version == root-generation/4`일 때만 v4 지시문. `NativeJson.file`이 ctx를 넘긴다.
- `tests/runner/test_root_native_v3.py`: /4만 v4 지시문, /2·/3·버전 없음은 `extract-v2.md`

### 검사
- `pytest tests studyez_contracts`: 2778 통과, 4 건너뜀. 제외 1개(`test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`)는 이 PC 환경 결함으로 master에서도 실패한다.
- 검사 실행이 `web/public/bank-prompt.json` 줄바꿈을 다시 써서 `git restore`로 되돌렸다(기존 현상).

### 재생: 261113_01 저장 입력, 새 지시문 (2026-11-11, 출력 `C:\Users\ows01\rpl\v4n`, git 밖)

같은 `normalize.input.json`, 같은 첫 은행 92문항(첫 누락 점검 입력의 `questions`)으로 normalize → brief-fix(구조 지적 1건: T005 관계 누락) → 첫 누락 점검 2묶음. 모델 호출 4회, 15.3분(5.8·3.2·2.7·3.6분).

| | 이전 실행(extract-v2.md) | 새 지시문 |
|---|---|---|
| 방향 수 | 140 (포인트 D 94, 지도 관계 DM 46) | 98 (D 94, 지도 관계 BD 4) |
| 방향당 component | 140개 모두 1개 | 1개 38, 2개 45, 3개 12, 4개 1, 5개 2 (합계 178) |
| 이름만 끼운 관계 cue | 37 | 0 |
| 첫 점검 missing 방향 | 112 / 140 | 68 / 98 |
| 첫 은행이 답한 component | — (문장 통째라 셀 수 없음) | 178 중 99 |

- missing 68개 중 39개는 일부 component를 이미 답한다. 문항 추가 단계(v4 add)는 빠진 component만 받으므로(`missing_component_ids`),
  추가는 문장 통째(이전 112건)가 아니라 빠진 component 79개 단위가 된다.
- 남은 빠진 component는 대체로 첫 은행이 실제로 묻지 않은 사실이다(예: D025 「오염된 물·수건·기구 접촉」, D060 「고열·심한 권태감 후 발진」, D052 「DNA-dependent RNA polymerase·초기 전사인자」를 발문에 줌).
- 해석상 주의 문구가 든 component는 178개 중 13개 남았다(예: D049 「모든 Poxviridae의 숙주·전파·중증도가 같지는 않음」, D033 「항균제·스테로이드 일률 사용하지 않음」). 줄었지만 없어지지는 않았다.
- 한계: 표본 한 번이다. 추가·검토·수정까지 끝까지 돌린 것은 아니므로 최종 문항 수와 시간은 확인하지 않았다.

## 배포 대상 버전·순서·데이터 변경

- 데이터·DB·서버 API 변경 없음. 생성기(러너) 코드와 지시문만이다.
- master 병합은 사용자 결정. 병합 뒤 실제 실행에 쓰려면 러너 `.runtime` 재설치가 필요하다(러너 새 코드 반영 절차).
- /4 ledger identity가 바뀐다. 실패·중단된 기존 /4 실행을 이어 가려면 `--resume <이유>`(지금과 같음). 이어 가는 실행은 저장된 normalize를 그대로 쓴다.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 다음 /4 실행의 `normalize.json`에서 방향당 component 분포와 첫 누락 점검 missing 수, `v4-add-*` 문항 수를 본다.
- 롤백: 이 커밋을 되돌리면 /4도 `extract-v2.md`로 돌아간다.
- 승인 필요: master 병합, 러너 재설치, 운영 재실행.
