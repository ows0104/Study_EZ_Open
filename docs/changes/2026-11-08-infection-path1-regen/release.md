# 감염병리1 Main-Quiz 새로 생성 — 품질 측정을 보완 루프에 연결 — 배포 준비

## 코드 리뷰·검증 결과

- `studyez_contracts/bank/quality.py`: basic인데 채점 단위 2개 이상이면 경고(warning만, 문항을 떨어뜨리지 않음).
- `studyez_contracts/roots/generation_v2.py` `quality_reasons`: 품질 경고를 `question_fix` 보완 사유로.
  `repair_reasons`가 붙인다. 보완 상한 3회는 그대로이고 계약 검증(`validate_result`)은 보완 사유를 다시 계산하지 않으므로
  기존 결과의 검증은 바뀌지 않는다.
- `content/prompts/learning-links/automation/author-v2.md`(2026-11-08 관리자 토의 반영): 정답은 핵심어(짧은 문장 허용),
  명제는 발문·cloze 틀에 두고 핵심어만 빈칸, basic 정답 하나, 기전은 인과 cloze, 발문에 상황 제시와 양방향 연결,
  한계·예외는 cloze·객관식·해설로, ox는 함정 명제에 쓰고 해설에 이유. 「문항 품질」 보완 사유를 형식·분할·해설로 고칠 것.
- `bank/quality.py`: ox인데 해설이 없으면 경고(이유를 아는 것이 목표).
- `runner/root_importance_review.py`: 자격을 「수정 3/3 소진」에서 「모든 단계 완료·결과 없음·다음 원본 대조 없음」으로.
  계약 쪽은 이미 최종 회차 n을 일반으로 받는다.
- 실행 스크립트 `run.py`: 이전 `2026-11-08-infection-path1-map/run.py`의 사본, 실행 폴더 `runs/_e2e/26110802`와 revision만 다름.

측정(읽기 전용, 새 코드. 경고 종류별):
- 운영 Quiz Bank 35편: errors 2(기존 그대로). 새 경고는 ox 해설 없음 56 · basic 복수 단위 6.
  기존 경고: 회상 부담 50 · 일부 노출 11 · 단정어×부정 7 · 정답 쏠림 5.
- 공개 98문항 판: errors 0 · 회상 부담 26 · 예/아니오 축 6 · 단정어×부정 3 · basic 복수 단위 2 · 정답 쏠림 1.
- Map 83문항 판: errors 1 · basic 복수 단위 62 · 회상 부담 39.

검사:
- 루트 `pytest tests`: 2,136 통과·3 건너뜀. 제외 1건은 `test_desktop_control` 바로가기 설치기(origin/master에서도 같은 실패).
- `scripts/map_numbers --check` 정상.
- 서버(브랜치 계약을 `PYTHONPATH`로, 파일별 격리 sqlite, `.env` 없음): bank 33 · root_ 23 · route_contract · retention 모두 통과.

## 배포 대상 버전·순서·데이터 변경

master 병합 → Actions가 검사 → API(Cloud Run) → 웹(Pages) 자동 배포. server/·web/ 파일 변경 없음.
API는 같은 `validate_bank`로 Quiz Bank 업로드를 검증하므로 관리자 화면 issues에 basic 단위 경고가 새로 보일 수 있다(문항은 그대로).
DB·운영 문항·학습 기록·수정 상한 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인

배포 영수증·API health SHA 확인. 롤백은 병합 되돌리기.
감염병리1 새 생성(외부 모델 전송·대량 실행)은 실행 직전에 범위를 정해 사용자 승인을 받는다.
운영 등록·학생 공개·기존 판 교체는 별도 승인.

## 2026-11-08 실행 중 멈춤과 source 형식 복구 (claude/root-source-gap-recovery)

12:20 실행(`runs/_e2e/26110802`): Map 75개념(뿌리 7·깊이 3·관계 34) → 포인트 66 → 대조 지적 4 → 보완 70 → 재대조 지적 6(기록만)
→ packet → normalize(초기 지도 교정으로 보완 1/3 사용) → generate → **source-0 거절(12:47)**.
원인: 원본 대조가 required_gap I008에 필수 D046과 선택 D044·D045·D047·D048을 함께 적었다. 계약은 required_gap에 필수 방향만 받는다.
사용자 결정(2026-11-08 「복구 도구로 이어가기」).

- `generation_v2.split_required_gaps`: 필수 방향은 같은 required_gap에, 선택 방향은 같은 문구·문항의 optional_extension으로. 판단을 지우거나 올리지 않는다.
- `validate_source_gap_recoveries`·`accepted_source_raw_hash`: 원래 거절 사유·원문 해시·brief·결정적 분할을 증명으로 다시 계산. 최종 회차 source면 분할본 해시로 대조.
- `runner/root_source_gap_recovery.py`: 모델 호출 0, 원문·입력·사용량 그대로, 수정 상한 그대로. `.source-gap-recovery/`에 이전 ledger·도구·분할본 보관.
- `source-v2.md`: required_gap에는 required 방향만, optional은 optional_extension, 방향 없는 누락은 map_fix.
- 검사: 계약 3개(분할·거절·변조 6종), 루트 `pytest tests` 2,140 통과(제외 1 동일), 서버 root_ 24·route_contract 통과.
- 실제 폴더 사본에서 시험: 거절 재현 → I008만 분할 → 생성기가 medical-0 모델 호출 직전까지 진행.
