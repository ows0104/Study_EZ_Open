"""객관식 학습 목적. 새 문항은 명시하고 옛 문항만 기존 회수 방향으로 보완한다."""
import re


def choice_mode(question: dict) -> str:
    if question.get("format") not in ("mcq", "multi_select"):
        return "none"
    explicit = question.get("mcq_mode")
    if explicit in ("recall_first", "comparison"):
        return explicit
    stem = question.get("question", "")
    stem = stem if isinstance(stem, str) else ""
    # 기존 은행의 구분·함정·통합 문항, 선지의 옳고 그름·최상위 비교는 먼저 보기를 보여 준다.
    comparison = question.get("retrieval_direction") in ("discrimination", "trap", "integration") or re.search(
        r"다음|가장|옳은|옳지|틀린|모두|중에서|\b(?:following|which of|most|least|except|all that)\b", stem, re.I)
    return "comparison" if comparison or question.get("format") == "multi_select" else "recall_first"
