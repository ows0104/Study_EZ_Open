# Main-Quiz 사진 문항 참고 슬라이드 — 구현 계획

승인: 사용자 지적(2026-11-15)이 수정 지시. 운영 저장소(R2)에 사본을 올리는 것과 master 병합(=배포)은 따로 확인한다.

## 파일

1. `server/app/root_learning/evidence.py`: `photo_sources`·`source_list` — 출제 기록이 없고 `photo-import/1`이면 지문 이름 사본
   (있음만 확인해 기억, 없음은 기억하지 않음). `frozen_pdf`·`attach_evidence`가 이것을 쓴다.
2. `server/app/cli.py`: `main-quiz-photo-sources <과목> <회차> [S1=<pdf> ...] [--apply]` — 같은 과목 출제 기록의 같은 지문 사본,
   또는 명령줄 로컬 PDF 중 지문이 같은 것을 올린다. 기본은 미리보기.
3. `server/tests/test_root_photo_import.py`: 사본 전 슬라이드 없음 → 사본 뒤 인용 쪽 슬라이드·프록시 스트림·원본 링크.

## 운영 반영 (확인 뒤)

미리보기(2026-11-15, 운영 DB·저장소 읽기만):
S1 83.2 MB(로컬 필기복습 사본) · S2 36.4 MB(로컬 족보 원본) · S3 22.8 MB · S4 25.4 MB(기존 고정 사본에서 복사).

## 위험·복원

- 위험 낮음: 출제 기록이 없는 사진 반입 판만 새 길을 탄다. 복원은 `git revert`, 올린 사본은 지워도 판·기록에 영향 없다.
- S1은 사용자의 필기복습 폴더 파일이다(판을 만들 때 쓴 바로 그 파일). 판을 볼 수 있는 학생은 답의 슬라이드·원본 열기로 이 PDF를 본다.
