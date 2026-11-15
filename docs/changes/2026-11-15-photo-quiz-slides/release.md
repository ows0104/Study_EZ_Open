# Main-Quiz 사진 문항 참고 슬라이드 — 검증

- 서버 `-m tests root_photo_import` 통과(새 검사: 사본 전 슬라이드 없음, 사본 뒤 인용 쪽 1개·프록시 200·원본 링크).
- 서버 `-m tests root main_quiz` 44/46 통과. 실패 2개(`root_map_tree`·`root_map_tree_v3`)는 로컬 서버 venv에 pymupdf가 없어서이고
  변경 전에도 같다(photo-quiz-import 기록과 같음).
- `main-quiz-photo-sources` 미리보기를 운영에 읽기로 돌려 네 원본 모두 지문이 맞는 파일을 찾음(위 plan).
- 운영 반영(2026-11-15): `main-quiz-photo-sources --apply`로 S1·S2(로컬)·S3·S4(기존 고정 사본) 4개를 올림(사용자 「둘 다 진행」).
  #192 병합 `637cb12f`의 배포는 뒤 커밋에 밀려 멈췄고, #193 배포(`13811606`, 이 변경 포함)가 운영 API에 올림.
  병합 코드를 운영 데이터에 읽기로 돌려 141문항 모두 슬라이드가 붙음(강의 필기 S1 77·S3 16·S4 40장, 족보 S2 20장).
- 미확인: 로그인한 실제 화면에서 PDF.js가 그리는 것.
