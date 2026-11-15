# 감염병리 사진 판 r3 — Implementation Plan

[Spec](spec.md). 사용자 「문항 내용도 새 판으로 고쳐 줘」가 작업 요청이다. 운영 판 교체는 내용·승계 결과를 보고 따로 승인받는다.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `scripts/photo_quiz_import.py` | 명세 `carry_from` → `carry_links`(같은 ID·같은 `direction_hash`만 equivalences) |
| `server/tests/test_root_photo_carry.py` | 승계·미승계·ID만 같은 링크 거절 |
| 저장소 밖 `import_r3/make_spec.py`·`spec.json`·`document.json` | r3 내용 |

## 순서

1. 도구 → r2 재조립 해시 일치 확인 → r3 조립(150과제·링크 89).
2. 격리 로컬 DB에서 실제 문서로 등록·학습·교체 확인, 서버 검사.
3. Draft PR → CI → 병합(도구·검사만, 운영 영향 없음).
4. 사용자 승인 뒤 운영: 관리자 경로로 r3 등록 → 공개 판을 r3로(전체 공개 유지). 교체 직후 r2 기록이 승계된 방향에 이어지는지 읽어 확인.

## 복원

공개 판을 r2로 되돌린다(관리자 publication). r2·r3 기록은 모두 남는다.

## 검사 기록 (2026-11-16, 로컬)

- r2 재조립 `document_hash` 8014c24c… = 운영 r2.
- r3: 150과제, 그림 277장, 23.9 MB, 승계 링크 89.
- 격리 DB: r2 등록, 6과제 학습(승계 4·변경 2) → r3 등록 통과 → 학습 4/150(승계된 4만).
- `-m tests root_photo` 3개 통과, `tests/contracts/test_photo_media.py` 5개 통과.
