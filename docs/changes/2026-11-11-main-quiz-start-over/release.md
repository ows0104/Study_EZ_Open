# Main-Quiz 새로 출제 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 `request()`: `restart`는 requestId 재사용 확인 뒤에만 처리한다. 같은 ID로 다시 보내면 첫 판을 돌려준다(R5).
  `restartOf`·`restartReason`은 `raw`에 들어가 입력 지문이 달라지고, 고유 제약(subject, run_id, input_digest)과 충돌하지 않는다.
- `generation_input`에 `restartOf`가 추가됐다. 옛 packet은 None이라 기존 중복 판정·`canonical_generation`·`retain_duplicate`는 그대로다.
- 러너·생성기: 두 키는 derive_packet이 그대로 복사한다. 모델 입력은 이름 붙은 필드(title·sources·points 등)만 읽어 모델에 가지 않는다.
  result 재유도(`map_tree.resolve`)는 같은 함수라 일치한다. 러너 재설치는 필요 없다.
- 화면: 실패·취소된 map-tree 판에서만 버튼이 보인다(held는 서버도 거절). 이유 칸을 공유하고 비면 막힌다. 공개 범위는 옛 판 값을 쓴다.
- 검사: 새 `server/tests/test_root_restart.py` 통과. `test_root_generation_columns`(응답 필드 사본에 `restartOf` 추가) 통과.
  web `main-quiz-generation-button` 12/12·typecheck·build 통과. 서버 전체 결과는 state.json의 regression 기록.
  `test_root_map_tree*`는 로컬 server venv에 PyMuPDF(fitz)가 없어 돌지 않는다(기존 환경 결함, CI에서 실행).

## 배포 대상 버전·순서·데이터 변경
- PR 병합 = master 검사 → Cloud Run API → Pages. DB 스키마·migration·운영 데이터 변경 없음.
- API와 웹 순서 무관: 옛 API는 `restart` 필드를 `extra='forbid'`로 422 거절하므로 웹이 먼저 나가도 아무 판도 만들지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 라이브 openapi에 `RequestIn.restart`가 있는지, 관리자 화면 261110_02에 「새로 출제 (처음부터)」가 보이는지.
- 실제 「새로 출제」 클릭은 사용자 몫이다(강의 자료 전송·학생 공개의 승인).
- 롤백: git revert → 자동 재배포. 이미 만든 새 판은 일반 판과 같아 그대로 남는다.
