# 선지: 사진 문항 그림 전달·작성·검토 기준 완화 — 배포 준비

## 코드 리뷰·검증 결과
2026-11-14 로컬(worktree `../Study_EZ_mcq-images-lenient`, origin/master 0ada75df 기준, 기록 `runs/_development/2026-11-14-mcq-images-lenient/`):
- 검사:
  - `tests/quizbank/test_root_mcq.py`·`tests/runner/test_root_mcq_publish.py` 30 통과. 새 검사 3개:
    - 그림이 작업 폴더·입력·작성/검토 호출로 간다.
    - 그림 없는 묶음은 `images` 인자 없이 부르고, 검토 입력에 `lecture_facts`가 들어간다.
    - 깨진 base64는 그 그림만 뺀다.
  - 회귀 `pytest tests/contracts tests/quizbank tests/runner`: 2292 통과·1 건너뜀·1 실패.
    실패 `test_shortcut_installer_supports_korean_filename_in_windows_powershell`는 master에 있던 바로가기 설치기 결함이다(choices-merge 기록과 같음).
  - ruff: 새로 생긴 지적 없음(C420·SIM105 3개는 master에 있던 것).
- 실제 모델 재생성(소아감염 261113_02, 판 `auto-fea11389…`, 이 브랜치 코드):
  - 대상 141 중 작성 99 → 129, 건너뜀 42 → 12. 오답 299 → 410. 의학 검토가 뺀 오답 42 → 16. 실패 묶음 0.
  - 사진 문항 10개 전부 그림이 첨부됐다(usage `images` 8+2).
    - 예전에 빠졌던 Q025·Q067·Q073이 3개씩 생겼다.
    - Q025 오답의 이유가 그림을 근거로 한다(「사슬 모양의 그람양성 구균으로 포도송이 모양의 S. aureus와 다르다」).
  - 완화가 의도대로 작동했다. Q127 「여름, 장마철」「여름, 휴가철」, Q155 「29%」「36%」(같은 연구의 다른 지표)가 이제 남는다.
  - 「목록에 실제로 속하는 항목」은 계속 빠진다. Q074(다형홍반 병원체), Q135(수족구 부위), Q040(PCR 지속 검출 바이러스)는 그 이유로 아직 건너뛴다.
  - 남은 약점: Q006 오답(자가면역질환·악성종양·약물열)이 감염 범주가 아니라 쉽게 지워진다.
- 이전 결과 보존: `mcq-v2-before-lenient/`(폴더 전체), `mcq/v2-auto-fea11389….json`, `mcq/uploaded.before-lenient.json`.

## 배포 대상 버전·순서·데이터 변경
- DB 스키마·서버·웹·계약 변경 없음. asset 모양 그대로(`root-mcq/2`).
- 운영 asset: 소아감염 `root_mcq/auto-fea11389….json` 1건 교체(2026-11-14 20:56 KST, 231,898 B).
  운영 문서로 서버 판정을 재현해 154문항 중 129문항에 붙는 것을 확인했다(전 99).
- 순서: 위 재생성·업로드(완료) → master 병합 → 러너 재설치(게시 직후 선지 단계가 새 코드로).
  나머지 27편 재생성은 따로 정한다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 러너 `agent.lock` pid·새 설치본, 다음 게시 강의의 `usage.jsonl`에 사진 문항이 있으면 `images`.
- 롤백:
  - 코드: 병합 커밋 revert.
  - 소아감염 선지: `mcq/v2-auto-fea11389….json`을 `auto-fea11389….json`으로 복사하고, 표시 파일을 지운 뒤 `--upload-only`.
- 승인: 사용자 2026-11-14 요청(state.json build 근거). 범위는 소아감염 한 편 재생성·업로드, 병합, 러너 재설치. 나머지 27편은 제외.
