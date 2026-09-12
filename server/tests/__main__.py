"""검사를 전부 돈다. **한 파일에 한 프로세스다.**

    .venv/Scripts/python.exe -m tests            전부
    .venv/Scripts/python.exe -m tests smoke      이름에 그 글자가 든 것만

## 왜 한 프로세스에 모으지 않나

모을 수가 없다. 다섯 파일이 **import 시점에** 자기 `DATABASE_URL`을 세우고
그 뒤에 `app.database`를 부르는데, 거기서 엔진이 모듈 수준으로 한 번 만들어진다.

    os.environ.update(DATABASE_URL=f"sqlite:///{_TMP / 'smoke.db'}")
    from app.database import Base, engine      ← 여기서 굳는다

한 프로세스에 둘 이상을 들이면 **먼저 import된 것의 DB를 나머지가 같이 쓴다.**
그래서 이 폴더는 pytest가 아니라 스크립트다. 그건 사정이 있어 고른 것이지
안 해 둔 일이 아니다.

## 이 파일이 생긴 이유

`pytest server/tests`가 **"no tests ran"과 함께 종료 코드 0**을 돌려줬다.
파일 이름이 전부 `test_*.py`인데 안에 `test_` 함수가 없어서 하나도 안 걸리고,
pytest는 아무것도 안 걸린 것을 실패로 보지 않는다. 그러면 화면에 뜨는 초록색이
**「통과」인지 「안 돌았다」인지 구별되지 않는다.**

이 저장소가 CLAUDE.md에서 「없다로 읽히는 0」이라 부르는 것과 같은 모양이다.
막는 자리는 둘이다 — 여기(전부 도는 한 명령)와 `conftest.py`(pytest가 조용히
0을 돌려주지 않게 하는 것).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def modules(pattern: str = "") -> list[str]:
    """돌 것들. 이름순이라 실행 순서가 실행마다 안 바뀐다."""
    found = sorted(p.stem for p in HERE.glob("test_*.py"))
    return [m for m in found if not pattern or pattern in m]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    pattern = argv[0] if argv else ""
    names = modules(pattern)
    if not names:
        # **빈 목록을 0으로 돌려주지 않는다.** 그게 이 파일이 고치려는 바로 그 버그다.
        print(f"[tests] '{pattern}' 에 맞는 검사가 없다. 있는 것: {', '.join(modules())}")
        return 2

    failed: list[str] = []
    for name in names:
        # **밀어내야 한다.** 자식은 같은 stdout 에 바로 쓰는데 이쪽은 버퍼에 쌓여,
        # 안 밀면 어느 검사의 출력인지 모르는 줄이 먼저 나오고 머리글이 뒤에 붙는다.
        print(f"\n{'─' * 70}\n  {name}\n{'─' * 70}", flush=True)
        # 파일마다 새 프로세스다. 위의 「왜」를 보라.
        code = subprocess.run([sys.executable, "-m", f"tests.{name}"], cwd=str(ROOT)).returncode
        if code != 0:
            failed.append(f"{name} (코드 {code})")

    print(f"\n{'═' * 70}")
    if failed:
        print(f"  실패 {len(failed)}/{len(names)} — {', '.join(failed)}")
        return 1
    print(f"  전부 통과 — {len(names)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
