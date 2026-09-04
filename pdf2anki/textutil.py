"""문자열 정규화 도구. jokbo/validate 가 같은 규칙을 쓰도록 한 곳에 둔다.

유사도 지표가 두 개인 이유:

  word_tokens  어절 단위. 거의 같은 문장을 찾을 때 쓴다 (족보 연도간 문항 재활용).
  char_ngrams  글자 2-gram. 한국어는 조사가 붙어 어절이 갈리므로
               '합성' 과 '합성을' 을 같게 보려면 이쪽이 필요하다.
"""

from __future__ import annotations

import re
import unicodedata

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"

# 회수 목표를 구분하지 못하는 상투어. 두 지표 모두에서 뺀다.
BOILERPLATE = re.compile(
    r"고르시오|고르시요|다음\s*중|설명으로|설명이다|설명\s*중|것은|것을|무엇인가|무엇|"
    r"가장|옳은|옳게|틀린|잘못|아닌|하나만|나열|대시오|맞는|적절한|해당하는|"
    r"관한|대한|대하여|모두")
STOPWORDS = {
    "고르시오", "설명", "다음", "옳은", "것은", "틀린", "가장", "아닌", "중에서",
    "하나만", "무엇", "무엇인가", "대하여", "대한", "관한", "적절한", "해당하는",
    "이다", "한다", "하는", "되는", "있는", "없는", "모두",
}


RE_CLOZE_NUM = re.compile(r"\{\{c\d+::")


def collapse_cloze(q: str) -> str:
    """빈칸 번호를 전부 `c1` 로 모은다 — 한 노트가 카드 한 장이 되게.

    Anki 는 **번호 하나에 카드 한 장**을 만들고, 각 카드는 나머지 번호의 답을
    앞면에 그대로 인쇄한다. `c1..c4` 로 나뉘면 카드가 네 장이 되고 그 넷 모두
    앞면에 답 셋이 적혀 있다. 2026-09-04 에 세어 보니 `runs/` 의 cloze 64장 중
    **39장(61%)이 번호가 갈려 있었고**, 갈린 것 대부분이 한 축이었다
    (amastigote→promastigote→epimastigote→trypomastigote 같은 나열).

    재현 검사는 이미 **모든 빈칸이 함께 가려진 앞면**을 채점하고 있었다
    (`reproduce.front_of`). 즉 채점한 앞면과 실제로 구워지던 앞면이 달랐다.
    여기서 모으면 둘이 같아진다.

    번호를 지우는 것이지 빈칸을 지우는 것이 아니다 — 가린 자리 수는 그대로라
    `too_many_clozes` 계수기는 영향을 받지 않는다. `norm_key` 는 껍데기를
    통째로 벗기므로 **guid 도 바뀌지 않는다**(복습 이력이 보존된다).
    """
    return RE_CLOZE_NUM.sub("{{c1::", q)


def norm_key(s: str) -> str:
    """공백·장식문자·괄호 형태 차이를 지운 비교용 키."""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s\*★·:()~\-–—]", "", s)


# 정답 글자가 그림 안에 인쇄돼 있을 때, 그것을 이루는 낱말 구간. 앞면을 가리는 쪽과
# 누출을 세는 쪽이 **같은 함수를 본다** — 둘이 갈리면 가린 것을 또 누출로 세거나
# 그 반대가 된다.
ANSWER_RUN_MIN = 5


def answer_runs(words: list[str], answer: str, min_len: int = ANSWER_RUN_MIN) -> list[tuple[int, int]]:
    """정답이 그대로 인쇄된 낱말 구간 `[start, end)` 들.

    이어 붙인 낱말과 정답을 **양방향으로** 견준다 — 낱말이 정답의 일부이거나, 낱말이
    정답을 통째로 품거나(`Neurofibroma` 에 대한 `Neurofibromas`). 한쪽만 보면 가리는
    쪽과 누출을 세는 쪽이 어긋나, 가리지 못한 것을 계속 누출로 세게 된다.
    **낱말 목록을 쓰지 않는다** — 무엇을 가릴지는 그 카드의 정답이 정한다.

    길이 문턱을 두는 이유는 `cell` 처럼 짧은 조각이 정답의 일부이면서 그림 안 여기저기에
    우연히 있기 때문이다. 문턱 아래는 가리지 않는다 — **덜 가리는 쪽이 잘못 가리는 쪽보다 낫다.**
    """
    # `norm_key` 는 대소문자를 남긴다(오클루전 라벨 대조가 그 상태를 쓴다). 그림에 인쇄된
    # 캡션은 대문자로 시작하는 일이 잦으므로 여기서만 내려서 견준다.
    def key_of(s: str) -> str:
        return norm_key(s).lower()

    key = key_of(answer)
    if not key or not words:
        return []
    runs, i = [], 0
    while i < len(words):
        best, joined = 0, ""
        for j in range(i, len(words)):
            joined += key_of(words[j])
            if key in joined:
                best = j + 1          # 정답을 다 품었다. **여기서 끊는다** — 더 이으면
                break                 # 뒤따르는 낱말까지 덮어 그림을 갉아먹는다
            if joined and joined in key:
                best = j + 1          # 아직 정답의 일부다. 더 이어 볼 수 있다
                continue
            break                     # 더 이어도 정답에서 멀어지기만 한다
        matched = key_of("".join(words[i:best])) if best > i else ""
        if matched and min(len(matched), len(key)) >= min_len:
            runs.append((i, best))
            i = best
        else:
            i += 1
    return runs


def _strip(s: str) -> str:
    # 자모가 풀린(NFD) 한글은 `[가-힣]` 에 걸리지 않아 통째로 사라진다. Synology 를
    # 거친 파일명 일부가 실제로 NFD 였고, 그 강의만 조각 대조가 조용히 0점이 됐다.
    s = unicodedata.normalize("NFC", s)
    s = re.sub(rf"[{CIRCLED}]", " ", s)
    s = re.sub(r"\{\{c\d+::(.*?)(?:::.*?)?\}\}", r"\1", s)   # cloze 껍데기 제거
    return BOILERPLATE.sub(" ", s)


def word_tokens(s: str) -> set[str]:
    """어절 단위 토큰. 거의 동일한 문장 탐지용."""
    toks = re.findall(r"[A-Za-z]{3,}|[가-힣]{2,}", _strip(s))
    return {t.lower() for t in toks if t not in STOPWORDS}


def char_ngrams(s: str, n: int = 2) -> set[str]:
    """라틴 어절 + 한글 글자 n-gram. 조사 변화에 견딘다."""
    s = _strip(s)
    out = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", s)}
    hangul = re.sub(r"[^가-힣]", "", s)
    out |= {hangul[i:i + n] for i in range(len(hangul) - n + 1)}
    out |= {m for m in re.findall(r"\d+(?:\.\d+)?", s)}
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def containment(small: set[str], big: set[str]) -> float:
    """small 이 big 에 얼마나 담겨 있는가. 정답 노출 검사에 쓴다."""
    if not small:
        return 0.0
    return len(small & big) / len(small)
