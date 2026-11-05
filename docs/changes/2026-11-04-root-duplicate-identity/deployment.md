# 실제 배포 및 시범 보존

검증된 고정 사본 tmp/root-web에서 계약72, 격리 API6 suites, 웹 형식/생산 빌드/테스트 로그인 토큰 제외 검사가 모두 source b25b3e906bf8e636249bdcad0877118d3d25bc4bca8df8812a8c55f36144d722 / plan ef662f73bf081795994dfb0521ebca34d92143aea8eba4d449d3fc8155d41d12에 묶여 통과했다. 원래 폴더의 다른 미커밋 변경은 섞지 않았다. 정본 상태/승인/리뷰/검사·사후 로그 사본은 verified-scope에 보관했다. 원래 폴더의 state.json은 초기 계획 상태이며, 해당 전체 폴더를 검증한 근거로 대체하지 않는다.

API e8a7c1bb89e3c903e0908f020ce97d8ba1104bb7087f818e6c9a150638e45274 → studyez-api-release-1793757910362950700: 실제 revision Ready/ContainerReady/latestCreated/latestReady 확인 후100% 전환, health와 읽기 전용 인증/root smoke 통과. 웹4c8b9dc6be6df49de1e31d9f0f54c53686c99deaa727e8beaa18489c7ae68cea → Pages57fe6571-2415-4250-9895-e5f2bb903171: 업로드/실제 배포ID 확인 및 health/root smoke 통과. 후보를 먼저 둘 다 준비했을 때 마지막 웹 후보가 선택돼 첫 API begin이 'different target'으로 거절된 기록은 실제 배포 전이며, API 후보를 다시 선택·승인 기록해 순서대로 정상 배포했다. 자동 승인 검토 거절이 아니고 도구의 후보/대상 일치 검사다.

운영 보정은 정확한 generation dbdbfaa349944893967c350116656cd7/job525만 대상으로 했다. 원래 f0a8f3b68e3642598f85bbf462e1dc55/job524와 같은 소유자·실효 입력·고정 원본임을 확인하고 검사된 retain_duplicate를 사용했다. 중복 요청은 canceled/중복 요청 보존 상태로 종료하고 supersededBy를 원래 시범에 연결했으며 임시 resumeAt 지연은 해제했다. 추가 모델 호출0회다. 전송 기록과 원본은 그대로이며, 아직 수신되지 않은 중복 MD도 정확한 보존 상태에서는 수신·보관할 수 있다. 임의 취소와 변경된 MD의 거절은 유지한다.

배포된 실제 StudyEZ 화면을 다시 열어 새 응답 대기가 아닌 원래 시범의 검수 연결 실패를 표시하는 것을 확인했다. 증거는 production-final.jpg, 좁은 운영 변경은 execution.json이다. 기존69문항/build/status/bank/validation/review6개 baseline 값이 모두 동일하고 RootControl/result 게시가 없는 것도 다시 확인했다. 원래13단계/수정3회/원본·정답검수4회와 모든 판정/지문/실패를 유지했다. 부분 채택 제안은 별도 사람 선택 대기이며 구현하거나 게시하지 않았다.
