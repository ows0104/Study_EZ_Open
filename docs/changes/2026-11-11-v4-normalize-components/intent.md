# Main-Quiz /4 정규화: 성분을 따로 채점할 사실 하나씩

## 문제와 사용자 효과

아데노·폭스바이러스(방예지, 261113_01) Main-Quiz 운영 실행(2026-11-11, root-generation/4,
`runs/_root-generation/6e5c581a8a334974b47cba85718e7ef5`)은 첫 은행 92문항에 114문항을 더해 206문항이 됐다.
약 96분 중 문항 추가·추가분 검토·수정이 대부분이었고, 같은 내용을 다시 묻는 쌍이 10개쯤 생겼다
(Q001/Q095, Q005/Q108, Q081/Q160, Q123/Q179, Q188/Q203 등).

원인은 normalize 출력의 성분(component)이다.

- 방향 140개 모두 component가 1개였다. 포인트 문장이나 answer_scope 전체를 한 component에 그대로 옮겼다.
  - 예: D001 「비외피 정이십면체 캡시드; 약 36 kb 선형 dsDNA; 5′ 말단 terminal protein.」이 component 하나
  - 23개 방향은 「일반화하지 않는다」「구별한다」 같은 해석상 주의까지 component에 들어갔다.
    지시문(extract-v2.md)은 이런 내용을 notes/scope에 두라고 한다.
  - recall_units를 쓴 방향은 0개였다.
- /4 누락 점검(coverage.md)은 component의 합집합으로 충족을 판정한다. component가 문장 통째이면
  한 문항이 문장 전체를 답해야만 충족되고, 여러 문항이 나눠 물은 것은 「부분」이 된다.
  - 첫 점검: 140개 중 covered 28, missing 112. missing 112개 중 103개는 일부를 묻는 기존 문항이 있었다.
  - 포인트에서 온 방향(D) 94개 중 73개가 missing이었다. 은행은 같은 포인트로 만들었는데도 그렇다.
- 문항 추가(v4-add-0)는 missing 방향마다 한 문항을 만들었다. 112문항 중 103개는 발문이 방향 cue와 같고,
  111개는 정답이 answer_scope와 같다.
- 지도 관계에서 만든 방향(DM) 46개 중 37개는 cue가 「X와 Y의 관계·구별 또는 판단 한계는?」 틀이었고 39개가 missing이었다.

리케차(261110_03, `fa71412a…`)도 방향 86개 중 79개가 component 1개, 첫 점검 missing 51개, 추가 54문항이었다.

사용자 2026-11-11: 「문항추가가 왜 이렇게 많이 된거야??」 → 원인 설명 → 「여기서 고쳐줘」 → 계획 제시 → 「계획 승인」.

## 범위와 성공 기준

- root-generation/4의 normalize만 새 지시문(`content/prompts/learning-links/v4/normalize.md`)을 쓴다.
  /2·/3의 normalize와 `automation/extract-v2.md`는 그대로다.
- 성공 기준: 261113_01의 저장된 normalize 입력으로 새 지시문을 재생했을 때
  - 여러 사실을 묶은 방향이 component 여러 개로 나뉘고,
  - 같은 첫 은행 92문항에 대한 첫 누락 점검의 missing이 112개보다 크게 줄어든다.
  수치 목표는 정하지 않는다. 재생 결과를 release.md에 기록한다.

## 근거·미정 사항

- 코드로 answer_scope를 「;」 등으로 쪼개는 길은 택하지 않는다.
  `studyez_contracts/roots/recall_units.py`는 「텍스트나 길이로 분할을 추정하지 않는다」를 원칙으로 둔다.
- 모델이 지시를 따르는지는 재생으로만 확인할 수 있다. 재생 한 번은 표본 하나다.
- 이번 변경 밖(별도): 같은 실행의 조립 보류(`importance_basis.refs` 중복, v4-add-0 출력)는 사용자가 「나중에」로 미뤘다.
  brief-fix가 「점검 비교에서 빠진 목표」를 answer_scope 복사로 채운 일(46개)도 이번 범위가 아니다.
