# 콜린성 약리학(1) — 시범 자료 확인

확인: 2026-10-29 KST. 파일·저장 메타데이터·지문만 확인했다. 원본 전체의 의학 내용 검토·새 추출은 미실행이다.

## 강의

- 제안하는 첫 시범: `261002_01`, 콜린성 약리학(1)(이철환).
- 별도 강의: `261002_02`, 콜린성 약리학(2)(이철환). 합치지 않는다.
- 필기: `C:/Users/ows01/SynologyDrive/약리학/필기/2026/[261002_01] 콜린성 약리학(1)(이철환)_한은범v1.pdf`.
- 확인한 크기: 5,419,206바이트. 기존 기록상 35쪽이며 이번에는 지면 수를 별도로 검증하지 않았다.
- 현재 SHA256: `29bb4ad01a626a581c198ea8c4bc96aed1cae225759f946fda076b3d394e3728`.
- `runs/261002_01/source.json` 및 은행의 저장 응답 identity와 일치한다.

## 족보

- 기존 연결 근거: `runs/261002_01/bank/jokbo.json`.
- 교수별 조각: `runs/_materials/약리학/261005-2324/교수별/이철환/L12-13_콜린성-약리학-1-2.md`.
- 범위 메타데이터: 같은 이름의 `.json`. 제목은 콜린성 약리학 (1)~(2)이므로 (1) 전용으로 간주하지 않는다.
- 현재 크기: 19,731바이트. 바이트 SHA256: `505f589dea926fb522e92411b7e5f37b67945e8ec6bad1b4e5983d1af6231b37`.
- LF 줄바꿈으로 정규화한 SHA256은 `08c0d6c6bd0f0b1f2bfcfdc91f7272a581f15c1821f32900e723dadd4da99f2e`로 저장 응답 identity와 일치한다. 바이트 지문 차이를 내용 변경으로 단정하지 않는다.
- `runs/_materials/약리학/261005-2324/cut.json`의 원본 기록은 `C:/Users/ows01/SynologyDrive/약리학/족보/2026/2026 약물의 이해 족보.pdf`, 기록상 101쪽이다.
- 조각의 추가 원본 기록에는 `C:/Users/ows01/SynologyDrive/약리학/족보/2020/2020 약물의 이해 본문.pdf`도 있다. 원본 PDF들의 현재 지문·해당 지면은 실행 전 확인할 사항이다.

## 기존 문제와 포인트의 성격

- `runs/261002_01/bank/response-resume.json`이 가리키는 로컬 참조 은행:
  `runs/261002_01/bank/261018-remaining23-order/bank.json`.
- 질문 69개, 고유 ID 69개, 기존 concepts/retrieval_plan 각 50개. 이는 기존 구조의 메타데이터이며 새 뿌리 50개라는 뜻이 아니다.
- 현재 SHA256: `ab80175aa2b2af4dbfbcd182348315fea28227cc392895feda78cda0f4884fe8`.
- 구형 quizgen의 `run.meta.json`에 기록된 카드 수와 이 은행의 문항 수는 서로 다른 산출물이다.
- 참조 포인트: `runs/261002_01/bank/261017-connection-batch/authored-points.json`, 69행.
- 같은 폴더의 `point-origin.json`: `origin: web-question-index`, `independent: false`.
- `runs/261002_01/bank/points/1792085820815759700/`에는 raw 계획과 context가 있지만 확인한 폴더에서 독립 완료를 증명할 authored-points/independent-origin 쌍은 찾지 못했다. raw 파일만으로 독립 검증 근거를 삼지 않는다.
- 재개 기록의 기존 `remainingRepairRounds`는 0이다. 새 설계 검토를 기존 문항 수정 잔여 횟수의 초기화로 사용하지 않는다.

## 현재 확인 범위

파일의 존재·참조 경로·일부 현재 지문과 기존 포인트의 출처 성격을 확인했다.
운영 서버의 현재 은행·학습 기록·공개 상태는 조회하지 않았다. 원본 누락 여부·문항의 정확성·새 뿌리의
선정은 아직 판정하지 않았다. 이 문서를 출제·검수 통과나 새 추출 완료 증거로 사용하지 않는다.
