# JSON 자료 제공 완료

현재 승인 범위의 자료 제작 작업이다. 서비스 코드·DB·학습 기록 배포는 없다.
기준: answer-audit/upload-plan.json과 원본 2026 족보. 69단원·850문항 항목(원문 중복 보존), 80개 강의 연결, 831개 원본 정답 연결 및 19개 보류 상태를 그대로 보존했다.
출력: output/materials/감염과 면역_2026_JSON/, 같은 상위 폴더의 JSON 전체 ZIP 및 GPT 첨부용 ZIP.

자료 계약: 문항 원문과 교수·연도·정답·그림 및 원본 좌표를 JSON에 저장한다. 문항용 사진·표·도식 308개 영역, 전체 자료 영역 464개와 원본 대조 PNG 1691개를 보관한다. 원본 PDF는 동일 바이트로 복사하고 216개 원본 이미지 리소스와 압축 스트림·마스크를 보관한다.
GPT용 MD 69개를 JSON에서 생성하고 실제 첨부용 PNG 317개를 연결한다. 이 중 4개는 이미지 보기형 2문항의 원본 배치 대조 이미지로, 보기 번호와 그림의 관계를 보존한다. GPT 묶음은 수업명 폴더와 수업별_자료목록.txt를 포함한다.

검사: materials-verification.json에서 원본 텍스트·보기 분리의 무손실성·이미지 연결·실제 원문 픽셀·ID 여백의 원본 픽셀 보존·원본 PDF/이미지 스트림 해시를 확인했다. 전체 페이지의 고정 해상도 렌더를 사용하여 클립별 JPEG 리샘플링 차이를 제거했다. 마지막 추가 배치 이미지 검사는 직전 실제 통과의 동일 메타데이터/파일 해시 픽셀 증거를 재사용하고 새 4개 레이아웃 이미지의 원본 픽셀을 검증했다.
visual-review.json에서 사진·표·그래프·분할 문항·이미지 보기형 문항을 직접 확인했다. package-verification.json에서 두 ZIP의 모든 파일 바이트/해시, 안전 상대 경로, JSON 일치 및 GPT MD 이미지 링크를 검증했다.

배포/복원: 사용자에게 다운로드 파일을 제공한다. 기존 원본과 이전 정리본은 그대로 보존한다. 해당 자료를 사용 중지할 때는 기존 사이트 PDF를 계속 사용하면 된다. 생성 자료를 원본이나 개인 기록의 대체본으로 취급하지 않는다.
재생성 순서: build_package.py → finalize_exports.py → 전체 verify_materials.py → image_choice_layouts.py → finalize_exports.py → verify_materials.py → 시각 검토 → create_bundles.py → verify_package.py. 완료한 출력 폴더는 덮어쓰지 않고 새 버전 폴더를 사용한다.

## 사용자 최종 배포·보관 결정 (2026-11-01)

사용자 요청에 따라 사이트는 PDF 정리본을 유지하고 JSON과 연결 그림은 관리용으로 보존한다. 적용 지시는 docs/policies/infection-immunity-materials-2026.md에 기록했다. confirm_distribution.py의 읽기 전용 확인에서 80개 시간표 연결 PDF의 실제 저장 바이트가 검증본과 일치했고, 관리 자료 전체와 두 ZIP의 해시도 일치했다. 자세한 현재 확인은 distribution-confirmation.json에 보관한다. 추가 원격 변경이나 서비스 코드 배포는 없었다.
