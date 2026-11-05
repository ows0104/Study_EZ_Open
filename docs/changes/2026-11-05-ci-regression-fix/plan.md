# 구현 계획

## 변경 범위·대상 파일·순서
1. test_promote에 같은/이전 mtime과 같은 크기·다른 내용의 결정적 재현 검사를 추가하고 기존 코드 실패 확인.
2. runner/deck.py에서 크기 이후 스트리밍 내용 해시로 동일성을 판정.
3. 같지만 원본 mtime만 다른 경우 목적지 보존 검사. 작업 기록 및 release 리뷰 작성.
4. 별도 codex/ci-regression-fix 브랜치를 push, PR 검사와 diff 리뷰 후 승인된 범위로 merge. master의 동일 SHA 검사·API 배포·웹 배포를 확인하고 dashboard 완료 기록 갱신.

## 검사 명령과 성공 조건
development.py verify --check regression -- <프로젝트 Python> -m pytest tests -q
 development.py verify --check contracts -- <프로젝트 Python> -m pytest tests/contracts -q
선행 focused 검사: tests/runner/test_promote.py. 실제 PR/master CI의 서버·웹·bridge 검사 통과도 확인한다. release check로 입력·계획에 묶인 검사/리뷰 근거를 확인한다.

## 위험·복원·승인할 범위
같은 크기의 덱 비교마다 두 파일을 읽는 비용이 추가되며 메모리는 제한된다. 파일 선택, 업로드 정책, DB, 권한은 변경하지 않는다. 새 승인 요청 없이 현재 사용자의 명시적 수정·배포 요청을 적용한다. 실패 시 배포를 우회하지 않는다. 회귀 시 수정 커밋 revert PR로 복원하며 운영 데이터는 되돌리지 않는다. API 및 웹 SHA 일치와 읽기 전용 health로 확인한다.
