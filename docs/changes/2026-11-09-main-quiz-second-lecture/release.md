# Main-Quiz 생성 두 번째 강의 시범 — 사슬알균 — 실행 기록

실행 폴더: `runs/_e2e/26110901/` (메인 체크아웃, git 밖). 코드: 이 worktree.

## 앞 단계 (2026-11-09 02:49–03:07, 18분, 멈춤 없음)

| 단계 | 결과 |
|---|---|
| prepare | S1 38쪽 · S2 8쪽 고정 |
| Map /3 | 개념 57 · 뿌리 6 · 깊이 3 · 관계 30 (4분) |
| 포인트 /3 | 81 (5분) |
| 대조 | needs_revision 10 — overmerged 5 · unsupported 4 · missing 1 |
| 보완 1회 | 89 |
| 재대조 | needs_revision 6 — 기록만(감염병리1과 같은 처리) |
| packet | `map-tree-26110901`, speedStages |

모델이 notes에 남긴 자료 충돌은 다음과 같다.
- 백신: 다당 vs 접합
- 비말 전파: 드물다 vs 없다
- catalase 감별
- 2025 참고 기출 정답 번호: 30·100번 vs 4·11번

모델은 이 충돌들을 지우지 않았다.

## generation/ — 실패 1 (03:07–03:32)

normalize → generate(106문항, 그림 8) → context-0 → source-0 ‖ medical-0 → 보완 사유(required_gap 등) → **repair-1 거절**.

결함 두 개가 겹쳤다. 둘 다 강의와 무관한 엔진 결함이다.

1. **보완 입력에 렌더러 소유 `stimuli`가 들어갔다.**
   - generate의 raw에는 `stimuli`가 0개였다. 렌더러가 `visual_stimuli`로 8개를 붙인 은행이 repair-1 입력 `bank`·`previousAuthoring.bank`로 갔다.
   - 모델은 지시대로 바뀌지 않은 문항을 그대로 베꼈다. 저작 스키마(`AUTHOR_BANK`는 `stimuli`를 뺀다)가 전체를 거절했다.
   - 감염병리1에는 그림 문항이 없어 이 길을 지나지 않았다.
2. **어댑터의 스키마 검사가 같은 세션 되돌려주기(#41)보다 앞에 있었다.**
   - 그래서 스키마 오류는 되돌려주기 없이 바로 실패했다.
   - 베낀 `stimuli`를 빼면 그 뒤에 `recall units must partition every component exactly once`가 하나 더 있었다. 되돌려주기가 잡았어야 할 종류다.

수정은 다음과 같다(c0f5a48a).
- `connection_visuals.authored`: 보완 단계 입력은 저작 형태(`stimuli` 없음)로 준다. 그림 선택은 `previousAuthoring.visual_stimuli`로 그대로 간다.
- `root_native_json`: 되돌려주기를 쓸 수 있으면 스키마 오류도 `check_file` 오류로 같은 세션에 한 번 되돌려준다. 쓸 수 없는 검사 환경은 지금처럼 바로 실패한다.
- 검사: 새 2개. 둘 다 수정 전에는 같은 오류로 실패한다.
- 결과: 루트 2,182 통과(제외 `test_desktop_control`), `map_numbers --check` 정상.
- 서버·계약 변경은 없다.

`generation/`은 보존한다. 사용량은 repair-1까지 1/3을 썼다. 2026-11-09 사용자 「generation-2로 다시」에 따라 같은 packet으로 `generation-2/`에서 다시 돈다.

## generation-2 — 실패 2 (같은 packet, c0f5a48a 코드)

normalize(초기 지도 오류 1 → 보완 1/3 선소비) → generate(89문항) → context-0 → source-0 ‖ medical-0
→ **repair-1 통과**(위 수정 확인) → context-1 → source-1 ‖ medical-1 → **repair-2(3/3, 마지막) 거절**.

- 원인: 모델이 `result.json` 앞에 UTF-8 BOM을 썼다. 영수증 해시는 맞았지만 어댑터가 엄격한 utf-8로 읽다 실패했다.
  감염병리1 26110803 audit에서도 같은 BOM이 나온 적이 있다(그때는 run.py의 postcheck로 처리).
- 수정(52e1e751): `root_native_json.read_model`은 모델이 쓴 파일의 맨 앞 BOM 하나를 허용한다. 바이트와 영수증은 그대로다.
  `artifact`·`check_file`·`validate_stage`·tier 복구·task supplement가 이를 쓴다. 검사 1개를 더했다(수정 전 실패).
- 이 폴더를 재호출 없이 이어 가려면 계약의 형식 복구(`validate_format_recoveries`, tier 표기 전용)에 새 종류를 더해야 한다.
  아직 하지 않았다.

### 내용 신호: 중요도 근거 다툼이 마지막 회차에 몰렸다

| 회차 | target_checks | 보완 사유 |
|---|---|---|
| source-0 | unknown 118 · conflict 1 | question_fix 34 · map_fix 4 · required_gap 3 |
| source-1 | consistent 60 · unknown 31 · conflict 28 | question_fix 14 · **map_fix 68** · required_gap 16 |

- source-1의 map_fix는 대부분 「목표 X의 근거를 별도로 판단한다」였다.
  예: 포인트가 S1 7쪽 Summary를 `learning_objective`로 적었는데 「Summary 본문은 2쪽의 명시적 학습목표가 아니다」.
- 포인트 /3 단계의 importance_basis 판정을 원본 대조가 두 번째 회차에서야 본격적으로 다투었다.
  그 결과 98건이 마지막 보완 1회에 실렸다.
- 감염병리1 26110803에서는 최종 conflict가 7이었다.

## generation-3 — 보완 3/3 소진, 최종 정답 검수 보류 (결과 없음)

같은 packet이고 코드는 52e1e751(수정 3건 모두)이다. 엔진 결함으로 멈춘 곳은 없었다.

| 회차 | context(임상 정리 확인) | medical(독립 정답 검수) | source 지적 |
|---|---|---|---|
| 0 | consistent | 완료(round-0 은행) | required_gap 45 · map_fix 34 · question_fix 14 |
| 1 | **unknown** — 「나머지 PNG를 직접 대조한 근거가 없다」 | **blocked**(보완 사유 아님) | question_fix 3 |
| 2 | **conflict** — repair-2가 Q107·Q108 해설에 「P018의 … 보완」 같은 저작 이력을 썼다 | **blocked** | required_gap 2 · map_fix 1 · question_fix 1 |

- 보완 예산: 초기 지도 교정 1회 + repair-1 + repair-2 = 3/3.
  마지막 회차가 blocked여서 생성기는 설계대로 게시하지 않고 멈췄다(「독립 정답 검수 입력 분리가 완료되지 않았습니다」).
- 내용은 수렴했다(최종 source 지적 4건). 그러나 **최종 은행에는 독립 정답 검수가 한 번도 돌지 않았다.**
- target_checks: source-0만 판정했다(consistent 87 · conflict 32). source-1·2는 119개 전부 unknown이었다.
  같은 지시문인데 회차마다 판정 범위가 다르다.

## 시범에서 나온 것 (요약)

엔진 결함 3건은 고쳤다(c0f5a48a · 52e1e751). 검사는 새 3개이고 수정 전에는 실패한다.
1. 보완 입력의 렌더러 소유 `stimuli`(그림이 있는 강의에서 처음 지남)
2. 스키마 오류가 같은 세션 되돌려주기를 건너뜀
3. 모델 파일의 UTF-8 BOM

일반화 전에 정해야 할 것(설계 결정, 미착수):
- **해설의 저작 이력**:
  - 해설에 포인트·문항 ID나 「보완」 경위가 들어가면 check_file에서 잡아 같은 세션으로 되돌릴지 정해야 한다.
  - 계약(`validate_authoring`)에 넣으면 이미 완료된 결과의 재검증에 영향이 있는지 먼저 확인해야 한다.
- **context `unknown`의 처리**:
  - 지금은 근거 없이 미뤄도 그 회차의 정답 검수가 조용히 빠지고, 보완 사유도 생기지 않는다.
  - 한 번 다시 묻거나 사유로 올릴지 정해야 한다.
- **초기 지도 교정의 예산 선소비**: 두 실행 모두 1/3을 먼저 써서, 실제 보완은 두 번뿐이었다.
- **원본 대조의 판정 범위 흔들림**: target_checks를 회차마다 전부 판정하거나 전부 미루었다. 그래서 중요도 근거 다툼(generation-2의 map_fix 68)이 어느 회차에 몰릴지 예측할 수 없다.

운영 반입·학생 공개는 하지 않았다. 결과(`result.json`)가 없다.

## 후속: 해설 저작 이력 검사 (2026-11-09 사용자 「해설 저작 이력 검사」)

- `quizbank/authoring_text.internal_id_mentions`가 학생에게 보이는 칸에서 이번 실행의 내부 ID를 찾는다.
  - 학생 칸: question·answer·answer_units·explanation·options·option_explanations·matching·sequence.
  - 내부 ID: 문항·포인트·개념·목표·방향·관계. 글자와 숫자를 모두 가진 ID만 센다. 그래서 P450·C5a·「A군」은 세지 않는다.
- `root_native_json.check_file`(generate·repair)이 이를 검사한다. 걸리면 같은 세션에 한 번 되돌려 의학적 설명으로 고치게 한다.
  - 계약(`validate_authoring`)과 생성기의 수용 판정은 바꾸지 않았다. 남은 것은 지금처럼 임상 정리 확인이 conflict로 잡는다.
  - 기존 결과의 재검증에는 영향이 없다.
  - 문항을 그대로 복사해야 하는 brief-repair 복구와, 원문을 보존하는 웹·독립 은행 generate에는 적용하지 않는다.
- 기존 결과물 13개 측정:
  - 감염병리1(공개 판 포함): 0건
  - 사슬알균 generate: 0건
  - 사슬알균 보완 출력: 3건(Q107·P018, Q108·P020, Q014·Q015)
  - 학생 칸 밖의 ID와 의학 표기는 세지 않았다(오탐 0)
- 검사: 새 2개(찾기 단위 1·같은 세션 되돌려주기 1), 둘 다 수정 전 실패. 루트 2,185 통과, `map_numbers --check` 정상.
