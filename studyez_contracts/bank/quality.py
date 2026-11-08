"""Conservative answer-disclosure checks for V1 authoring, plus recall-load measures."""
import html
import re
import unicodedata
from collections import Counter

CHOICE = ("mcq", "multi_select")
# Repeated causal verbs do not disclose which process changes or why.
# "Na 통로 억제 → 활동전위 생성은? / 억제" still requires a causal judgment.
GENERIC_PREDICATES = {"억제", "촉진", "차단", "증가", "감소", "상승", "하강", "활성화", "비활성화"}


def _text(value: str) -> str:
    text = html.unescape(unicodedata.normalize("NFKC", value)).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[*_`]+", "", text)).strip()


def _without_candidates(stem: str, answer: str, question: dict) -> str:
    """Ignore an answer only at an explicit alternative, not elsewhere in prose."""
    spans = []
    basic = question['format'] == 'basic'
    prefix, separator, comparison = stem.partition(' 중 ')
    if separator and (basic or question.get('retrieval_direction') == 'discrimination') \
            and re.search(r'가장|어느|어떤|무엇|어디|어떻게|쪽|고르|선택|판단|분류', comparison):
        separators = list(re.finditer(r'[·,/]|(?:와|과)\s+', prefix))
        boundaries = [0] + [m.end() for m in separators]
        ends = [m.start() for m in separators] + [len(prefix)]
        parts = [prefix[start:end].strip() for start, end in zip(boundaries, ends)]
        if len(parts) >= 2 and all(parts) and len(set(parts)) >= 2:
            for start, end in zip(boundaries, ends):
                piece = prefix[start:end].rstrip()
                if piece.strip() == answer or piece.endswith(' ' + answer):
                    # Preserve preceding context: an earlier asserted answer
                    # must still be detected even when the last term is a choice.
                    spans.append((start + len(piece) - len(answer), start + len(piece)))
    if basic:
        for match in re.finditer(r'(?P<a>[^\s,?]+?)인가\s*[,?]\s*(?P<b>[^\s,?]+?)인가', stem):
            if match['a'] != match['b']:
                spans.extend(match.span(k) for k in ('a', 'b') if match[k] == answer)
    for start, end in sorted(set(spans), reverse=True):
        stem = stem[:start] + ' ' * (end - start) + stem[end:]
    return stem


def leaked_units(question: dict) -> list[str]:
    """Conservative literal disclosure check, never applied to choice candidates."""
    if question["format"] not in ("basic", "cloze", "list"):
        return []
    stem = _text(question["question"])
    found = []
    for unit in question["answer_units"]:
        answer = _text(unit)
        # A one-letter symbol or a one-syllable suffix is not useful evidence.
        if len(answer) < 2 or answer in GENERIC_PREDICATES:
            continue
        boundary = (r"(?<![a-z0-9])" if answer[0].isascii() and answer[0].isalnum() else "")
        boundary_end = (r"(?![a-z0-9])" if answer[-1].isascii() and answer[-1].isalnum() else "")
        if re.search(boundary + re.escape(answer) + boundary_end, _without_candidates(stem, answer, question)):
            found.append(unit)
    return found


# ── 분포 표시 ────────────────────────────────────────────────────────────────
# 아래 선은 규칙이 아니라 **건강한 모집단의 꼬리**다. 2026-11-08 운영 Quiz Bank
# 35편 3,103문항에서 쟀다(웹 정본 프롬프트로 만든 것):
#   basic 정답 길이   p50=15  p97=49  p99=59  최대 84
#   list  채점 단위    p50=10  p97=32  p99=46  최대 73
#   list  정답 전체    p50=30  p97=92  p99=112
#   list  단위 수      p97=5   최대 6
#   cloze 0인 편 1/35 · 객관식(mcq+multi_select) 0인 편 0/35
# 같은 자를 2026-11-07 Main-Quiz 한 편(감염성 질환의 병리 1, 98문항)에 대면
# basic>50자 15.8%, 단위>30자 16.4%, cloze·객관식 0개였다.
# 선에 걸린 문항은 **떨어뜨리지 않는다**(경고만). 판단은 사람과 gate 가 한다.
LONG_ANSWER_CHARS = {"basic": 50, "list": 90}
LONG_UNIT_CHARS = 30
MAX_ANSWER_UNITS = 6
NARROW_FORMAT_MIN_QUESTIONS = 20
POLARITY_MIN_QUESTIONS = 3

# 정본 §3.5 는 단정어를 일괄 금지하지 않는다. 그래서 단어가 아니라 **단서와 정답의
# 상관**을 잰다 — 단정어가 든 발문의 답이 늘 한쪽이면 지식 없이 맞힌다.
OVERSTATEMENT = ("반드시", "항상", "모두", "모든", "결코", "오직", "만으로", "예외 없",
                 "전혀", "절대", "언제나", "무조건", "라는 이유만")
# 한 글자 O/X 는 ox 정답일 때만 극성이다. basic 정답 "Olaparib"·"O₂"·"OCT1" 은
# 극성이 아니다 — 2026-11-08 운영 은행에서 이 자리를 34번 잘못 짚었다.
_NEGATIVE = re.compile(r"^(아니|없|불가|틀리|거짓|.{0,10}수 없)")
_AFFIRMATIVE = re.compile(r"^(예[.,!]|예$|그렇|맞다|맞습|있다|가능|참[.,!]|참$)")
_LENGTH_FORMATS = ("basic", "list")


def answer_polarity(question: dict) -> str | None:
    """예/아니오로 답하는 문항인가 — `'neg'` · `'pos'` · `None`.

    cloze 의 answer 는 빈칸을 채운 문장 전체라 여기서 보지 않는다(프레임은 재지 않는다).
    """
    if question["format"] == "ox":
        return {"o": "pos", "x": "neg"}.get(_text(question["answer"]))
    if question["format"] not in _LENGTH_FORMATS:
        return None
    head = re.split(r"[.;]", _text(question["answer"]), maxsplit=1)[0].strip()
    if _NEGATIVE.match(head):
        return "neg"
    if _AFFIRMATIVE.match(head):
        return "pos"
    return None


def _yes_no_axis(question: dict) -> list[str]:
    """basic·list 가 예/아니오로 답하고 있는가.

    하나의 판단은 ox 의 자리다(정본 §3.5). basic 으로 두면 질문 축이 사라져
    남은 문장 구조만으로 답이 드러난다 — 정본 §2.1 이 금지하는 모양이다.
    운영 Quiz Bank 1,813문항에서는 1건(0.06%)이고, 2026-11-07 Main-Quiz 한 편에서는
    97문항 중 6건(6.2%)이었다.
    """
    if question["format"] not in _LENGTH_FORMATS or not answer_polarity(question):
        return []
    return [f"{question['question_id']}: {question['format']}인데 예/아니오로 답한다 — "
            f"하나의 판단은 ox로 내고, 직접 회상이면 질문 축을 바꾼다"]


def recall_chars(question: dict) -> int:
    """학생이 실제로 적어 내는 글자 수. 공백은 세지 않는다."""
    return len(re.sub(r"\s+", "", _text(question["answer"])))


def _recall_load(question: dict) -> list[str]:
    """한 문항의 회상 부담. cloze·객관식은 재지 않는다."""
    fmt = question["format"]
    if fmt not in _LENGTH_FORMATS:
        return []
    found = []
    chars, line = recall_chars(question), LONG_ANSWER_CHARS[fmt]
    if chars > line:
        found.append(f"정답 {chars}자(선 {line}자)")
    # basic 의 채점 단위는 정답 하나뿐이다. 단위 길이는 **여러 단위를 한 문항에서 회상하는**
    # list 에만 묻는다 — basic 에 같은 선을 대면 위의 정답 길이 선이 뜻을 잃는다.
    long_units = ([u for u in question["answer_units"] if len(u.strip()) > LONG_UNIT_CHARS]
                  if fmt == "list" else [])
    if long_units:
        found.append(f"{LONG_UNIT_CHARS}자 넘는 채점 단위 {len(long_units)}개")
    if len(question["answer_units"]) > MAX_ANSWER_UNITS:
        found.append(f"채점 단위 {len(question['answer_units'])}개(선 {MAX_ANSWER_UNITS}개)")
    if not found:
        return []
    return [f"{question['question_id']}: 회상 부담이 크다 — {', '.join(found)}. "
            f"cloze·객관식으로 나눌지 검토"]


def _basic_units(question: dict) -> list[str]:
    """basic 은 정답 하나를 회상하는 형식이다(정본 §3.5). 여러 채점 단위면 형식이 틀렸다.

    운영 Quiz Bank 35편 basic 1,240문항 중 단위 2개 이상은 6개(0.5%)였고, 2026-11-08
    Map 파이프라인 감염병리1 83문항 판에서는 basic 72개 중 62개였다 — 「A·B와 한계는?」처럼
    여러 요구를 한 발문에 묶은 것이다.
    """
    if question["format"] != "basic" or len(question["answer_units"]) < 2:
        return []
    return [f"{question['question_id']}: basic인데 채점 단위 {len(question['answer_units'])}개 — "
            f"같은 범주 항목이면 list, 대응·비교면 cloze 표·객관식, 서로 다른 요구면 문항을 나눈다"]


def _ox_reason(question: dict) -> list[str]:
    """ox 는 판단보다 이유를 아는 것이 목표다(2026-11-08 관리자). 이유는 해설에 있다.

    운영 Quiz Bank ox 137개 중 60개(44%)가 해설 없이 O/X만 남겼다.
    """
    if question["format"] != "ox" or (question.get("explanation") or "").strip():
        return []
    return [f"{question['question_id']}: ox인데 해설이 없다 — 왜 O 또는 X인지 핵심 근거를 해설에 쓴다"]


def _polarity_bias(bank: dict) -> list[str]:
    """예/아니오 문항의 정답이 한쪽으로만 쏠렸는가. 정본 §2.1 의 「정답 단서」다."""
    groups: dict[str, list[str]] = {}
    for q in bank["questions"]:
        side = answer_polarity(q)
        if side:
            groups.setdefault(side, []).append(q["question_id"])
    total = sum(len(v) for v in groups.values())
    if total < POLARITY_MIN_QUESTIONS or len(groups) != 1:
        return []
    side, ids = next(iter(groups.items()))
    label = "부정" if side == "neg" else "긍정"
    return [f"예/아니오로 답하는 문항 {total}개의 정답이 모두 {label}이다 — "
            f"발문 구조만 보고 맞힐 수 있다: {', '.join(ids)}"]


def _overstated_cue(question: dict) -> list[str]:
    """단정어가 든 발문에 부정 정답. 단어 자체는 금지가 아니다 — 겹칠 때만 적는다."""
    if answer_polarity(question) != "neg":
        return []
    stem = _text(question["question"])
    hit = [cue for cue in OVERSTATEMENT if cue in stem]
    if not hit:
        return []
    return [f"{question['question_id']}: 발문의 단정어({', '.join(hit)})와 부정 정답이 겹친다 — "
            f"지식 없이 판별될 수 있음"]


def _narrow_format(bank: dict, long_ids: list[str]) -> list[str]:
    """정답이 긴 문항이 있는데 cloze·객관식을 한 번도 쓰지 않았는가."""
    counts = Counter(q["format"] for q in bank["questions"])
    total = sum(counts.values())
    if total < NARROW_FORMAT_MIN_QUESTIONS or not long_ids:
        return []
    missing = []
    if not counts["cloze"]:
        missing.append("cloze 0개")
    if not counts["mcq"] + counts["multi_select"]:
        missing.append("객관식 0개")
    if not missing:
        return []
    return [f"형식이 좁다: {total}문항에 {' · '.join(missing)} — 회상 부담이 큰 문항 "
            f"{len(long_ids)}개를 cloze·객관식으로 돌릴 자리를 찾지 못했다"]


def quality_errors(bank: dict) -> tuple[list[str], list[str]]:
    """New authoring checks leave existing 3.0 banks valid.

    2026-11-08 부터 정답 노출 외에 세 가지를 **측정만** 한다 — 구조 단서와 정답의
    상관, 정답의 회상 부담, 형식 쏠림. 전부 warnings 라 문항을 떨어뜨리지 않고
    repair 단계 입력(`validation`)과 관리자 화면의 issues 로 돌아간다.
    """
    if bank["build_meta"]["schema_version"] not in ("3.1", "3.2", "3.3"):
        return [], []
    errors, warnings = [], []
    long_ids = []
    for q in bank["questions"]:
        disclosed = leaked_units(q)
        if disclosed and len(disclosed) == len(q["answer_units"]):
            errors.append(f"{q['question_id']}: 발문에 모든 정답 단위 노출 — 복사로 답할 수 있음")
        elif disclosed:
            warnings.append(f"{q['question_id']}: 발문에 일부 정답 단위 노출 가능 — {', '.join(disclosed)}")
        load = _recall_load(q)
        if load:
            long_ids.append(q["question_id"])
        warnings += load + _basic_units(q) + _ox_reason(q) + _yes_no_axis(q) + _overstated_cue(q)
    warnings += _polarity_bias(bank) + _narrow_format(bank, long_ids)
    return errors, warnings
