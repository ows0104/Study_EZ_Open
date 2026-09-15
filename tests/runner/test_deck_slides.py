"""`slides/`를 갈아 끼우는 자리.

2026-09-02, `260902_01`이 103장을 만들어 놓고 올리다 죽었다. 계획을 세울 때는
있던 슬라이드가 올릴 때는 없었고, `slides/`의 앞 9장이 **이름 순서대로** 비어
있었다 — 폴더를 통째로 지우고 다시 채우는 사이에 업로드가 그 폴더를 읽었다.
"""

from runner import deck


def _media(run_dir, numbers):
    media = run_dir / "media"
    media.mkdir(parents=True, exist_ok=True)
    for number in numbers:
        (media / f"p260902_01_slide{number:02d}.png").write_bytes(b"png")
    # 그림 크롭은 슬라이드가 아니다. 따라가면 안 된다.
    (media / "p260902_01_fig3.png").write_bytes(b"png")
    return media


def test_슬라이드를_서버_이름으로_옮긴다(tmp_path):
    _media(tmp_path, [8, 12, 79])
    assert deck._slides(tmp_path, "260902_01") == 3
    names = sorted(p.name for p in (tmp_path / "slides").iterdir())
    assert names == ["260902_01_s008.png", "260902_01_s012.png", "260902_01_s079.png"]


def test_갈아_끼우는_동안_폴더가_안_빈다(tmp_path):
    """다시 채우는 내내 옛 폴더가 그대로 서 있어야 한다 — 업로드가 그것을 읽는다."""
    _media(tmp_path, [8, 12, 79])
    deck._slides(tmp_path, "260902_01")
    before = sorted(p.name for p in (tmp_path / "slides").iterdir())

    seen = []
    real_copy = deck.shutil.copy2

    def watching(src, dst):
        # 한 장 옮길 때마다 그 순간의 `slides/`를 본다.
        seen.append(sorted(p.name for p in (tmp_path / "slides").iterdir()))
        return real_copy(src, dst)

    deck.shutil.copy2 = watching
    try:
        deck._slides(tmp_path, "260902_01")
    finally:
        deck.shutil.copy2 = real_copy

    assert seen, "옮긴 것이 없다"
    for moment in seen:
        assert moment == before, "채우는 도중에 폴더가 비었다"


def test_media가_없으면_슬라이드도_없다(tmp_path):
    (tmp_path / "slides").mkdir()
    (tmp_path / "slides" / "260902_01_s008.png").write_bytes(b"png")
    assert deck._slides(tmp_path, "260902_01") == 0
    assert not (tmp_path / "slides").exists()


# ── 판 폴더로 가른 뒤 ──────────────────────────────────────────
#
# 5단계(`862edb4`)가 `run_dir / "media"` 를 `_attempt(run_dir, "media", PRE)` 로
# 바꿨다. 옛 모양에서는 갈래와 상관없이 같은 폴더라 값이 같았지만, 판을 가르고
# 나서는 **복습 덱을 구우면서 예습 판을 뒤지는 것**이 된다. 못 찾으면 `slides/` 를
# 지우므로 서버가 읽는 강의 것이 복습 빌드마다 날아간다.

def _attempt_media(run_dir, kind, version, numbers):
    work = run_dir / kind / version
    work.mkdir(parents=True, exist_ok=True)
    (work / "run.config.json").write_text("{}", encoding="utf-8")
    media = work / "media"
    media.mkdir()
    for number in numbers:
        (media / f"p260902_01_slide{number:02d}.png").write_bytes(b"png")
    return media


def test_복습_빌드는_복습_판의_media_를_본다(tmp_path):
    _attempt_media(tmp_path, "main", "260915-1017", [8, 12, 79])
    assert deck._slides(tmp_path, "260902_01", deck.MAIN) == 3
    names = sorted(p.name for p in (tmp_path / "slides").iterdir())
    assert names == ["260902_01_s008.png", "260902_01_s012.png", "260902_01_s079.png"]


def test_예습_판이_없다고_복습_slides_를_지우지_않는다(tmp_path):
    """이것이 2026-09-15 `260831_02` 에서 실제로 났다 — 89장을 굽고 `slides/` 를 잃었다."""
    _attempt_media(tmp_path, "main", "260915-1017", [8, 12])
    assert deck._slides(tmp_path, "260902_01", deck.MAIN) == 2
    assert (tmp_path / "slides").is_dir()


def test_예습_빌드는_예습_판의_media_를_본다(tmp_path):
    _attempt_media(tmp_path, "main", "260915-1017", [8, 12, 79])
    _attempt_media(tmp_path, "prequiz", "260915-0410", [3])
    assert deck._slides(tmp_path, "260902_01", deck.PRE) == 1
    names = sorted(p.name for p in (tmp_path / "slides").iterdir())
    assert names == ["260902_01_s003.png"]
