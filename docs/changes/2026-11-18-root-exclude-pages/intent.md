# Main-Quiz 운영자 제외 쪽(page-withhold/1)과 261109_02 재출제

## 문제와 사용자 효과
감염과 면역 `261109_02`(레지오넬라, 리스테리아, 바실루스(석승혁)) Main-Quiz를 새로 받고 싶다.
- 11-12~14 GPT 판(v1 필기)은 normalize 단계에서 OpenAI 콘텐츠 제한 거절 3번으로 실패했다(job 598, generation `d4b5c7e6…`).
- 11-15 Claude 판(v2 필기)은 게시됐다(job 620, generation `2bcdcf1f…`, operator-exclusions/1로 두 문항 제외).
- 11-16 보강 job 660(`a2dee040…`)은 사람이 멈췄다(canceled).

사용자는 필기의 일부 쪽(바실루스 단원 일부, v2 필기 S1 36~48쪽)을 빼고 GPT로 처음부터 다시 내기로 했다.
지금 러너에는 원본 PDF의 특정 쪽을 모델에 보내지 않는 길이 없다.
- `runner/root_front.py` `prepare`는 packet `sources`를 지문 확인 뒤 그대로 스냅샷한다.
- 생성기(`quizbank.connection_generate.prepare`)와 게시 뒤 근거 보강(`quizbank.evidence_sources.prepare`)도 같은 원본을 통째로 그린다.

## 범위와 성공 기준
- 강의별 운영자 기록 `runs/page-exclusions.json`에 「이 강의의 이 자료(자산 ID+원본 지문)에서 뺄 쪽」을 이유·승인 발언·시각과 함께 적는다.
  그러면 그 강의의 Main-Quiz 요청에서 앞 단계·생성기·근거 보강이 그 쪽이 빠진 사본만 읽는다.
- 쪽 번호는 원본 그대로 둔다. 인용·그림 쪽·대조의 쪽 검토·게시된 근거 지면이 원본 쪽 번호와 어긋나지 않는다.
- 사이트의 필기 파일, 서버 packet·지문, `runs/model-overrides.json`은 바뀌지 않는다. 기록이 없는 강의는 지금과 똑같이 돈다.
- 261109_02를 GPT(기본 Codex 경로)로 restart + replacePublished 하고, 새 판 게시와 공개판 교체를 운영 DB 읽기로 확인한다.
  거절이 나면 두 번쯤에서 멈추고 사람에게 넘긴다.

## 근거·미정 사항
사용자 결정(2026-11-18). 이 세션을 연 세션(local_d10e0b8e…)이 사용자에게서 받아 이 세션에 넘긴 것이다.
- 모델: GPT(기본 Codex 경로). 이 새 generation 행을 `runs/model-overrides.json`에 쓰지 않는다(Claude 지정 금지).
- 자료: 현재 notes_current 자산인 손지민 v2 PDF(76쪽, asset `d74531e7-4361-48f3-a8a2-528ee82db339`)와 족보 그대로.
  사이트에 올라간 필기 파일은 바꾸지 않는다.
- 빼는 쪽: v2 필기 S1의 36~48쪽만. 34·35·52·72쪽은 남긴다.
- 공개판 교체: 사용자 「교체한다」. restart + replacePublished, 현재 공개판 `auto-2bcdcf1f3feb4542938e66882c46875f`(학습 세션 3건).

미정: 없음. 제외 쪽을 가리키는 인용이 결과에 남으면 막지 않고 `withheld-citations.json`과 로그 경고로 센다(spec R5).
