# 사진 실습 Main-Quiz 수작업 반입 — Spec

Intent: [intent.md](intent.md).

## 1. 문항 힌트 칸 `clue`

- 문항(`bank_snapshot.questions[]`)의 선택 칸 `clue`(문자열): 발문에서 뺀 부위·염색·임상 단서.
  학생은 답을 보기 전에 「힌트 보기」(`H`)로 펴고 접는다. 답을 본 뒤에도 같은 자리에 남는다.
- 이름을 `hint`로 하지 않는다. `hint`는 v1.52 실험 뒤 걷어 내는 칸(`RETIRED_QUESTION`)이고, 옛 은행에 남은 값이
  학생에게 새로 보이면 안 된다. `clue`는 사진 반입 판(§3)에만 허용한다 — 생성 파이프라인 계약과 프롬프트는 바뀌지 않는다.
- 힌트를 편 것은 기록하지 않는다(학습 기록·「도움받은 풀이」 판정 변경 없음). 후속에서 필요하면 따로 정한다.

## 2. 사진 판의 그림

- `studyez_contracts/roots/media.validate_images(bank, sources, *, photo=False)`.
  - `photo=False`(기존 모든 판): 변화 없음 — PNG만, 강의당 64장·8 MB, 화소 합 16M.
  - `photo=True`(사진 반입 판만): PNG 또는 JPEG(같은 `png_base64` 칸에 바이트), 200장·24 MB, 화소 합 64M. 장당 1 MB는 그대로.
  - JPEG는 SOI·EOI와 마커 구조를 확인하고 첫 SOF의 크기가 `width`·`height`와 같아야 한다. 해시 검사는 같다.
- `public_images`는 바이트의 실제 형식으로 `data:image/jpeg` 또는 `data:image/png` URL을 만든다.
- 근거: 조직 사진 PNG는 팔레트 압축해도 장당 약 300 KB(실측) → 140장 40 MB 초과. JPEG는 장당 약 60 KB.
- 그림 출처: 각 그림은 등록된 강의 원본 PDF의 한 쪽과 그 쪽 안의 crop(0–1)을 가진다. 필기 PDF의 내장 사진은
  그 그림이 놓인 자리, 필기자가 붙인 virtual-slide 캡처(Stamp 주석)는 주석 자리, 족보 그림은 족보 PDF의 그림 자리다.
  바이트는 그 자리의 원본 그림(필기자 동그라미·글씨 주석을 뺀 것)이다 — 쪽 렌더와 화소가 같지 않을 수 있으며 이를 판 기록에 적는다.

## 3. 수작업 반입 `photo-import/1`

- 파이프라인 결과(`validate_result`)가 아니다. 검수 증명·ledger·manifest·RootGeneration 행을 만들지 않는다.
- 문서는 `roots/1`이고 `generation_policy`를 두지 않는다(새 정책값은 서버 상태 계산 여러 곳을 바꿔야 해서 피한다).
  사진 판 표시는 `review.provenance.method == 'photo-import/1'` 하나다(`media.photo_import`). 이 표시는 `generation_policy`가
  없을 때만 효력이 있고, 생성 파이프라인은 이 값을 쓰지 않는다.
- 조립: `scripts/photo_quiz_import.py SPEC.json OUT.json`. 입력 명세와 문항 데이터는 저장소 밖에 둔다(족보 원문 — 공개 저장소).
  - 문항마다 목표 하나·방향 하나·관계 하나(같은 주제 개념 C→C association), 과제 하나. 포인트 하나가 모든 목표를 덮는다.
  - 과제 순서는 문항의 `learning_page`(사진이 놓인 필기 쪽; 족보 그림만 있는 문항은 같은 주제의 첫 쪽) 순.
  - tier는 문항 값, `importance`는 Essential 5·Core 4·Important 3·Optional 2. 목표 중요도 축은 `unreviewed`(근거 계산 안 함).
  - 족보 재현은 `format: mcq`, `mcq_mode: recall_first`(선지는 「선지 보기」 뒤), 정답은 선지 ID, 해설 첫 줄에 원문 정답.
  - 해설 = 사진 순서·사진 판독·감별·해설·출처. 해설 전용 그림(정답이 그림에 적힌 것 3장)은 계약에 자리가 없어 넣지 않는다.
- 검토 기록: `provenance.status='reviewed'`(게시 조건), `reviewer`에 「수작업 작성(Claude 세션), 관리자 지시로 반입;
  독립 원본·의학 검수자 아님」, `independent_points='unverified'`, `notes`에 승인 원문. `scope.limitations`와 은행
  `warnings`에 「파이프라인의 원본 대조·의학 검수를 거치지 않은 수작업 문항」을 적는다.
- 반입 방법: 기존 관리자 화면(Main-Quiz 강의 화면의 「관리자」)에서 JSON을 올린다 → 비공개 판 등록(`POST /admin…`,
  `reviewed=False`) → 「나만」(allowedUsers=[관리자])으로 활성화 → 확인 뒤 학생 공개는 따로. 기존 경로라 서버 반입 코드는 새로 없다.
  사진 판 문서(약 15 MB)를 올릴 수 있게 관리자 업로드 상한을 5 MB → 30 MB로 올린다(`RootLearning.tsx`).
- 기존 판·학습 기록을 바꾸지 않는다. 261104_05는 기존 판이 없다(로컬 기록 기준, 운영은 관리자 화면의 판 목록으로 확인).

## 수용 기준

- 기존 판(PNG, 64장 상한)의 검사 결과가 바뀌지 않는다(`tests/contracts` 전부 통과).
- 사진 판에서 JPEG·상한·크기 불일치·잘린 JPEG가 검사된다(`tests/contracts/test_photo_media.py`).
- 웹: `clue`가 있는 문항에만 「힌트 보기」 버튼·`H`가 보이고, 없는 문항은 화면이 그대로다. `npm run typecheck` 통과.
- 반입 도구가 로컬 격리 DB에서 등록·조회까지 통과한 뒤에만 운영 반입을 묻는다.
