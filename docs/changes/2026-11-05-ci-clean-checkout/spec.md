# Make CI tests reproducible from a clean checkout — 설계

## 요구사항과 수용 기준
work 없는 checkout에서 tests/quizbank/test_incremental_comparison.py의 6개 검사가 동일한 provenance/hash/시간/검수 범위를 검증해야 한다. 작업 폴더에서 읽었던 일반 함수 구현을 그대로 승격하며 모델 호출이나 콘텐츠 판단은 추가하지 않는다. requests를 CI 설치 목록에 추가한다.

두 번째 실행 41983410862는 1,919 passed/1 skipped 후 Windows 바로가기 검사가 요구하는 실제 .venv가 없어 한 건 실패했다. 테스트를 건너뛰지 않고 CI에서 프로젝트 .venv를 생성해 모든 Python 검사/의존성 설치에 사용한다. 이는 동일한 새 checkout 재현성 복구 범위다.

실제 .venv 준비 후에도 영어 Windows의 WScript.Shell.Save가 한글 파일명을 저장하지 못했다. 목적지/대상/인수/설명/이름은 유지하고 COM 저장용 임시 이름만 ASCII로 한다. 기존 바로가기를 교체하는 동작은 유지하며 실패/성공 모두 새 임시 파일만 정리한다. 바로가기 변경은 기존 installer를 명시적으로 실행할 때만 일어난다.

## 책임·입출력 계약·오류 상태
scripts/incremental_comparison.py는 전달받은 합성/실제 아티팩트 폴더를 읽기만 한다. main/운영 탐색/자동 보고서 쓰기를 복사하지 않는다. 기존 업무용 work 원본은 그대로 보존한다.

## 호환성과 데이터 보존
서버/웹 제품 코드·DB·콘텐츠·학습 기록·권한 변경 없음. GitHub 전체 검사가 새 SHA에서 통과하기 전 서버 및 웹 배포를 허용하지 않는다.
