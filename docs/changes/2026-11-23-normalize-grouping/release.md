# Main-Quiz /4 정규화: 포인트를 강의 뼈대로 묶어 목표를 짠다 — 배포 준비

사용자 2026-11-23 「CLI normalize도 Work처럼 묶게 고쳐줘.」 브랜치 `claude/normalize-grouping`, 기준 master `3c24ca06`.

## 코드 리뷰·검증 결과

### 바뀐 것
- `content/prompts/learning-links/v4/normalize.md`: 「목표의 뼈대」 문단(R1), 지도 관계 중복 금지 문장 확장(R2).
- `content/prompts/learning-links/v4/PROVENANCE.md`: 한 문단.
- `tests/runner/test_root_native_v3.py`: /4 지시문에 R1·R2 문장이 있는지.
- 코드·스키마·수용 검사·DB 변경 없음.

### 검사
- `pytest tests studyez_contracts`(1차 지시문 시점): 3117 통과, 5 건너뜀. 제외 1개(`test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`)는 이 PC 환경 결함.
  2차 지시문은 문단 안 문장만 바꿨고 `tests/runner/test_root_native_v3.py` 14개를 다시 통과했다.

### 재생: 261118_05 저장 입력(`normalize.input.json`, 입력 지문 f8b43e…), gpt-6.1-sol, git 밖 `C:\sez\ng\`

모델 호출 2회(5.9분·6.1분). 1차 재생에서 root 남발·제목+물음표 cue·세부를 큰 목표에 접기가 나와 지시문을 한 번 고쳤다(root는 갈래 둘 이상, 세부는 leaf로 남김, 제목+물음표 cue 금지).
비교 스크립트 `C:\sez\ng\compare.py`.

| | CLI 이전 | Work | 새 지시문 1차 | 새 지시문 2차 |
|---|---|---|---|---|
| 목표 | 118 | 131 | 51 | 72 |
| root/branch/leaf | 0/18/100 | 9/81/41 | 14/21/16 | 7/27/38 |
| 갈래 2개 이상 걸친 root | — | 6/9 | 6/14 | 7/7 |
| 포인트가 여러 목표에 붙음 | 0 | 43 | 13 | 20 |
| 포인트 2개 이상 묶은 목표 | 0 | 34 | 37 | 36 |
| 지도 밖 추가 개념 | 222 | 101 | 7 | 20 |
| 관계 kind | association 271 | assoc 182·비교 9·인과 7·순서 2·선행 2 | assoc 65·비교 37·인과 32·순서 9·분류 5 | assoc 43·인과 31·비교 29·순서 5 |
| 제목+물음표 cue | 23 | 0 | 36 | 0 |
| 이름만 끼운 관계 cue | 0 | 0 | 0 | 0 |
| component 합계 | 249 | 259 | — | 204 |
| 문항 단위(방향 또는 recall_unit) | 151 | 164 | 112 | 119 |

- 2차는 성공 기준의 구조 항목을 채운다: root 7개가 모두 갈래를 넘는 축이고(예: 「세 바이러스의 과·유전체·외피 대응」,
  「노로·로타의 감별 축」, 「노로·로타의 설사 병인 비교」), 포인트–목표가 1:1이 아니며, 관계 kind가 원본 관계를 따르고,
  답 조각 개념이 사라졌다. 11-11에 막은 이름만 끼운 cue는 0이다.
- **남은 차이: 2차는 Work보다 거칠다.** component가 204개로 CLI·Work(249·259)보다 약 20% 적고 문항 단위도 119개다.
  묶으면서 세부 일부가 빠졌거나 합쳐졌을 수 있다. 뒤 단계 누락 점검(component 합집합)은 normalize에 없는 component를 찾지 못하므로,
  빠진 세부는 문항 추가로 되살아나지 않는다. 포인트는 100개 모두 목표에 붙어 있다.
- 한계: 표본 한 강의, 재생 두 번. 뒤 단계(문항 작성·검토·의학 검토)는 돌리지 않았다. 연결 문항·포인트 밀도·cloze 표·의학 위험이
  Work판처럼 나오는지는 확인되지 않았다.

## 배포 대상 버전·순서·데이터 변경

- 데이터·DB·서버 API 변경 없음. 지시문만이다.
- master 병합은 사용자 결정. 병합 뒤 실제 실행에 쓰려면 러너 `.runtime` 재설치(러너 담당 세션과 맞춘다).
- /4 ledger identity가 바뀐다. 실패·중단된 기존 /4 실행을 이어 가려면 `--resume <이유>`. 이어 가는 실행은 저장된 normalize를 쓴다.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 다음 /4 실행의 `normalize.json`에서 root/branch/leaf, component 합계, 첫 누락 점검 missing, `v4-add-*` 문항 수.
- 롤백: 이 커밋을 되돌리면 /4 normalize가 이전 지시문으로 돌아간다.
- 승인 필요: master 병합, 러너 재설치, 끝까지 돌리는 비교(약 80분, Codex 사용량).
