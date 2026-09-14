"""원본이 갈렸는지 **한 값으로** 판정한다.

2026-09-04 이전에는 두 곳이 서로 다른 파일의 서로 다른 값을 봤다.

    문지기  publish._owns → deck.source_pdf → run.config.json  (빌드가 쓴 것)
    쓸기    watch._already_built           → source.json       (빌드 뒤에 찍는 것)

그래서 쓸기가 아무것도 안 만들고 `source.json` 만 새 판으로 찍으면 **쓸기는
「이미 만듦」, 문지기는 「옛 판이라 못 내보낸다」** 가 되어 그 편이 갇혔다.
둘 다 이 모듈을 보게 해서 그 갈림을 없앤다.

**판 번호(`vN`)만으로는 못 잡는 것이 있다.** 2026-09-04 에 `260903_03` 의 v1 파일이
이름 그대로 5,769,068B(16:37) 에서 5,791,054B(19:52) 로 바뀌었고, 그 사이 18:13 에
만든 덱이 문지기를 그냥 지났다. 그래서 내용 해시를 같이 본다.

**`mtime` 으로 판정하지 않는다.** `260901_01` 의 `v1` 파일이 `v3` 보다 나중에 쓰여
있다(23:11 vs 20:19). Synology 가 파일만 다시 쓴 것으로 보이고, mtime 을 믿으면
안 바뀐 것을 바뀌었다고 본다. `size` 도 약하다 — 같은 크기로 갈릴 수 있다.

**지문은 `prep.json` 에서 읽는다.** 그것이 원본을 실제로 읽어 만든 산출물이기
때문이다. `run.config.json` 은 이어 돌릴 때마다 다시 쓰이므로, 거기 지문을 박으면
**prep 를 다시 안 돌린 재개에서 기록이 산출물보다 앞선다** — 그게 편을 가두는
바로 그 모양이다. 지문이 없는 옛 편(`runner import` 로 옮겨 온 것 등)은 예전처럼
판 번호로만 본다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from . import filenames, runlayout

KEY = "source_sha256"
_CHUNK = 1 << 20

ABSENT = "absent"                    # 만든 적이 없다
SAME = "same"                        # 같은 원본이다
NEWER_VERSION = "newer_version"      # 파일명의 판 번호가 올라갔다
CONTENT_CHANGED = "content_changed"  # 판 번호는 같은데 내용이 갈렸다
OLDER_VERSION = "older_version"      # 산출물이 더 새 판으로 만들어져 있다

# 다시 만들어야 하는 상태. 부르는 쪽이 이 집합으로 묻는다.
STALE = (NEWER_VERSION, CONTENT_CHANGED)


@dataclass
class Verdict:
    state: str
    note: str = ""              # 사람이 볼 말. 같으면 빈 문자열
    recorded: dict | None = None
    by_hash: bool = False       # 내용 해시로 판정했는가 (아니면 판 번호로만)

    @property
    def stale(self) -> bool:
        return self.state in STALE


def sha256_of(path: Path) -> str:
    """11MB PDF 에 수십 ms 다. 판 번호가 갈린 것이 이미 보이면 부르지 않는다."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fp:
        while chunk := fp.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _version_of(name: str) -> int | None:
    parsed = filenames.parse(Path(name)) if name else None
    return parsed.version if parsed else None


def built_from(run_dir: Path) -> dict | None:
    """이 자리의 산출물이 **무엇으로** 만들어졌는가.

    앞에 있는 것일수록 산출물에 가깝다. `source.json` 은 빌드가 끝난 뒤에 찍는
    표시라 마지막이다 — 그것만 앞서 갱신되는 것이 편을 가두는 모양이었다.
    """
    # **시도 것은 `runlayout` 에게 묻는다.** 새 모양에서는 `prep.json` 이
    # `runs/<편>/main/<판>/` 안에 있고 옛 모양에서는 강의 폴더에 있다. 여기서
    # `run_dir / "prep.json"` 을 그대로 쓰면 옮긴 편이 **지문 없음**으로 읽혀
    # 「아직 안 만들었다」가 되고, 밤 쓸기가 그 편을 다시 만든다.
    prep = _load(runlayout.find(run_dir, "prep.json") or run_dir / "prep.json")
    if isinstance(prep, dict) and prep.get("source"):
        name = str(prep["source"])
        return {"sha256": str(prep.get(KEY) or ""), "name": name,
                "version": _version_of(name), "where": "prep.json"}

    cfg = None
    for which, kind in (("run.config.json", runlayout.MAIN),
                        ("prequiz.config.json", runlayout.PREQUIZ)):
        found = runlayout.find(run_dir, which, kind)
        if found and (cfg := _load(found)):
            break
    if isinstance(cfg, dict) and (cfg.get("pdf") or cfg.get("pdf_name")):
        name = Path(str(cfg.get("pdf") or cfg.get("pdf_name"))).name
        return {"sha256": "", "name": name, "version": _version_of(name),
                "where": "run.config.json"}

    rec = _load(run_dir / "source.json")
    if isinstance(rec, dict) and rec.get("stem"):
        return {"sha256": str(rec.get(KEY) or ""), "name": str(rec.get("stem")),
                "version": rec.get("version"), "where": "source.json"}
    return None


def compare(run_dir: Path, pdf: Path, version: int) -> Verdict:
    """지금 손에 있는 필기와 이 자리의 산출물을 댄다.

    판 번호가 이미 갈렸으면 해시를 뜨지 않는다. 밤 쓸기가 과목마다 수십 편을
    훑으므로, 값이 답을 바꾸지 못하는 자리에서 40MB 를 읽지 않는다.
    """
    rec = built_from(run_dir)
    if rec is None:
        return Verdict(ABSENT)

    old_v = rec.get("version")
    if old_v is not None and old_v < version:
        return Verdict(NEWER_VERSION, recorded=rec,
                       note=f"산출물은 v{old_v} 로 만들었는데 필기는 v{version} 이다")
    if old_v is not None and old_v > version:
        return Verdict(OLDER_VERSION, recorded=rec,
                       note=f"산출물이 v{old_v} 인데 지금 보는 필기는 v{version} 이다")

    # 판 번호가 같다. 여기서부터가 이름만으로는 못 보던 자리다.
    if not rec.get("sha256"):
        return Verdict(SAME, recorded=rec)
    try:
        now = sha256_of(pdf)
    except OSError:
        return Verdict(SAME, recorded=rec)
    if now == rec["sha256"]:
        return Verdict(SAME, recorded=rec, by_hash=True)
    return Verdict(CONTENT_CHANGED, recorded=rec, by_hash=True,
                   note=(f"이름은 v{version} 그대로인데 내용이 갈렸다 "
                         f"({rec['sha256'][:12]} → {now[:12]})"))


def record(pdf: Path, version: int) -> dict:
    """`source.json` 에 넣을 값. 지문을 같이 적는다."""
    stat = Path(pdf).stat()
    return {"path": str(pdf), "stem": Path(pdf).stem, "version": version,
            "size": stat.st_size, "mtime": int(stat.st_mtime),
            KEY: sha256_of(pdf)}
