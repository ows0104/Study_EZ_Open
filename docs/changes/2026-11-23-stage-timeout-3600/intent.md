# /4 Codex 단계 시한 3600초

## 문제와 사용자 효과
사용자 「혹시 모르니 타임리밋을 좀 더 올리자」(2026-11-23 21:4x).
같은 날 261123_01 면역약리학 Main-Quiz(job 728, generation 51637d39…)가 normalize 단계에서 실패했다.
- normalize는 20:05:56에 시작했다. OpenAI 스트림이 네 번 끊겼고(`idle timeout waiting for websocket`), Codex가 HTTPS로 바꿔 이어 갔다.
- 결과 파일은 20:44:21에 썼지만 완료 확인 전에 2400초가 지나 `[MODEL_TIMEOUT]`으로 보류됐다.
- 같은 시각 통풍·류마티스·루프스는 정상으로 지나갔다. 출제 내용 문제가 아니라 느려진 호출이다.

## 범위와 성공 기준
- /4(root-generation/4) 단계의 Codex 시한 2400 → 3600초. normalize·미리 시작한 normalize·v4-add·review·fix·coverage 등 `NativeJson`을 거치는 모든 Codex 단계.
- Claude 단계 7200초, 편 전체 시한 `BUILD_TIMEOUT` 180분, 앞 단계(`root_front.py` map·point 2400초)와 그 밖의 개별 호출 시한은 그대로.

## 근거·미정 사항
최근 14일 `runs/_root-generation/*/generation/.native` 실측(작업 폴더 input.json → result.json 시각):
normalize 106회 중앙 5.4분·95% 8.0분·최대 38.4분(30분 넘음 4회), v4-review 1,511회 95% 3.7분, v4-fix 986회 최대 18.8분.
3600초면 이번 실패와 같은 지연을 넘기고도 남는다. 편 전체 180분 안이다.
