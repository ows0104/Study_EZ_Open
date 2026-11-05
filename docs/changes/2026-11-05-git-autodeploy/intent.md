# Git collaboration snapshot and automatic production deployment

## 문제와 사용자 효과
사용자 요청(2026-11-05): “지금까지 한 거 전부 Git에 커밋, 푸시해주고, Git을 변경하면 자동으로 배포되게 해줄 수 있어? 슬슬 공동작업을 준비하고 있어서.” 현재 추적 대상 변경 전체를 보존하고 GitHub 기반 협업과 운영 자동 배포를 연결한다. 이 요청은 이번 Git 정리와 자동 배포 구현·활성화에 대한 현재 사람의 승인이다.

## 범위와 성공 기준
비밀값·원본 강의·생성 캐시는 기존 제외 정책을 유지한다. master push의 검사 성공 후 API를 먼저 배포하고 같은 Git SHA의 API가 확인된 후 웹을 배포한다. 다른 브랜치/PR은 검사만 한다. DB/문항/학습 기록/공개 권한을 변경하지 않는다.

## 근거·미정 사항
GitHub private 저장소, Cloud Run studyez-api, Cloudflare Pages study-ez-open의 기존 계정을 사용한다. 현 GitHub 요금제는 private 브랜치 보호를 지원하지 않는다(403 확인). 강제 보호를 설정했다고 보고하지 않는다. 자료 변경 자체의 의미와 기존 승인 기록을 이번 작업에서 다시 해석하지 않고 요청한 스냅샷으로 보존한다.
