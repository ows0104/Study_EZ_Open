# 검수통과28문항 보존형 과제재연결과 이미지 후속검수 — 구현 계획

## 변경 범위·대상 파일·순서
1. origin/master2489e52e 별도브랜치/worktree와 대시보드 claim, 현재 승인 기록. 현재 Main Quiz의 RootLearning/RootSolve 경로·배포assets 확인(구4등급UI는 legacy 링크에 보존).
2. studyez_contracts/roots/task_supplement.py: append-only 독립연결/검수/모든 원래방향 동일성/부모판과 proof 검사. 기존 표준 validate_document를 유지한다.
3. runner/root_task_supplement.py: 원래결과 전체고정·제안/독립원본·독립그림의 실제CLI 파일출력과 durable 영수증, 원본/material 보호, 상한3 보존. 필요시 원본PDF의 더 명확한 시각정보를 별도 검수에 사용하되 은행그림은 불변, 미해결은 보류한다.
4. server/app/root_learning/task_supplement.py 및 원본·검수 읽기 경로: 새판 명시반입, 동시변경/부모판hash/이력검사, 같은방향만 승계. 기존 UI/풀이계약과 오래된 세션은 보존.
5. 관련 contracts/runner/server 검사·원래자료보존·실제CLI 후속·격리UI와 저장/새로고침 확인. 전체CI→검토→같은SHA API/Pages→관리자시범 새판 게시/읽기/사람기록보존 증명. 원래실패·보류·새실패를 숨기지 않는다.

## 검사 명령과 성공 조건
relink-contracts: 기존문항/과제/방향/원본/수정횟수 변경거부, 새매핑 누락·판정 미완료·그림 미확인·stale/중단/replay 거부, 호환 계약회귀. relink-server: 원래판/사람사건/세션/은행 보존, 명시동일성 승계/신규미학습, 동시제어·멱등성·원본/새검수노트. preserved-candidate: 실제 모든 원래파일/91문항/원래49과제/3of3 지문. live-followup: 실제CLI 완료/독립검수/실제그림/표준계약/격리UI/배포/운영 새판 readback.

## 위험·복원·승인할 범위
현재 사용자 지시가 본 범위의 구현·실제CLI·관리자시범 포함·기록보존을 승인한다. 추가 문항수정/4회차 생성·학생전체공개·다른강의·다른세션 프롬프트/화면개편은 범위 밖이다. 복원은 control을 원래판으로 되돌리며 새판/원래판/사람기록/실패는 삭제하지 않는다. 위험은 새 의미연결 오판과 그림 불확실성이므로 독립CLI 검수와 실제이미지 확인을 유지한다.
