# 과제 — 카드를 실제로 풀어 본다

아래에는 카드의 앞면 텍스트만 있다. 정답·해설·원본 자료를 보지 않고 질문이 요구하는
만큼만 간결하게 답한다.

- {domain_knowledge}으로 풀되 원본 자료를 찾지 않는다.
- 무엇을 묻는지 알 수 없거나, 선지·그림·조건이 없어 답이 하나로 정해지지 않으면
  `answerable=false`로 표시하고 이유를 적는다.
- 성립하는 질문이지만 확신이 낮으면 최선의 답을 쓰고 confidence를 낮춘다.
- `[...]`는 가려진 빈칸이고 `[O/X]`는 참·거짓 진술이다.

아래 경로에 JSON만 쓴다.

```json
{"answers": [
  {"id": "c001", "answerable": true, "answer": "...", "confidence": "high"},
  {"id": "c002", "answerable": false, "answer": "", "confidence": "low",
   "why_not": "답을 정하는 조건이 없다"}
]}
```

`confidence`는 `high | medium | low` 중 하나다.

    {out}
