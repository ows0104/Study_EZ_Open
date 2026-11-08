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
