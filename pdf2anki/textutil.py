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


def norm_key(s: str) -> str:
    """공백·장식문자·괄호 형태 차이를 지운 비교용 키."""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s\*★·:()~\-–—]", "", s)


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
