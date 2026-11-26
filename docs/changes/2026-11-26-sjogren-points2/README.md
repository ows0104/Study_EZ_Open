# 쇼그렌(261123_07) 출제포인트 2차 보강 — 공개판 제자리 수정

2026-11-26. 1차 보강([2026-11-26-sjogren-points](../2026-11-26-sjogren-points/README.md), #269)의 뒤를 잇는다.

## 왜

사용자가 1차 보강 뒤 「CD40L과 같은 약제 퀴즈가 없는데?」, 「미토콘드리아도, poly IC도」라고 지적했다.
1차 대조에서는 내용이 카드 어딘가에 있으면 「있다」고 셌다. 이번에는 기준을 바꿨다.
**그 사실이 카드의 답 자리에 있고, 숨겨지지 않는 등급(Important 이상)인가.**

- 신약 이름을 답으로 떠올리는 카드는 Q120(Ianalumab) 하나였고, 그것도 Optional이었다.
  - SJ-Q068은 보기에서 고르는 것뿐이다.
  - Q091은 약–표적을 발문에 주고 기능만 묻는다.
- poly(I:C) 결과(KO는 침 분비 유지, 정상은 감소)는 Q018 발문에 쓰여 있었다. 정작 답으로는 묻지 않았다.
- 미토콘드리아 핵산이 IFN을 부르는 이유(host origin이 아님)를 묻는 카드가 없었다.

사용자 승인: 「A,B하고 Telitacicept도 해줘」.

## 바뀐 것 (`edits.json`)

| 카드 | 변경 | 내용 | 근거 |
|---|---|---|---|
| Q120 | Optional → Core | BAFF-R 표적 약 → Ianalumab | p.31 |
| Q016 | Optional → Core | 미토콘드리아 손상과 IFN의 선후는 불명확 (객관식) | p.10 |
| Q026 | Optional → Important | ESSDAI = 12개 객관적 장기영역의 가중점수 | p.13 |
| Q080 | Optional → Important | 림프종 외 위험 증가 혈액종양 → 다발골수종 | p.29 |
| Q135 (새, 부모 Q120) | Core | CD40L 차단 후보약 → Dazodalibep | p.31 표·필기 |
| Q136 (새, 부모 Q120) | Core | FcRn·IgG 대사 후보약 → Nipocalimab | p.31 표·필기 |
| Q137 (새, 부모 Q120) | Important | BAFF·APRIL 동시 차단 → Telitacicept | p.31 표만 (사용자 요청) |
| Q138 (새, 부모 Q015) | Core | 미토콘드리아 핵산이 1형 IFN을 부르는 이유 → host origin이 아니어서 바이러스처럼 취급 | p.10 필기 |
| Q139 (새, 부모 Q018) | Core | poly(I:C): KO {크게 변하지 않음}, 정상 {크게 감소} | p.10 실험 필기 |
| Q140 (새, 부모 Q122) | Important | Autoimmune epithelitis | p.7 |
| Q141 (새, 부모 SJ-Q063) | Important | pilocarpine과 같은 계열 → Cevimeline | p.30 |

**만들지 않은 것**
- ESSDAI–ESSPRI 상관이 낮다는 카드: SJ-Q019(Core O/X)가 이미 묻고 있다. 대조 정규식이 놓쳤던 것이다.
- cGAS–STING: Q138 해설에만 넣었다.
- 1차에서 남긴 수치(SMR, 91%/49%, flare 1–2%, C4 단독 감소): 손대지 않았다.

## 검사와 결과

`fetch.py` → `apply.py` → `verify.py` → `write.py`. 작업 사본은 `runs/_development/2026-11-26-sjogren-points2/`에 있다.

- **verify:** 사용자 3명, 이벤트 379건. 손대지 않은 과제 168개의 상태가 모두 같다. 선지(mcq) 144개와 slideFocus 196개가 붙는다.
- **write:**
  - root_content: 8b2bad24… → 736f7f6a…
  - root_generation 결과: 337103af… → 6ca0d4a8…
  - 선지·순서·근거 asset: 바뀌지 않음. 글을 바꾼 기존 카드가 없다.
- **다시 읽기:** digest가 맞다. light가 있다. 생성 결과 문서 = 공개 문서. 과제는 185 → 192개다.

## 주의

- 새 카드 7장에는 생성 증명이 없다. 이 편에 보강이나 채우기를 돌리면 거절될 수 있다(1차와 같다).
- 새 카드에는 객관식 선지가 없다. 모두 주관식이다.
- 1차 `edits.json`은 `.gitignore`(`docs/changes/**/*.json`)에 걸려 커밋되지 않았고, worktree를 지울 때 함께 사라졌다.
  1차의 변경 내용은 1차 README의 표에 남아 있다. 이번 `edits.json`은 `git add -f`로 넣었다.
