# Spotter 작업 안내

사진을 보고 푸는 땡시 앱이다. Study_EZ와 서버 인증을 공유하며
`runner`·`quizgen`을 import하지 않는다.
검사: `python -m pytest tests/spotter`.

## 원본과 생성 파일

| 수정할 것 | 원본 |
|---|---|
| 문항 정답 오류 | `data/question_corrections.json` |
| 사진 이름표 | `data/image_overrides.json` |
| 종 정보 | `data/species/*.json` |
| 표본 정보 | `data/specimens/*.json` |
| 용어 별칭 | `data/glossary.json` |
| 구별하기 어려운 사진 쌍 | `data/identification_pairs.csv` |
| 기생충학 화면 | `web/` |
| 해부학 화면 | `web/anatomy/_template.html`와 설정 |

`generated_exams.json`·`images.json`·`past_questions*.json`·마스터 JSON/CSV 등은
생성 파일이다. 원본을 수정한 뒤 필요한 빌드를 실행한다.
생성 데이터는 기본 검색에서 빠지므로 조사할 때 파일 경로를 명시한다.

```powershell
python spotter/scripts/build_master.py
python spotter/scripts/build_web.py
python spotter/scripts/build_anatomy.py --check
python spotter/scripts/sync_shared.py --check
```

공용 세션의 원본은 `../platform/session/session.js`이고 `web/session.js`는 사본이다.

## 배포

`spotter-dist/`는 생성된 배포본이므로 직접 고치지 않는다.

```powershell
python spotter/scripts/deploy_pages.py --check spotter-dist
python spotter/scripts/deploy_pages.py spotter-dist
```

두 번째 명령은 로컬 배포본을 만든다. R2 업로드와 원격 Pages 배포는 별도 운영 작업이다.
[배포 안내](../docs/deployment.md)와 [형제 앱](../docs/sibling-apps.md)을 따른다.
