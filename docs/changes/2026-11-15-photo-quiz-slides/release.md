# Main-Quiz 사진 문항 참고 슬라이드 — 검증

- 서버 `-m tests root_photo_import` 통과(새 검사: 사본 전 슬라이드 없음, 사본 뒤 인용 쪽 1개·프록시 200·원본 링크).
- 서버 `-m tests root main_quiz` 44/46 통과. 실패 2개(`root_map_tree`·`root_map_tree_v3`)는 로컬 서버 venv에 pymupdf가 없어서이고
  변경 전에도 같다(photo-quiz-import 기록과 같음).
- `main-quiz-photo-sources` 미리보기를 운영에 읽기로 돌려 네 원본 모두 지문이 맞는 파일을 찾음(위 plan).
- 미확인: 운영 반영 뒤 실제 답 화면. 업로드·배포 뒤 확인해 여기에 적는다.
