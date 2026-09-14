"""족보 컷의 판 기록 (`docs/runs-layout.md` 3단계).

2026-09-14 에 `out/` 의 재생성본 25편을 배포 중인 판과 맞대 보니 **족보참조 카드가
25편 전부 줄어** 있었는데(중앙 -17장), 재료가 안 붙은 것인지 문턱에 걸린 것인지
프롬프트가 달라진 것인지 **구별할 수 없었다.** 그 구별을 가능하게 하는 것이 여기다.

여기서 지키는 것은 넷이다.

    ① 컷이 자기 판을 적는다                     cut.json
    ② 다시 자르면 앞 컷이 `_previous/` 로 간다   덮으면 질문을 못 하게 된다
    ③ 편이 어느 판의 어느 조각을 봤는지 적는다    jokbo.used.json
    ④ **안 붙었으면 그 이유가 남는다**           셋의 처방이 전부 다르다
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from quizgen import cutmark


def _cut(d, *, slices=2, index=True):
    """조각 몇 개와 색인이 있는 컷 폴더를 만든다."""
    d.mkdir(parents=True, exist_ok=True)
    for i in range(slices):
        (d / f"L{i}_강의.json").write_text('{"stats": {}}', encoding="utf-8")
        (d / f"L{i}_강의.md").write_text("# 조각", encoding="utf-8")
    if index:
        (d / "index.json").write_text(json.dumps(
            {"source": "족보.pdf", "lectures": []}), encoding="utf-8")
    return d


# ── ① 판을 적는다 ────────────────────────────────────────────────────
def test_판은_날짜가_아니라_날짜와_시각이다(tmp_path):
    """하루에 두 번 자를 수 있다. 날짜만이면 겹친다."""
    morning = cutmark.new_cut_id(dt.datetime(2026, 9, 14, 1, 30))
    evening = cutmark.new_cut_id(dt.datetime(2026, 9, 14, 23, 12))
    assert morning == "260914-0130"
    assert evening == "260914-2312"
    # 이름 정렬이 곧 시간 정렬이어야 한다 — `_previous/` 를 훑을 때 그것에 기댄다.
    assert sorted([evening, morning]) == [morning, evening]


def test_자른_코드의_판을_내용_해시로_적는다(tmp_path):
    """커밋만으로는 모자란다 — 작업 트리가 더러운 채로 돌리는 일이 흔하다."""
    who = cutmark.cutter()
    assert len(who["code_sha256"]) == 16
    assert "jokbo.py" in who["files"]


def test_원본_지문은_크기와_해시다_mtime이_아니다(tmp_path):
    pdf = tmp_path / "족보.pdf"
    pdf.write_bytes(b"%PDF-1.4 ...")
    mark = cutmark.source_mark(pdf, pages=70)
    assert mark["bytes"] == len(b"%PDF-1.4 ...")
    assert len(mark["sha256"]) == 64
    assert mark["pages"] == 70
    assert "mtime" not in mark        # `runner/fingerprint.py` 가 실측으로 뺀 값이다


def test_판이_없는_옛_컷은_그렇게_말한다(tmp_path):
    d = _cut(tmp_path / "병리학")
    assert cutmark.read(d) is None
    assert "적혀 있지 않다" in cutmark.describe(d)


def test_되짚어_채운_것은_그렇게_표시된다(tmp_path):
    """자른 코드의 판은 되짚을 수 없다. 지금 코드를 적으면 거짓이 된다."""
    d = _cut(tmp_path / "병리학")
    pdf = tmp_path / "족보.pdf"
    pdf.write_bytes(b"x")
    mark = cutmark.write(d, source=pdf, cut_id="260823-0221",
                         cut_at=dt.datetime(2026, 8, 23, 2, 21), backfilled=True)
    assert mark["backfilled"] is True
    assert "unknown" in mark["cutter"]
    assert mark["cut_at"].startswith("2026-08-23")   # 오늘이 아니다
    assert "되짚어 채운 것" in cutmark.describe(d)


# ── ② 판은 서로 형제다 (2026-09-15 · 3′) ──────────────────────────────
#
# 앞 컷을 `_previous/<판>/` 으로 **밀어내던** 자리다. 밀어내는 것 자체가 문제였다 —
# 지금 컷만 과목 폴더에 있어서, 다시 자르면 그 컷이 이사를 갔다. 그 컷으로 만든 덱이
# 적어 둔 `cut_id` 로 폴더를 찾으면 거기 없었다.
#
# 지금은 컷이 처음부터 `<과목>/<판>/` 에 들어가므로 아무것도 움직이지 않는다.

def test_밀어내는_일은_이제_없다(tmp_path):
    """`archive` 는 늘 None 이다. 부르는 자리가 남아 있으면 이 검사가 말한다."""
    d = _cut(tmp_path / "병리학")
    assert cutmark.archive(d) is None
    assert (d / "index.json").is_file()              # 아무것도 안 옮겼다
    assert not (d / cutmark.PREVIOUS).exists()       # 만들지도 않는다


def test_판을_찾는_길이_셋이다(tmp_path):
    """기록된 경로가 셋 다 있다 — 판 폴더 · 과목 폴더 · 옛 모양."""
    subject = tmp_path / "_materials" / "기생충학"
    cut = _cut(subject / "260908-0130")
    assert cutmark.resolve(cut) == cut                      # 판 폴더를 그대로

    cutmark.set_current(subject, "260908-0130")
    assert cutmark.resolve(subject) == cut                  # 과목 폴더 → current

    flat = _cut(tmp_path / "_jokbo" / "병리학")
    assert cutmark.resolve(flat) == flat                    # 옛 모양 — 그 자리다


def test_current가_없는_판을_가리키면_제일_새것으로_내려간다(tmp_path):
    """사람이 그 파일을 손으로 고쳤거나 판을 지운 경우. 조용히 안 읽는 것보다 낫다."""
    subject = tmp_path / "_materials" / "기생충학"
    _cut(subject / "260908-0130")
    new = _cut(subject / "260912-1507")
    cutmark.set_current(subject, "없는판-0000")
    assert cutmark.resolve(subject) == new


def test_current가_아예_없어도_제일_새것을_준다(tmp_path):
    subject = tmp_path / "_materials" / "기생충학"
    _cut(subject / "260908-0130")
    new = _cut(subject / "260912-1507")
    assert cutmark.resolve(subject) == new
    assert cutmark.cuts(subject) == ["260908-0130", "260912-1507"]


def test_판_모양이_아닌_폴더는_판이_아니다(tmp_path):
    subject = tmp_path / "_materials" / "기생충학"
    (subject / "_previous").mkdir(parents=True)
    (subject / "임시").mkdir()
    assert cutmark.cuts(subject) == []


def test_current는_한_줄만_든다(tmp_path):
    """되돌리려면 이 한 줄만 고치면 된다."""
    subject = tmp_path / "_materials" / "기생충학"
    subject.mkdir(parents=True)
    p = cutmark.set_current(subject, "260908-0130")
    assert p.read_text(encoding="utf-8").strip() == "260908-0130"


# ── 원본이 갈렸는지 ──────────────────────────────────────────────────
def test_원본이_갈리면_말한다_막지는_않는다(tmp_path):
    d = _cut(tmp_path / "병리학")
    pdf = tmp_path / "족보.pdf"
    pdf.write_bytes("처음 판".encode())
    cutmark.write(d, source=pdf)
    assert cutmark.stale_source(d) is None

    pdf.write_bytes("다른 판이고 길이도 다르다".encode())
    assert "갈렸다" in cutmark.stale_source(d)


def test_크기가_같고_내용만_갈린_것도_잡는다(tmp_path):
    """`runner/fingerprint.py` 가 실측한 자리다 — 판 번호·크기로는 못 잡는다."""
    d = _cut(tmp_path / "병리학")
    pdf = tmp_path / "족보.pdf"
    pdf.write_bytes(b"AAAA")
    cutmark.write(d, source=pdf)
    pdf.write_bytes(b"BBBB")
    assert "크기는 같고 내용이 다르다" in cutmark.stale_source(d)


def test_원본이_없으면_말을_안_한다(tmp_path):
    """네트워크 드라이브가 안 붙어 있을 수 있다. 모르는 것을 갈렸다고 하지 않는다."""
    d = _cut(tmp_path / "병리학")
    pdf = tmp_path / "족보.pdf"
    pdf.write_bytes(b"x")
    cutmark.write(d, source=pdf)
    pdf.unlink()
    assert cutmark.stale_source(d) is None


# ── ③④ 편이 적는 쪽 ─────────────────────────────────────────────────
def test_붙었으면_어느_판의_어느_조각인지_적는다(tmp_path):
    d = _cut(tmp_path / "병리학")
    pdf = tmp_path / "족보.pdf"
    pdf.write_bytes(b"x")
    cutmark.write(d, source=pdf, cut_id="260914-2312")

    rec = cutmark.used_record(d, d / "L0_강의.json", 0.83)

    assert rec["attached"] is True
    assert rec["cut_id"] == "260914-2312"
    assert rec["slice"] == "L0_강의.json"
    assert rec["score"] == 0.83
    assert "why_not" not in rec
    assert "L0_강의.json" in cutmark.used_line(rec)


@pytest.mark.parametrize("reason", [
    "족보 폴더에 index.json 이 없다 — 아직 안 잘렸다",
    "제목 일치도 0.20 가 문턱 0.25 아래다 (조각은 있다)",
])
def test_안_붙었으면_이유가_남는다(tmp_path, reason):
    """**이것이 이 기록의 요점이다.** 카드 수만 보면 셋이 같은 0으로 나온다."""
    rec = cutmark.used_record(tmp_path / "없는컷", None, 0.2, reason)
    assert rec["attached"] is False
    assert rec["why_not"] == reason
    assert reason in cutmark.used_line(rec)


def test_이유를_안_주면_그렇다고_적는다(tmp_path):
    """빈 문자열이 「이유가 없다」로 읽히면 안 된다."""
    rec = cutmark.used_record(tmp_path, None, 0.0)
    assert rec["why_not"] == "이유가 적히지 않았다"


def test_판이_안_적힌_컷을_써도_기록은_선다(tmp_path):
    """옛 컷으로 돌린 편도 「판 미기록」이라는 사실을 남겨야 한다."""
    d = _cut(tmp_path / "병리학")           # cut.json 없다
    rec = cutmark.used_record(d, d / "L0_강의.json", 0.9)
    assert rec["attached"] is True
    assert rec["cut_id"] is None
    assert "판 미기록" in cutmark.used_line(rec)


def test_편_폴더에_기록을_남긴다(tmp_path):
    p = cutmark.write_used(tmp_path, {"attached": False, "why_not": "없다"})
    assert p.name == "jokbo.used.json"
    assert json.loads(p.read_text(encoding="utf-8"))["why_not"] == "없다"
