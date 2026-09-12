"""pytest가 이 폴더에서 **조용히 0을 돌려주지 않게** 한다.

`pytest server/tests` 는 `no tests ran` 과 함께 **종료 코드 0** 을 냈다. 파일
이름이 전부 `test_*.py` 인데 안에 `test_` 함수가 없기 때문이고, pytest 는 아무것도
안 걸린 것을 실패로 보지 않는다. 그러면 초록색이 「통과」인지 「안 돌았다」인지
구별되지 않는다 — CLAUDE.md 가 「없다로 읽히는 0」이라 부르는 것이다.

**옮기면 되는 것 아닌가.** 안 된다. 다섯 파일이 import 시점에 자기 `DATABASE_URL`
을 세우고 `app.database` 의 모듈 수준 엔진을 만든다. 한 프로세스에 모으면 먼저
import 된 것의 DB 를 나머지가 같이 쓴다. **스크립트인 것은 사정이 있어 고른 것이다**
(`tests/__main__.py` 에 자세히 적어 뒀다).

그래서 여기서는 옮기지 않고 **말만 한다.** 사람이 친 명령이 왜 아무것도 안 했는지
그 자리에서 알려 주고 0 이 아닌 값으로 끝낸다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent

MESSAGE = """
이 폴더의 검사는 pytest 가 아니라 스크립트다. 하나도 수집되지 않은 것이 정상이다.

    .venv/Scripts/python.exe -m tests            전부
    .venv/Scripts/python.exe -m tests smoke      이름에 그 글자가 든 것만

한 파일에 한 프로세스여야 한다 — 파일마다 import 시점에 자기 DATABASE_URL 을
세우기 때문이다. 자세한 것은 server/tests/__main__.py 에 있다.
"""


def pytest_collection_modifyitems(session, config, items):
    """하나도 안 걸렸으면 그 사실을 말하고 0 이 아닌 값으로 끝낸다.

    **`items` 가 비어도 이 훅은 불린다.** 그래서 「수집이 0이다」를 여기서 잡을 수
    있다 — 수집된 것을 손보는 훅으로는 못 잡는다.

    `server/` 아래를 겨눈 실행에서만 문다. 저장소 루트에서 `pytest` 를 돌리면
    `tests/` 의 567개가 걸리므로 이 자리는 지나간다.
    """
    if items:
        return
    # 겨눈 자리가 이 폴더를 **품거나 품긴** 실행에서만 문다. `pytest` 를 그냥 친
    # 것(`server/` 전체)도 여기 든다 — 그때가 제일 헷갈리는 자리라 빠지면 안 된다.
    # 저장소 루트의 `pytest tests` 는 567개가 걸리므로 위에서 이미 돌아갔다.
    targeted = [Path(str(a).split("::")[0]).resolve() for a in (config.args or [])]
    if targeted and not any(p == HERE or HERE in p.parents or p in HERE.parents
                            for p in targeted):
        return
    # **`pytest.exit` 이어야 한다.** `SystemExit` 을 훅 안에서 올리면 pytest 가
    # INTERNALERROR 를 찍고 **그래도 0으로 끝난다** — 고치려던 거짓말이 모양만
    # 바뀐 채 그대로 남는다. 2026-09-12 에 그렇게 한 번 틀렸다.
    pytest.exit(MESSAGE, returncode=1)
