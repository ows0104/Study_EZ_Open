"""족보를 언제 무엇으로 잘랐는지 적어 둔다 — **컷의 판(版)**.

`docs/runs-layout.md` 의 「새로 적어야 하는 것 ①」이다.

> 지금 `runs/_jokbo/<과목>/index.json` 은 `source`·`pages`·`regions`·`lectures`·
> `source_path` 를 든다. **자른 시각도, 자른 코드의 판도 없다.** 컷팅이 한 번쯤
> 바뀔 것을 아는 이상, 바뀐 뒤에 「이 덱은 어느 컷으로 만들었나」를 물을 수 없다.

## 왜 이제 급한가

2026-09-14 에 `out/` 의 재생성본 25편을 배포 중인 판과 맞대 봤더니 **족보참조
카드 수가 25편 전부 줄어 있었다**(중앙 -17장, `260820_01` 은 26 → 4). 그런데
**재료가 안 붙은 것인지 프롬프트가 달라져 인용을 덜 한 것인지 구별할 수 없었다.**
그때 그 편이 어느 컷을 봤는지 아무 데도 안 적혀 있었기 때문이다.

`CLAUDE.md` 가 「어느 쪽 0인지 코드가 구별하지 못하면 사람도 못 한다」고 적은 그
모양이고, 여기가 그 구별을 가능하게 하는 자리다. **이미 쌓인 시도는 못 갈린다** —
이 기록이 붙는 편부터 갈린다.

## 두 쪽이 필요하다

    ①  컷이 자기를 적는다      cut.json   이 폴더 · 판 · 무엇을 언제 무슨 코드로
    ②  편이 그 판을 적는다      jokbo.used.json   어느 판의 어느 조각을 봤는가
                                                  (안 붙었으면 **그 이유**)

②가 없으면 ①은 「지금 컷」만 말한다. 다시 자르면 덮이고 질문은 다시 못 하게 된다.

## mtime 으로 판정하지 않는다

`runner/fingerprint.py` 가 실측으로 적어 둔 것을 그대로 따른다 — `260901_01` 의
`v1` 파일이 `v3` 보다 나중에 쓰여 있었다(Synology 가 파일만 다시 쓴 것으로 보인다).
그래서 원본이 갈렸는지는 **크기와 내용 해시**로 본다. `cut_at` 은 사람이 읽는
값이고 판정에 쓰지 않는다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from .prep import sha256_of

CUT_FILE = "cut.json"
PREVIOUS = "_previous"          # 다시 자를 때 앞 컷이 들어가는 자리

# 컷을 만드는 코드. **이 목록이 곧 「자른 코드의 판」의 정의다.** 파서가 다른
# 모듈로 번지면 여기도 같이 늘려야 한다 — 안 늘리면 코드가 바뀌었는데 판이 그대로다.
CUTTER_FILES = ("jokbo.py", "textutil.py")


def new_cut_id(when: dt.datetime | None = None) -> str:
    """`260914-1830`. **날짜만으로는 겹친다** — 하루에 두 번 자를 수 있다.

    `run_id` 가 `260812_01` 이라 앞 6자리 관례가 같고, 이 모양이면 이름 정렬이
    곧 시간 정렬이다(`docs/runs-layout.md` 「`<판>`은 날짜가 아니라 날짜+시각이다」).
    """
    now = when or dt.datetime.now()
    return f"{now:%y%m%d-%H%M}"


def cutter() -> dict:
    """자른 코드의 판. 커밋과 **코드 내용 해시** 둘을 든다.

    커밋만으로는 모자란다 — 이 저장소는 작업 트리가 더러운 채로 돌리는 일이 흔하고,
    그때 커밋은 코드를 가리키지 못한다. 그래서 `CUTTER_FILES` 의 내용 해시를 같이
    적고, 커밋은 「사람이 찾아갈 자리」로만 둔다.
    """
    here = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for name in CUTTER_FILES:
        p = here / name
        h.update(p.read_bytes() if p.is_file() else b"")
    got = {"code_sha256": h.hexdigest()[:16], "files": list(CUTTER_FILES)}
    # git 이 없거나 저장소가 아닐 수 있다. 없으면 없다고 적고 지나간다 —
    # 코드 해시가 이미 판을 말하므로 이것이 없어도 기록은 성립한다.
    try:
        rev = subprocess.run(["git", "-C", str(here), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        # **경로는 `-C` 한 자리 기준이다.** 여기에 `quizgen/jokbo.py` 를 주면 git 이
        # `quizgen/quizgen/jokbo.py` 를 찾아 **아무것도 안 걸리고 `dirty: false` 가
        # 나온다.** 2026-09-14 에 실제로 그렇게 한 번 거짓을 적었다 — 고친 파일로
        # 자른 컷이 「깨끗한 커밋으로 잘렸다」고 말했다.
        status = subprocess.run(["git", "-C", str(here), "status", "--porcelain",
                                 "--", *CUTTER_FILES],
                                capture_output=True, text=True, timeout=10)
        if rev.returncode == 0:
            got["commit"] = rev.stdout.strip()
            got["dirty"] = bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return got


def source_mark(pdf: Path, pages: int | None = None) -> dict:
    """원본 PDF 의 지문. **크기와 내용 해시** — mtime 은 안 본다(모듈 머리)."""
    p = Path(pdf)
    got = {"name": p.name, "path": str(p.resolve()) if p.exists() else str(p)}
    if p.is_file():
        got["bytes"] = p.stat().st_size
        got["sha256"] = sha256_of(p)
    if pages is not None:
        got["pages"] = pages
    return got


def read(cut_dir: Path) -> dict | None:
    """그 폴더의 `cut.json`. 없으면 None — **옛 컷은 없는 것이 정상이다.**"""
    p = Path(cut_dir) / CUT_FILE
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def archive(cut_dir: Path) -> str | None:
    """지금 있는 컷을 `_previous/<판>/` 으로 밀어 넣는다. 옮긴 판 이름을 돌려준다.

    **다시 자르면 앞 컷이 덮인다.** 그러면 그 컷으로 만든 덱이 무엇을 봤는지 물을
    수 없다 — 이 함수가 있는 이유다. 컷 하나가 0.5~0.9MB 라 남기는 값이 거의 없다.

    `cut.json` 이 없는 옛 컷도 옮긴다. 판 이름을 모르므로 `index.json` 의 mtime 에서
    딴 이름에 `-old` 를 붙인다 — **이름으로 판정하지 말라는 뜻이다**(모듈 머리).
    """
    cut_dir = Path(cut_dir)
    index = cut_dir / "index.json"
    if not index.is_file():
        return None                       # 처음 자르는 것이다. 옮길 것이 없다
    mark = read(cut_dir)
    if mark and mark.get("cut_id"):
        name = str(mark["cut_id"])
    else:
        stamp = dt.datetime.fromtimestamp(index.stat().st_mtime)
        name = f"{new_cut_id(stamp)}-old"
    dest = cut_dir / PREVIOUS / name
    if dest.exists():
        # 같은 분에 두 번 잘렸다. 덮지 않는다 — 덮으면 이 함수의 목적이 없어진다.
        for n in range(2, 100):
            if not (alt := cut_dir / PREVIOUS / f"{name}.{n}").exists():
                dest = alt
                break
    dest.mkdir(parents=True, exist_ok=True)
    for item in cut_dir.iterdir():
        if item.name == PREVIOUS:
            continue
        shutil.move(str(item), str(dest / item.name))
    return dest.name


def write(cut_dir: Path, *, source: Path, pages: int | None = None,
          practical: list[dict] | None = None, counts: dict | None = None,
          cut_id: str | None = None, cut_at: dt.datetime | None = None,
          backfilled: bool = False) -> dict:
    """`cut.json` 을 쓰고 그 내용을 돌려준다.

    `cut_at` 은 되짚어 채울 때만 준다 — **지금 시각을 적으면 그 컷이 오늘 난 것처럼
    보인다.** 되짚은 판은 남아 있는 파일의 시각에서 딴 것이므로 그것을 적어야 한다.
    """
    mark = {
        "cut_id": cut_id or new_cut_id(),
        "cut_at": (cut_at or dt.datetime.now()).isoformat(timespec="seconds"),
        "cutter": cutter(),
        "source": source_mark(source, pages),
    }
    if practical:
        mark["practical_sources"] = practical
    if counts:
        mark["counts"] = counts
    if backfilled:
        # **이 값은 자른 그 자리에서 적힌 것이 아니다.** 나중에 남아 있는 파일로
        # 되짚어 채운 것이라 `cutter` 가 그때 코드가 아니라 지금 코드를 가리킨다.
        mark["backfilled"] = True
        mark["cutter"] = {"unknown": "이 컷을 자른 코드의 판은 기록되지 않았다"}
    (Path(cut_dir) / CUT_FILE).write_text(
        json.dumps(mark, ensure_ascii=False, indent=2), encoding="utf-8")
    return mark


def stale_source(cut_dir: Path) -> str | None:
    """원본이 이 컷보다 새것인가. 갈렸으면 사람이 읽을 한 줄, 아니면 None.

    **막는 데 쓰지 마라.** 원본이 갈렸다고 지금 컷이 못 쓰는 것이 아니다 — 다시
    자르면 되는 일이고, 그 판단은 사람이 한다. 여기서는 말만 한다.

    **되짚어 채운 컷(`backfilled`)에서 「안 갈렸다」는 증거가 아니다.** 그 지문은
    자른 그 자리가 아니라 나중에 같은 파일을 읽어 뜬 것이라, 자른 뒤 채우기 전에
    갈린 것은 이미 안 보인다. 채운 시점 **이후**의 변화만 잡는다.
    """
    mark = read(cut_dir)
    if not mark:
        return None
    src = mark.get("source") or {}
    p = Path(src.get("path", ""))
    if not src.get("sha256") or not p.is_file():
        return None
    if p.stat().st_size != src.get("bytes"):
        return f"원본이 갈렸다 ({src.get('bytes')}B → {p.stat().st_size}B)"
    if sha256_of(p) != src["sha256"]:
        return "원본이 갈렸다 (크기는 같고 내용이 다르다)"
    return None


def used_record(jokbo_dir: Path, slice_path: Path | None, score: float,
                reason: str = "") -> dict:
    """편이 적는 쪽(②). 어느 판의 어느 조각을 봤는가, 안 봤으면 왜 안 봤는가.

    **`jokbo_dir` 을 받았다는 것이 「족보가 붙었다」는 뜻이 아니다.** `run.config.json`
    이 오래전부터 `jokbo_dir` 을 적어 왔는데 `260911_01` 은 그것이 적힌 채로 기출
    0장이었다. 붙었는지 아닌지는 `slice` 가 있는지로 본다.
    """
    mark = read(Path(jokbo_dir)) or {}
    got = {
        "jokbo_dir": str(Path(jokbo_dir)),
        "cut_id": mark.get("cut_id") or None,
        "cut_at": mark.get("cut_at") or None,
        "cutter": (mark.get("cutter") or {}).get("code_sha256"),
        "slice": Path(slice_path).name if slice_path else None,
        "score": round(float(score), 3) if slice_path else None,
        "attached": bool(slice_path),
    }
    if not slice_path:
        # **여기가 이 파일의 요점이다.** 「안 붙었다」가 재료 없음인지 문턱 미달인지
        # 구별되지 않으면 나중에 카드 수만 보고 원인을 짐작하게 된다.
        got["why_not"] = reason or "이유가 적히지 않았다"
    return got


def write_used(run_dir: Path, record: dict) -> Path:
    """그 기록을 편 폴더에 남긴다."""
    p = Path(run_dir) / "jokbo.used.json"
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def used_line(record: dict) -> str:
    """②를 사람이 읽는 한 줄. **붙었는지를 먼저 말한다.**"""
    cut = record.get("cut_id") or "판 미기록"
    if not record.get("attached"):
        return f"안 붙었다 — {record.get('why_not', '이유가 적히지 않았다')} (컷 {cut})"
    score = record.get("score")
    tail = f" · 일치도 {score:.2f}" if isinstance(score, int | float) else ""
    by = f" · {record['by']}" if record.get("by") else ""
    return f"{record.get('slice')} (컷 {cut}){tail}{by}"


def describe(cut_dir: Path) -> str:
    """사람이 읽는 한 줄. 컷이 없으면 그렇게 말한다."""
    mark = read(cut_dir)
    if not mark:
        return "판이 적혀 있지 않다 (2026-09-14 이전에 자른 컷이다)"
    src = mark.get("source") or {}
    who = mark.get("cutter") or {}
    tail = ""
    if who.get("code_sha256"):
        tail = f" · 코드 {who['code_sha256'][:8]}"
        if who.get("commit"):
            tail += f"@{who['commit']}{'+' if who.get('dirty') else ''}"
    return (f"판 {mark.get('cut_id')} ({mark.get('cut_at', '')[:16]})"
            f" · {src.get('name', '?')}{tail}"
            + (" · 되짚어 채운 것" if mark.get("backfilled") else ""))
