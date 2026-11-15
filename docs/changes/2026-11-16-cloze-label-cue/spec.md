# 빈칸 묶음 선지에서 정답에만 붙은 항목 머리 떼기 — 설계

## 요구사항과 수용 기준
`tests/quizbank/test_root_mcq.py::test_빈칸_정답의_항목_머리가_발문에_있으면_선지에는_값만_보인다` —
결핵 표 문항은 값만, 머리가 발문에 없거나·비율·일부만 머리인 경우는 원문, 이름 안 쌍점(「E. coli O157:H7: 혈청형」)은 가장 긴 머리까지 뗀다.

## 책임·입출력 계약·오류 상태
`studyez_contracts/roots/mcq.py`의 `groups()` cloze 갈래만 `_cloze_values()`를 거친다. 정답 선지 글·`answer_choices`·
정답 ID(`choice_id`, 글에서 만든 해시)가 같이 바뀌어 앞면 선지와 답면 `mcqCorrectIds`는 어긋나지 않는다.
러너(`quizbank/root_mcq.py`)가 오답을 만들 때 보는 묶음 정답도 값만 받는다.

## 호환성과 데이터 보존
문항·판·asset·학습 기록·DB를 바꾸지 않는다. 로컬 `runs/_root-generation/*/mcq` 실측(2026-11-16): 묶음 cloze 1,110문항 중
40문항이 바뀌고 그중 16문항에 올라간 오답 풀이 있다. 전 asset `validate_v2` 통과, 붙지 못하게 되는 문항 0.
바뀐 문항의 정답 선지 ID가 바뀌지만 선지 ID는 저장하지 않고 화면에서만 쓴다.
