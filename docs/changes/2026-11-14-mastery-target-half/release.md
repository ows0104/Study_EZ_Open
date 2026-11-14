# 검증

- 서버 `-m tests root`: 41/43 통과. 실패 2개(`test_root_map_tree`, `test_root_map_tree_v3`)는 서버 venv에 `fitz`(PyMuPDF)가 없어
  quizbank를 import하지 못한 환경 문제로 이번 변경과 무관.
- 서버 `plan`·`mastery`·`timetable`·`light`·`optional` 전부 통과.
- 전체 서버 검사는 로컬에서 10분 안에 끝나지 않아 PR CI에 맡긴다.
- 웹은 문구 두 곳만 바뀌었다. 로컬 typecheck는 메인 체크아웃의 옛 node_modules에 `pdfjs-dist`가 없어 무관한 오류만 남(CI 확인).
- 미확인: 운영 화면에서의 실제 값.
