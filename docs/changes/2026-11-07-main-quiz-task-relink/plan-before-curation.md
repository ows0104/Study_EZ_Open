# Main Quiz 새 판 대체 — 구현 계획

1. 현재브랜치·협업 claim 유지, 보존형28연결 초안은 모델호출0 상태로 중단하고 새 사용자 지시를 기록한다.
2. studyez_contracts/roots/task_supplement.py를 명시적 새판 계약으로 조정한다. 새 전체BANK·원본그림명세·각문항 전체회상목표를 받으며 실제파일/모델완료/독립검수/별도0..3 예산/표준계약을 검증한다.
3. runner/root_task_supplement.py는 과거 결과를 고정 입력으로 삼아 실제CLI 작성, 원본 이미지 결정적 추출/render, 원본·목표 검수와 독립 의학검수 병렬 실행을 수행한다. 모든 문항의 준비/누락조건을 평가하고 새3회 이내에서만 모델수정, 모든 과거 출력은 보관한다. root 에이전트는 임상문항/의학판정을 직접 작성하지 않는다.
4. server/app/root_learning의 명시적 replacement 반입과 notes/source 읽기 연결을 추가한다. 원래판/기존일반은행은 보관, 공개범위기존유지, 새판 활성화. 운영의 실제 사람학습 기록 수와 baseline을 먼저 확인한다.
5. relink-contracts/runner, relink-server, preserved-candidate(원래입력·실제원본 지문/새판검증), live-followup(CLI영수증/격리UI/원본이미지/실제반입) 수행. 전체CI/리뷰→동일SHA API/웹→관리자시범 새판 반입 및 실제readback. UI 경로·단축키/기존 legacy 링크 보존, 현재배포assets 확인.

사용자 현재 새판 대체 지시가 구현/필요문항·이미지 수정/실제CLI·기존3회와 구별되는 새 생성·운영 대체에 적용된다. 데이터 삭제/학생전체공개/다른강의 실행은 불필요하다. 복원은 원래active판으로 되돌리고 원래판/새실패를 지우지 않는다.
