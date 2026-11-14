# 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_contracts/roots/generation_v4.py`: `relation_findings`, `make_document`의 coverage 판정 배치(B)와 manifest 키,
   result4 재계산 검사, MANIFEST_KEYS.
2. `quizbank/connection_generate_v4.py`: normalize 뒤 A, 조립 뒤 C(늦은 보충 1회)·재조립, D 멈춤. 2a 보충 블록을 함수로 빼서 두 곳에서 쓴다.
3. 서버 보고(`server/app/routes/root_generation.py` build_report, `web/src/bank/RootGenerationPanel.tsx`): 「검토 밖 배치 n개」 숫자 한 줄. 표시만.
4. 검사: `tests/contracts/test_generation_v4.py`(A 결함, B 배치·우선순위, 재계산 일치), `tests/quizbank/test_root_generation_v4.py`
   (brief-fix 호출, 늦은 보충 경로, 남으면 멈춤, 남는 것 없으면 지금과 같은 결과).

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank -q`, 서버 `pytest`(build_report), 웹 `tsc` 통과.
- 저장 산출물 재현(모델 호출 없음): 34개 v4 실행에서 A는 261105_03만 10% 초과, B는 운영판에서 98문항을 붙인다.
- 실측(모델 호출 있음, 로컬 사본, 운영 쓰기 없음): 운영판 2편(소아감염 fea11389, 피코르나 9cb48bf1)을 짧은 경로 사본에서
  재개 실행해 완료 단계는 재사용하고 C만 새로 돌린다. 남은 문항 수·멈춤 여부·추가 호출 수를 release.md에 적는다.
  멈춤이 잦으면 병합 전에 사용자에게 보고하고 기준을 다시 정한다.
- PR CI `Tests and build`, `Windows runner checks` 통과.

## 위험·복원·승인할 범위
- 위험: 중간. 대부분의 편에서 늦은 보충 호출(보통 4개)이 늘어난다. D 때문에 게시가 멈추는 편이 생길 수 있다(의학 검토 전이라 비용은 적음).
  B는 검토가 관계를 고르지 않은 문항을 범위 점검 판정으로 붙이므로, 과제의 방향 정합성은 범위 점검이 답으로 본 component 하나 이상으로만 보장된다.
- 복원: PR revert. 기존 게시판·학습 기록은 그대로다.
- 승인 범위(Build): 위 파일의 로컬 구현·검사·실측(로컬 사본, 운영 쓰기 없음)·Draft PR까지.
- 따로 승인: master 병합(=자동 배포), 러너 .runtime 재설치, 261105_03 재출제 요청(새 판 공개 전 과제 수·멈춤 결과 보고).
  학습 기록은 기존 R8 문항 지문 승계(`server/app/root_learning/content.py`)를 따른다. ID만으로 승계하지 않는다.
