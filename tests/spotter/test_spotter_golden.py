"""땡시(Spotter)를 리팩터해도 문항이 안 흔들리는지 보는 골든 검사.

**이 폴더에서 땡시를 재는 것이 2026-09-14 에 처음이다.** 그 전까지 땡시에는
검사가 하나도 없었고, `audit_*.py` 둘이 그 자리를 대신했는데 그것은 **자료를
보는 것이지 코드를 보는 것이 아니다**.

여기서 재는 것은 하나다 — **같은 자료에서 같은 문항이 나오는가.** 문항의 내용이
좋은지는 안 본다(그건 `screen_questions.py` 가 모델에게 물어서 한다). 이 검사가
막으려는 것은 리팩터가 문항을 **조용히** 바꾸는 것이다. 땡시의 사고는 예외가
아니라 숫자로 오기 때문이다 — 저장소가 스스로 적어 둔 마지막 커밋이
「구울 때마다 문항이 흔들리던 것을 멈춘다」다.

값이 바뀌면 **먼저 왜 바뀌었는지 답하고**, 의도한 것이면 그때 숫자를 고친다.
숫자를 먼저 고치면 이 검사는 아무것도 안 막는다.
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SPOTTER = Path(__file__).resolve().parents[2] / "spotter"
SCRIPTS = SPOTTER / "scripts"


def _generator(seed=20260906):
    """`build_web.main()` 이 쓰는 것과 같은 씨앗으로 세운다."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from generate_exam import Generator

    return Generator(seed=seed)


def _fingerprint(questions):
    """문항의 **뜻**만 남긴 지문. 번호·순서가 아니라 내용이 바뀌면 달라진다."""
    keep = ("qtype", "stem", "options", "answer_index", "specimen_id")
    blob = json.dumps(
        [{k: q[k] for k in keep} for q in questions],
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _built():
    gen = _generator()
    cands = gen.candidates()
    qs = [q for q in (gen.build(c, i + 1, 0) for i, c in enumerate(cands)) if q]
    return cands, qs


# ── 문항 생성 ──────────────────────────────────────────────────────

def test_후보와_문항_수가_그대로다():
    cands, qs = _built()
    assert len(cands) == 5580
    assert len(qs) == 5575


def test_같은_씨앗이면_같은_문항이_나온다():
    """**세 번 돌려서 같은지 보는 것이 아니다.** 한 프로세스 안에서 두 번 부르면
    캐시 때문에 저절로 같을 수 있다. 여기서는 박아 둔 지문과 맞대 본다 —
    그 지문은 `PYTHONHASHSEED` 를 바꿔 가며 세 번 뽑아 같은 것을 확인한 값이다.
    """
    _, qs = _built()
    assert _fingerprint(qs) == "96c37a979e5d02f9"


def test_씨앗이_다르면_다른_문항이_나온다():
    """씨앗이 안 먹고 있으면 위 검사는 통과하면서 아무것도 안 지킨다."""
    gen = _generator(seed=1)
    cands = gen.candidates()
    qs = [q for q in (gen.build(c, i + 1, 0) for i, c in enumerate(cands)) if q]
    assert _fingerprint(qs) != "96c37a979e5d02f9"


# ── 족보 ───────────────────────────────────────────────────────────
#
# `parse_jokbo.py` 의 산출물을 잰다. 파서 자체를 돌리지 않는 이유는 원본 PDF 가
# `기생충학/` 에 있고 그 폴더는 **남의 것이라 저장소에 안 들어간다**(반출금지가
# 적힌 자료다). 산출물은 추적되므로 이 값들은 어느 기계에서나 선다.
#
# 이 숫자가 `docs/archive/refactor-plan.md` Phase 3(족보 파서 둘을 하나로)의 한쪽 자다.

JOKBO_BY_YEAR = {
    "2015": 40, "2016-1": 38, "2017": 30, "2019": 40,
    "2021": 21, "2022": 30, "2023": 40, "2025": 40,
}


def _past():
    p = SPOTTER / "data" / "past_questions.json"
    return json.loads(p.read_text(encoding="utf-8"))["questions"]


def test_족보_문항_수가_해마다_그대로다():
    import collections
    got = collections.Counter(q["year"] for q in _past())
    assert dict(got) == JOKBO_BY_YEAR
    assert sum(JOKBO_BY_YEAR.values()) == 279


def test_족보_문항의_사진과_정답이_안_줄었다():
    """**합쳤는데 문항이 줄었다**를 보는 자리다. 합계만 보면 사진이나 정답만
    빠진 것을 못 본다 — 그쪽이 조용히 빠지는 쪽이다."""
    qs = _past()
    assert sum(1 for q in qs if q.get("image_paths")) == 266
    assert sum(1 for q in qs if q.get("answer_index") is not None) == 234


# ── 연결부 ─────────────────────────────────────────────────────────

def test_공용_세션_파일이_안_갈라졌다():
    """`platform/session/session.js` 의 사본이 `spotter/web/` 에 있다. 빌드 도구가
    없어서 사본을 두는데, **조용히 갈라지는 것만 막으면 된다**는 것이
    `sync_shared.py` 의 설계다. 그 검사를 여기서도 부른다 — 저장소를 합치면서
    원본 경로가 형제 폴더에서 상위로 바뀐 자리이기도 하다."""
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "sync_shared.py"), "--check"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(SPOTTER),
    )
    assert r.returncode == 0, r.stdout + r.stderr


# ── 빌드 산출물 (있을 때만) ────────────────────────────────────────

def test_구워_둔_문항_DB가_있으면_그것도_안_흔들린다():
    """`build/` 는 무시되는 폴더라 기계마다 있을 수도 없을 수도 있다."""
    p = SPOTTER / "build" / "quiz_db.json"
    if not p.is_file():
        pytest.skip("build/quiz_db.json 이 없다 — build_web.py 를 안 돌린 기계다")
    qs = json.loads(p.read_text(encoding="utf-8"))["questions"]
    # 생성 문항 + 족보 indicator 문항. 합계만 본다 — 족보 쪽은 위에서 따로 잰다.
    assert len(qs) == 5606


# ── 해부학 원본과 배포본 ───────────────────────────────────────────
#
# 2026-09-14 에 회수하기 전까지 **해부학 넷의 원본은 배포 저장소에만 있었다.**
# `deploy_pages.py` 가 배포본을 제자리에서 고쳐 로그인 문을 달았기 때문에,
# 배포 저장소를 되돌리면 앱이 통째로 사라지는 구조였다.
#
# 지금은 `spotter/web/anatomy/` 가 원본이고 배포는 옮기기만 한다. 아래 둘이
# 그 관계를 잡아 둔다 — **원본과 배포본이 조용히 갈라지는 것**이 이 앱들의
# 사고 방식이다(2026-09-06 에 새 HTML 이 옛 `app.js` 를 네 시간 불렀다).

ANATOMY = ("exam1", "trunk", "head-neck", "neuro")
_STAMP = re.compile(r'(<script src="[^"]+?\.js)\?v=[0-9a-f]+(")')


def _unstamped(path):
    return _STAMP.sub(r"\1\2", Path(path).read_text(encoding="utf-8"))


# 배포가 아직 안 간 변경. **고친 날과 이유를 적는다** — 배포하면 이 칸이 비고,
# 안 비면 「고쳤다고 했는데 안 나갔다」가 검사에서 드러난다.
PENDING_DEPLOY: dict[str, str] = {}
# 2026-09-14: `trunk`·`head-neck` 의 사진 수정이 여기 서 있었고, 배포하자
# **이 검사가 먼저 「같아졌으니 지워라」고 말했다.** 그게 이 칸의 쓸모다.


def _anatomy(subject):
    root = Path(__file__).resolve().parents[2]
    return (root / "spotter" / "web" / "anatomy" / subject / "index.html",
            root / "spotter-dist" / subject / "index.html")


@pytest.mark.parametrize("subject", ANATOMY)
def test_해부학_원본과_배포본이_각인_말고는_같다(subject):
    """다른 것은 `?v=` 각인뿐이어야 한다 — 그건 배포가 그때 계산해 붙인다.

    **`PENDING_DEPLOY` 에 적힌 과목은 달라야 한다.** 배포하면 같아지고, 그때
    그 줄을 지운다. 지우는 것을 잊으면 이 검사가 먼저 말한다.
    """
    src, dst = _anatomy(subject)
    same = _unstamped(src) == _unstamped(dst)
    if subject in PENDING_DEPLOY:
        assert not same, (
            f"{subject} 는 배포되어 같아졌다. PENDING_DEPLOY 에서 그 줄을 지워라: "
            f"{PENDING_DEPLOY[subject]}"
        )
    else:
        assert same


@pytest.mark.parametrize("subject", ANATOMY)
def test_본문_사진은_서명_URL로만_부른다(subject):
    """**이 검사가 없어서 두 과목이 깨진 채로 나가 있었다.**

    `gate_subject.py` 가 사진 함수를 갈아 끼우는데, `trunk` 과 `head-neck` 은
    `loadQuestion` 안의 한 줄이 그 갈아 끼우기를 안 탔다 —

        imgEl.src = "Spotter_Questions_All/" + data.image_filename;

    배포본에 그런 폴더가 없다. 사진은 R2 서명 URL 로만 나가고, 그 자리를
    `GATE.image` 가 만든다. `exam1` 은 `setQuestionImage`, `neuro` 는
    `imageUrlOf` 를 불러서 멀쩡했고 **둘만 조용히 깨져 있었다.**

    개수를 세는 대신 죽은 경로가 하나도 없는지 본다 — 개수는 앱마다 다르다.
    """
    src, _ = _anatomy(subject)
    body = src.read_text(encoding="utf-8")
    assert "Spotter_Questions_All/" not in body
    assert "GATE.image(" in body


def test_각인은_줄끝을_안_본다():
    """`digest` 가 날바이트를 해싱하면 CRLF 로 받은 기계와 LF 로 받은 기계가
    **같은 파일에 다른 주소**를 붙인다. 배포본이 적고 있던 `gate.js?v=c12746c4`
    가 정확히 그 값이었다 — 내용은 같은데 주소가 둘이었다."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import deploy_pages

    body = b"const A = 1;\nconst B = 2;\n"
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        lf = Path(d) / "lf.js"
        crlf = Path(d) / "crlf.js"
        lf.write_bytes(body)
        crlf.write_bytes(body.replace(b"\n", b"\r\n"))
        assert deploy_pages.digest(str(lf)) == deploy_pages.digest(str(crlf))


# ── 해부학 한 판 ───────────────────────────────────────────────────

def test_해부학_셋이_판에서_그대로_나온다():
    """`exam1`·`trunk`·`head-neck` 은 `_template.html` 한 장에서 찍는다.

    **사본 셋이던 것을 2026-09-14 에 합쳤다.** trunk 과 head-neck 은 635줄 중
    네 줄만 달랐고(제목·번호·표제·과목 키), exam1 은 거기에 핀 표시가 붙은
    것이었다. 합치는 근거는 취향이 아니라 사고다 — 사본 하나만 고쳐서 두 과목이
    본문 사진 없이 배포돼 있었다(`test_본문_사진은_서명_URL로만_부른다`).

    파일을 손으로 고치면 이 검사가 먼저 말한다. 판을 고치고 다시 찍어야 한다.
    """
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_anatomy.py"), "--check"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(SPOTTER),
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_neuro_는_판_밖에_있다():
    """989줄이고 트렁크 계열과 1,586줄이 다르다 — **다른 앱이다.** 억지로 넣으면
    판이 두 앱을 다 아는 괴물이 된다. 그 선을 검사로 적어 둔다."""
    subjects = json.loads((SPOTTER / "web" / "anatomy" / "subjects.json")
                          .read_text(encoding="utf-8"))
    assert "neuro" not in subjects
    assert (SPOTTER / "web" / "anatomy" / "neuro" / "index.html").is_file()
