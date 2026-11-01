# 감염과 면역 2026 족보 배포·관리 형식

2026-11-01 사용자 명시 지시: “ㅇㅋ 그럼 감염과 면역 족보는 사이트에 PDF로 올려두고, JSON이랑 그림은 관리용으로 보관해줘.”

- 사이트의 강의별 족보 첨부는 검증된 PDF 정리본을 사용한다. 현재 기준은 `docs/changes/2026-11-01-infection-jokbo-answer-audit/upload-plan.json`의 80개 수업 / 69개 단원 PDF다.
- 문항 JSON과 연결 그림은 관리용으로 보존한다. 기준 자료는 `output/materials/감염과 면역_2026_JSON/`의 catalog.json, questions.json, sections/, images/, source/ 및 관련 보존 자료다. 전체 ZIP도 같은 상위 폴더에 보존한다.
- 관리용 JSON·PNG·MD·ZIP으로 사이트의 PDF 족보 첨부를 교체하지 않는다. GPT 첨부용 MD·그림 묶음은 필요할 때 쓰는 파생 자료로 보존한다.
- 원본 PDF·원본 이미지·문항 ID·출처 및 정답 연결 확인 19개 상태를 보존한다. 내용 변경 시 관리 자료와 게시 PDF의 대응을 검증한다.
- 생성 자료를 갱신할 때 이전 버전을 보존하고 새 버전으로 기록한다. 기존 필기·퀴즈·개인 학습 기록은 유지한다.

관리 자료 제작·검증 근거: `docs/changes/2026-11-01-infection-jokbo-json/`.
