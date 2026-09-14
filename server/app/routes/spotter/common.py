"""땡시 경로가 다 같이 쓰는 것 — 문·과목·R2 키·작은 헬퍼.

여기 있는 것의 공통점은 **경로가 아니라는 것**이다. 경로는 관심사별 모듈에 있고
(`content`·`state`·`reports`·`threads`·`uploads`), 그 다섯이 전부 이 파일을 부른다.

`_subject`·`_safe_name` 은 **막는 자리**라 한 벌이어야 한다. 과목 이름과 사진
이름이 R2 키의 칸이 되므로, 검사가 모듈마다 따로 있으면 한 군데만 빠져도
접두사 밖을 가리키는 키가 만들어진다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from app.auth import require_app
from app.models import (
    APP_SPOTTER,
    SPOTTER_ALERT_MIN,
    SPOTTER_REPORT_OPEN,
    SpotterReport,
)
from app.storage import ObjectStorage, StorageNotConfigured

router = APIRouter(prefix="/spotter", tags=["spotter"])

# 이 앱의 문. `APP_POLICY[APP_SPOTTER]`가 `auto`라 로그인하면 그 자리에서
# 권한이 나온다. Study_EZ가 `manual`이라 사람을 기다리는 것과 갈리는
# 지점이고, 이 줄 하나가 그 차이의 전부다.
require_spotter = require_app(APP_SPOTTER)

PREFIX = "spotter"

# 과목. **하나의 앱 안에서 갈리는 갈래지 앱이 아니다** — 문은 `require_spotter`
# 하나이고, 로그인하면 다섯이 다 열린다. 과목을 늘리는 것은 여기 한 줄이다.
#
# 이름이 곧 R2 키의 한 칸이고 배포된 사이트의 경로와도 같다
# (`spotter.studyez.kr/<과목>/`). 셋을 맞춰 두면 어디서 왔는지 헷갈릴 일이 없다.
SUBJECTS = ("parasitology", "exam1", "trunk", "head-neck", "neuro")

# 기본 과목. 옛 경로(`/api/spotter/db`)가 가리키는 곳이다 — 과목이 하나뿐이던
# 시절에 배포된 화면이 아직 열려 있을 수 있어서 남겨 둔다.
DEFAULT_SUBJECT = "parasitology"

# 한 번에 서명해 줄 사진의 수. 해부학 과목은 한 판에 700장까지 쓸 수 있어서
# 화면이 커서 앞뒤로 창을 밀며 나눠 받는다. 상한이 있는 것은 이 경로가
# 로그인만 지나기 때문이다 — 없으면 한 번에 전부 받아 갈 수 있다.
MAX_SIGN = 120


def _subject(name: str) -> str:
    if name not in SUBJECTS:
        raise HTTPException(status_code=404, detail=f"없는 과목입니다: {name}")
    return name


def _db_key(subject: str) -> str:
    return f"{PREFIX}/{subject}/quiz_db.json"


def _image_prefix(subject: str) -> str:
    return f"{PREFIX}/{subject}/images"


# 문항 DB. 인스턴스마다 과목별로 한 벌씩 들고 있는다.
#
# **바이트가 서버를 지나는 유일한 자리다.** 서명 URL로 내보내면 주소가 매번
# 달라져 브라우저 캐시가 안 듣고, 5.4MB짜리를 접속할 때마다 새로 받는다.
# gzip하면 0.24MB고 ETag가 붙으므로 두 번째 접속부터는 304로 끝난다.
_db_cache: dict[str, dict[str, Any]] = {}


def _storage() -> ObjectStorage:
    try:
        return ObjectStorage()
    except StorageNotConfigured as exc:
        raise HTTPException(status_code=503, detail="자료 저장소가 아직 준비되지 않았습니다.") from exc


def _iso(value: datetime) -> str:
    """시각 하나. **오프셋을 반드시 붙인다.**

    화면이 `new Date(...)`로 읽는데, 오프셋이 없으면 브라우저가 그것을 **현지
    시각**으로 해석한다. 우리는 UTC로 저장하므로 그대로 두면 기록이 아홉 시간
    어긋나 보인다. Postgres는 `timezone=True` 칼럼에서 오프셋을 돌려주지만
    sqlite(로컬 테스트)는 떼어 버려서, 두 곳이 다르게 도는 것을 여기서 막는다.
    """
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def _safe_name(name: str) -> str:
    """사진 이름 한 칸. 키를 만들기 전에 반드시 지난다.

    `..`나 `/`가 든 이름을 그대로 이으면 접두사 밖을 가리키는 키가 되고,
    그러면 이 경로로 Study_EZ의 강의 필기가 새어 나간다. 같은 버킷을 쓰는
    대가이므로 여기서 한 번에 막는다.
    """
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail=f"사진 이름이 올바르지 않습니다: {name}")
    return name


# ── 제보 한 줄을 읽는 법 ───────────────────────────────────────────
#
# 제보(`reports`)와 게시판(`threads`) 이 **둘 다** 쓴다. 게시판의 내용이 곧
# 그 과목·사진에 모인 제보이기 때문이다. 어느 한쪽에 두면 다른 쪽이 그것을
# 부르고, 제보 쪽은 글타래를 세워야 해서(`ensure_threads`) 화살표가 서로를
# 가리킨다. **여기 두면 둘 다 아래로만 본다.**

def _image_names(row: SpotterReport) -> list[str]:
    """이 제보가 걸린 사진 이름들.

    새 줄은 `images`에 파일명만 들고 있다. **옛 줄은 그 칼럼이 비어 있어서**
    사람이 읽는 `image`에서 뽑는다 — 「a.jpg, b.jpg (출처 · 출처)」 꼴이라
    괄호 앞까지가 이름이다. 칼럼을 붙이기 전에 들어온 제보도 같이 세려는
    것뿐이고, 앞으로 쌓이는 것은 전부 첫 갈래로 온다.
    """
    raw = row.images or row.image.split(" (")[0]
    return [name.strip() for name in raw.split(",") if name.strip()]


def _hot_questions(rows: list[SpotterReport]) -> dict[str, set[str]]:
    """선을 넘은 문항 → 걸린 사람들.

    한 사람이 한 문항에 한 줄이라 열린 줄을 세면 그대로 사람 수다. 세는 자리를
    여기 하나에 두고 제보함·격리 목록·게시판이 다 이것을 부른다 — 세 벌이면
    화면마다 다른 수를 말하게 된다.
    """
    tally: dict[str, set[str]] = {}
    for row in rows:
        if row.status == SPOTTER_REPORT_OPEN:
            tally.setdefault(row.question_id, set()).add(row.user_id)
    return {qid: users for qid, users in tally.items() if len(users) >= SPOTTER_ALERT_MIN}


def _hot_images(rows: list[SpotterReport]) -> list[dict[str, Any]]:
    """**여러 문항에 걸쳐** 같은 사진에 쌓인 제보.

    한 사진이 여러 문항에 쓰인다. 사진이 흐리거나 잘못 잘렸으면 제보는 그
    사진을 쓰는 문항마다 흩어져 들어오고, 문항으로만 세면 어느 쪽도 임계값을
    못 넘은 채 나쁜 사진 하나가 계속 돌아다닌다. 그 자리를 여기서 잡는다.

    **한 문항에만 걸린 사진은 안 낸다.** 그것은 위의 문항 묶음이 이미 말한
    것이고, 같은 일을 두 번 적으면 목록이 두 배로 길어지면서 새로 알려 주는
    것은 없다.

    사람은 문항이 아니라 **사람으로 센다.** 한 사람이 같은 사진의 두 문항을
    제보했으면 한 명이다 — 「여럿이 걸렸다」가 이 수의 뜻이라서다.
    """
    tally: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        if row.status != SPOTTER_REPORT_OPEN:
            continue
        for name in _image_names(row):
            spot = tally.setdefault(name, {"questions": set(), "users": set()})
            spot["questions"].add(row.question_id)
            spot["users"].add(row.user_id)

    out = [
        {
            "image": name,
            "open": len(spot["users"]),
            "questionIds": sorted(spot["questions"]),
        }
        for name, spot in tally.items()
        if len(spot["users"]) >= SPOTTER_ALERT_MIN and len(spot["questions"]) > 1
    ]
    return sorted(out, key=lambda g: (-g["open"], g["image"]))
