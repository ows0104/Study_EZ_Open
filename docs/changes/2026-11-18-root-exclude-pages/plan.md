# Main-Quiz 운영자 제외 쪽(page-withhold/1)과 261109_02 재출제 — 구현 계획

## 변경 범위·대상 파일·순서
1. 새 파일 `quizbank/withheld_pages.py`: 가린 문서·사본·사이드카 읽기.
2. 새 파일 `runner/page_exclusions.py`: 기록 읽기·굳히기·인용 세기.
3. 기존 파일 수정:
   - `runner/connection_generation.py`: 원본을 내려받은 뒤 `freeze`를 부른다. 게시 직전에 `withheld-citations.json`을 남긴다.
   - `runner/root_front.py`: `prepare`의 가린 사본과 `withheld_pages`, `refs_ok`·문제은행 그림 쪽·대조 쪽 검토.
   - `quizbank/connection_generate.py`: `prepare`가 가린 문서를 연다.
   - `quizbank/evidence_sources.py`: `prepare`가 가린 문서를 열고, 캐시 표식에 제외 쪽을 넣는다.
4. 검사 `tests/runner/test_page_exclusions.py`(합성 PDF, 가짜 모델):
   - 가린 쪽 모양(쪽 수·번호 보존, 원본 불변). 사이드카 지문 불일치.
   - 생성기·근거 material.
   - 기록 형식, 굳히기 1회·유지, 보류 세 가지.
   - 앞 단계 인용 거절.
   - 끝까지 도는 실행: 앞 단계·생성기 material이 가려지고 서버가 파생 packet을 그대로 다시 만든다.
5. 문서: `runner/CLAUDE.md`에 한 문단.
6. 운영: PR(Draft→Ready 한 번) → 병합 → 러너 재설치(메모리 「러너 새 코드 반영 절차」).
   그 뒤 `runs/page-exclusions.json`에 261109_02 행을 쓰고 restart+replacePublished 요청 하나를 넣는다.
   영수증은 이 폴더 `operations.md`에 남긴다.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner/test_page_exclusions.py -q`: 8개 통과.
- `python -m pytest tests/runner tests/quizbank tests/contracts -q`: 기존과 같이 모두 통과.
- 운영 확인:
  - 새 실행 폴더에 사이드카가 있고, `front/material/S1.md` 36~48쪽이 안내 문구이며 76쪽이 그대로다.
  - 새 판이 게시되고 공개판이 새 revision으로 바뀌었다(운영 DB 읽기).

## 위험·복원·승인할 범위
- 위험: 모델이 안내 쪽을 인용 → 앞 단계는 거절·후속, 생성기는 경고만(R5).
  거절(콘텐츠 제한)이 남은 쪽에서도 날 수 있다. 두 번쯤에서 멈추고 사람에게 넘긴다.
- 복원: 코드는 git revert. 기록 파일 행을 지우면 이후 요청은 원본 전체로 돈다. 이미 굳힌 실행은 그대로다.
- 승인 범위:
  - 코드 구현·PR·병합·러너 재설치.
  - 운영 DB 쓰기는 261109_02 restart+replacePublished 요청 하나(사용자 「교체한다」).
  - 모델 지정 파일은 건드리지 않는다.
