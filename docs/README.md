# 문서 안내

현재 코드에 필요한 설명부터 읽고, 과거 결정의 이유가 필요할 때 기록을 연다.

| 목적 | 문서 |
|---|---|
| 수정할 파일 찾기 | [작업 지도](map.md) |
| 실행·검사 | [명령 안내](commands.md) |
| 데이터 흐름·책임 | [현재 구조](architecture.md) |
| 폴더와 옛 이름 대응 | [폴더 안내](layout.md) |
| 파일·서버 계약 | [산출물 계약](artifact-contract.md), [표본](samples/README.md) |
| 실행 시도와 배포본 | [runs 구조](runs-layout.md) |
| 퀴즈 파이프라인 | [quizgen](quizgen.md), [프롬프트 조립](prompt-architecture.md) |
| 배포 | [배포 안내](deployment.md), [Pages](cloudflare-pages-runbook.md) |
| 인프라 운영 | [R2](r2-runbook.md), [도메인](domain-runbook.md) |
| 앱 추가·공유 인증 | [형제 앱](sibling-apps.md) |
| Chrome 확장 제출 | [스토어 제출](chrome-web-store-submission.md) |
| 실패 사례·인터뷰·옛 인계 | [기록 보관함](archive/README.md) |

컴포넌트의 `CLAUDE.md`는 수정 시 지켜야 할 계약과 검사만 담는다.
명령 옵션은 해당 CLI의 `--help`, 데이터 필드는 코드의 스키마가 기준이다.
문서에 수시로 변하는 코드 줄 수·테스트 개수·운영 리비전을 복제하지 않는다.
