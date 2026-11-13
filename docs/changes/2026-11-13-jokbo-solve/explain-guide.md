# 족보 해설 작성 안내 (jokbo-explain/1)

족보 세트 하나의 문항마다 해설을 쓴다. 문항 원문·선지 순서·정답표는 바꾸지 않는다.
결과는 git 밖에만 쓴다(족보는 제3자 저작물, 저장소는 공개).

## 입력

```bash
python -m runner.jokbo_solve pack <setId>
```

세트 제목, 강의 번호, 문항(발문·선지·답안지 답·답 메모·반복 연도), 그림 파일 경로가 나온다.
그림이 있는 문항은 **그림을 직접 열어 본 뒤** 쓴다.

근거 자료(강의 번호 = 시간표 「감염과 면역 N」):

- 올해 필기: `~/SynologyDrive/감염과 면역/필기/2026/[YYMMDD_NN] 제목(교수)_필기자.pdf`
- 작년 필기: `~/SynologyDrive/감염과 면역/필기/2025/1차/`
- amgi 필기 텍스트(있으면 빠름): `pack` 출력의 `notes`
- PDF 글자 추출: `python -c "import fitz,sys; d=fitz.open(sys.argv[1]); [print('==p',i+1,'\n',p.get_text()) for i,p in enumerate(d)]" <pdf>`

올해 필기를 먼저, 없으면 작년 필기를 본다. 필기에 근거가 없으면 일반 의학 지식으로 쓰고
`basis.kind = "knowledge"`로 표시한다.

## 출력

`runs/_materials/감염과 면역/jokbo-solve/explain/<setId>.json`

```json
{
  "_meta": {"schema": "jokbo-explain/1", "notes": ["사용한 필기 파일 이름"]},
  "<pastExamItemId>": {
    "text": "해설 본문",
    "choiceNotes": ["선지 1에 대한 한 줄", "…선지 수만큼"],
    "caution": "확정 못 한 점(없으면 키를 뺀다)",
    "basis": {"kind": "notes", "pages": [12, 13]},
    "answerCheck": "agree",
    "proposedAnswers": [3]
  }
}
```

| 필드 | 규칙 |
|---|---|
| `text` | 왜 그 답인지 핵심 기전·구분을 2~5문장. 한국어, 용어는 원어 병기. 인사·칭찬·“좋은 문제” 같은 군말 없음 |
| `choiceNotes` | 선지 수와 같은 길이·같은 순서. 정답 선지는 「정답.」으로 시작. 오답은 무엇이 틀렸는지·그 선지가 실제로 맞는 대상 |
| `caution` | 답안지 답 의심, 필기에 없는 선지, 그림 판독 한계, 판본·교수에 따라 갈리는 내용. 없으면 키를 뺀다 |
| `basis` | `notes`(필기 근거, `pages`에 필기 PDF 쪽) 또는 `knowledge` |
| `answerCheck` | `agree` 답안지 답이 맞다 / `doubt` 근거상 다른 답이 맞아 보인다 / `no-key` 답안지에 답이 없다 |
| `proposedAnswers` | `no-key` 문항에만. 확신할 때만 적고 `caution`에 「답안지에 답이 없어 추정」 근거를 쓴다 |

- 답안지 답은 고치지 않는다. 의문은 `doubt` + `caution`(무엇이 왜 다른지, 근거 쪽)으로만 드러낸다.
- 전원정답(`answerText`가 「전원정답」·「모두 정답」)은 `agree`로 두고, 각 선지가 왜 맞을 수 있는지 쓴다.
- 인정 답이 여럿(`answerMode`)인 문항은 인정된 답 모두가 왜 맞는지 쓴다.
- 선지 없는 문항은 `choiceNotes`를 뺀다.

## 원천 오류 교정 (fixes)

선지 분할·합쳐짐, 다른 문항 그림, 그림 누락, 다른 강의 세트에 들어간 문항, 근거가 분명한 정답 오기는
고친다. **원본 족보 PDF로 확인한 것만** 고친다.

- 원본: `~/amgi/2025 감염과 면역 족보.pdf`(2020~2025), `~/amgi/2022 감염과 면역 족보 본문.pdf`,
  `~/SynologyDrive/감염과 면역/족보/<연도>/`. 쪽 찾기: `python -c "import fitz,sys; d=fitz.open(sys.argv[1]); [print(i+1) for i,p in enumerate(d) if sys.argv[2] in p.get_text()]" <pdf> "<발문 일부>"`
- 쪽 그림 보기: `python -c "import fitz,sys; d=fitz.open(sys.argv[1]); d[int(sys.argv[2])-1].get_pixmap(dpi=110).save(sys.argv[3])" <pdf> <쪽> <scratch.png>` 후 Read.

`runs/_materials/감염과 면역/jokbo-solve/fixes/<setId>.json`

```json
{
  "<pastExamItemId>": {
    "note": "무엇을 왜 고쳤는지 한 문장(채점 뒤 화면에 보인다)",
    "evidence": "2025 감염과 면역 족보.pdf p.106 (문항·답안지), 필기 p.48",
    "choices": ["원본대로 다시 나눈 선지 전부"],
    "answers": [2],
    "figures": ["pe_2022_0c_028-2.png", "pe_2022_0c_028-1.png"],
    "moveTo": ["30"],
    "stemReplace": [["깨진 글자", "고친 글자"]]
  }
}
```

| 키 | 언제 |
|---|---|
| `choices` | 원본과 선지 수·경계가 다를 때. 원본 글자 그대로, 순서 유지 |
| `answers` | 답안지 오기가 **원본 PDF·같은 문항 다른 해 답·필기 족보 정답표** 중 둘 이상으로 확인될 때만. 원래 답은 빌드가 `originalAnswers`로 보존한다. 판단만으로는 고치지 말고 `doubt`로 둔다 |
| `figures` | 그림 목록을 통째로 바꾼다(순서·다른 문항 그림 제거). 원본에서 잘라 낸 새 그림은 `fixes/figures/<pastExamItemId>-<n>.png`로 저장하고 이름만 적는다 |
| `moveTo` | 다른 강의 내용이 잘못 들어간 문항을 시간표 강의 번호(`"30"`, `"CBL 1"`)로 옮긴다 |
| `stemReplace` | 스캔·복원으로 깨진 글자. 뜻이 바뀌는 수정 금지 |

정답을 고친 문항의 해설은 고친 답 기준으로 쓰고 `answerCheck: "agree"`, `caution`에 「답안지 원래 답 N → 고침, 근거」를 남긴다.
선지를 다시 나눈 문항은 `choiceNotes`를 새 선지 수에 맞춰 다시 쓴다.

## 이미 있는 해설 점검

`pack` 출력의 `existingExplanation`이 있으면 처음부터 다시 쓰지 말고 점검한다.

- 의학적으로 틀린 말, 필기와 어긋나는 말, 선지 노트 순서·개수 불일치, 그림과 맞지 않는 해설을 고친다.
- 해설이 지적한 오류(선지 분할·그림·정답)가 위 교정 기준에 맞으면 `fixes`로 고치고 해설을 맞춘다.
- `doubt` 문항은 원본 PDF로 확인해 고치거나(`answers`), 근거가 모자라면 `doubt`로 남긴다.
- 고친 문항 id와 이유를 마지막 보고에 적는다. 고칠 것이 없으면 그대로 둔다.

## 「정답.」 표시

`choiceNotes`의 「정답.」은 **채점 기준 답**(`answers`, 교정했으면 고친 답)에만 붙인다.
`doubt`로 남기는 문항에서 근거상 맞아 보이는 다른 선지는 「근거상 정답일 수 있음.」으로 시작한다.

## 여러 강의를 묶은 세트(7-8, 25-28)

문항마다 어느 강의 내용인지 `runs/_materials/감염과 면역/jokbo-solve/assign/<setId>.json`에 적는다.
`{"<pastExamItemId>": "25"}`처럼 쓰고, 두 강의에 걸치면 `["25", "26"]`로 쓴다. 강의 번호는 세트의
`lectures` 안에서만 고른다. 적지 않은 문항은 묶음의 모든 강의에 남는다.

## 확인

```bash
python -m runner.jokbo_solve build
```

여럿이 동시에 쓸 때는 빌드 대신 세트 하나만 검사한다: `python -m runner.jokbo_solve check <setId>`.
`missingExplain`·`unknownIds`·`problems`가 비어야 하고(선지 범위 밖 답 경고는 교정 전까지 남는다), 묶음 세트는 `unassigned`도 비어야 한다.
