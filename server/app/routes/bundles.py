"""여러 편의 덱을 한 파일로 받는 자리 — 하루치, 블럭(과목) 전체.

**합치는 것은 서버가 아니라 브라우저다.** 여기는 목록과 바이트만 준다.

왜 서버가 안 합치나. Cloud Run 이 `--memory 512Mi` 이고(`server/deploy.ps1`),
복습 덱 한 편이 5~13MB 라 블럭 하나는 200MB 를 넘는다. 합치려면 미디어를 통째로
펴야 하므로 그 메모리로는 안 되고, 늘리면 **모아받기를 안 쓰는 요청까지** 그
메모리 값으로 과금된다. 합치는 코드는 `web/src/bundle/apkg.ts` 에 있고, 하는 일은
`quizgen/bundle.py` 와 같다 — 노트·덱·미디어를 그대로 옮겨 담고 guid 는 안
건드린다(그래서 이미 임포트한 덱 위에 덮어도 안전하다).

세 경로가 하는 일:

    GET  /api/bundles/decks                         덱이 어디 있고 무엇을 받아 갔나
    GET  /api/bundles/decks/{subject}/{run}/{kind}  덱 한 편의 바이트. **받았다고 안 적는다**
    POST /api/bundles/grabs                         파일이 손에 들어간 뒤에 적는다

**왜 서명 URL 이 아니라 바이트인가.** 한 편짜리 내려받기는 서명 URL 을 주고
브라우저가 R2 에서 곧바로 받는다(`lectures.sign_file`). 그런데 모아받기는 그
바이트를 **읽어서 합쳐야** 하고, 읽으려면 `fetch` 여야 하고, `fetch` 는 CORS 를
탄다 — 2026-09-15 에 재 보니 R2 의 서명 GET 에는 `Access-Control-Allow-Origin` 이
안 붙는다. `<img>` 와 `<a>` 는 CORS 를 안 타므로 지금까지 이 저장소의 어느 화면도
여기 안 걸렸다. **버킷에 CORS 규칙이 붙으면 이 경로는 없어져도 된다** — 그때는
서명 URL 을 주면 되고, 바이트는 다시 서버를 안 지나간다.

흘려 보내므로 메모리는 조각 하나뿐이다(`storage.open_stream`). 대신 한 요청이
길어질 수 있어 Cloud Run 시한을 120초에서 600초로 올렸다(`deploy.ps1`) — 200MB
짜리 실습 덱이 느린 회선에서 120초를 넘긴다.

**서명과 표시를 가른 것이 여기서 새로 하는 일이다.** 한 편짜리 내려받기
(`lectures.sign_file`)는 서명하면서 같이 적는데, 그것은 누르면 곧바로 파일이
나가기 때문이다. 모아받기는 덱 스무 개를 받아 합치는 동안 얼마든지 깨질 수 있고
(창을 닫거나 메모리가 모자라거나), 그때 「받아 갔다」가 적혀 있으면 다음에 누를 때
**그 편이 목록에서 빠진다** — 받은 적 없는 덱이 영영 안 온다. 그래서 파일이
만들어진 뒤에 브라우저가 따로 와서 적는다.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import Asset, AssetGrab, Lecture
from app.naming import nfc
from app.routes.common import record_grabs, storage_or_503

router = APIRouter()

# 화면이 쓰는 갈래 이름 → 자산 종류. `DeckKind` 와 같은 두 값이다.
DECK_KINDS = {"pre": "pre_apkg", "main": "main_apkg"}
KIND_OF_ASSET = {asset_kind: kind for kind, asset_kind in DECK_KINDS.items()}

# 한 번에 다룰 수 있는 덱 수. 한 학기가 편 200개쯤이라 그 두 배를 둔다 —
# 막자는 것이 아니라 잘못 만든 요청이 조용히 커지지 않게 하는 자다.
MAX_DECKS = 400


class DeckRef(BaseModel):
    """덱 하나를 가리키는 세 값. 자산 id 가 아니라 이것으로 받는다 —
    id 는 다시 구우면 바뀌고, 화면이 들고 있던 목록은 그보다 오래 산다."""

    subject: str
    run_id: str = Field(alias="runId")
    kind: str

    model_config = {"populate_by_name": True}


class DeckRefs(BaseModel):
    decks: list[DeckRef]


@router.get("/bundles/decks")
def read_decks(
    start: Date | None = Query(None, description="이 날짜부터 (없으면 전체)"),
    end: Date | None = Query(None, description="이 날짜까지"),
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """덱이 있는 자리 전부와, 그중 이 사람이 받아 간 것.

    **한 학기치를 한 번에 준다.** 하루 버튼은 캘린더 날짜 머리마다 서므로 날짜별로
    물으면 한 주를 그리는 데 열 번을 부른다. 한 편에 한 줄이라 학기 전체가 400줄쯤
    (60KB) 이고, 화면은 이것을 날짜로도 과목으로도 자기가 갈라 쓴다.

    **`timetable` 의 값으로는 못 센다.** 거기 `marks.prequiz` 는 덱이 아니라 웹
    문항이 있어도 참이고, `grabbed.pre` 는 작년 필기만 받아도 참이다(`GRAB_TRACKS`).
    둘 다 자리 하나에 여러 종류를 묶은 값이라 **덱만 골라 셀 수가 없다.**
    """
    query = (
        select(Asset, Lecture)
        .join(Lecture, (Asset.subject == Lecture.subject) & (Asset.run_id == Lecture.run_id))
        .where(Asset.kind.in_(DECK_KINDS.values()))
    )
    if start is not None:
        query = query.where(Lecture.date >= start)
    if end is not None:
        query = query.where(Lecture.date <= end)
    rows = db.execute(
        query.order_by(Lecture.date, Lecture.slot, Asset.kind, Asset.uploaded_at, Asset.id)
    ).all()

    # **한 자리에 파일이 둘일 수 있다.** 표의 유일 조건이 파일명까지 포함해서
    # (`uq_asset_slot`), 이름이 달라진 채로 다시 구워지면 같은 (편, 갈래)에 두 줄이
    # 남는다. 그대로 두면 화면이 「12편」이라 적고 같은 덱을 두 번 받으며(합칠 때
    # guid 가 겹쳐 접히므로 파일은 멀쩡하다) **수만 거짓이 된다.** 늦게 올라온
    # 것을 쓴다. 시각이 같으면 ID로 순서를 고정해 `read_deck_bytes`와 같은 것을 집는다.
    latest: dict[tuple[str, str, str], tuple[Asset, Lecture]] = {}
    for asset, lecture in rows:
        latest[(asset.subject, asset.run_id, asset.kind)] = (asset, lecture)

    grabbed = {
        (subject, run_id, kind)
        for subject, run_id, kind in db.execute(
            select(AssetGrab.subject, AssetGrab.run_id, AssetGrab.kind).where(
                AssetGrab.user_id == user.id, AssetGrab.kind.in_(DECK_KINDS.values())
            )
        ).all()
    }

    return {
        "decks": [
            {
                "subject": lecture.subject,
                "runId": lecture.run_id,
                "date": lecture.date.isoformat(),
                "slot": lecture.slot,
                "title": lecture.title,
                "kind": KIND_OF_ASSET[asset.kind],
                "filename": asset.filename,
                "sizeBytes": asset.size_bytes,
                "grabbed": (asset.subject, asset.run_id, asset.kind) in grabbed,
            }
            for asset, lecture in latest.values()
        ]
    }


@router.get("/bundles/decks/{subject}/{run_id}/{kind}")
def read_deck_bytes(
    subject: str,
    run_id: str,
    kind: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """덱 한 편의 바이트. **받았다고 적지 않는다** — 그것은 `grabs` 가 한다.

    합치는 쪽이 이것을 편마다 한 번씩 부른다. 조각으로 흘려 보내므로 서버 메모리는
    덱 크기와 상관없다.

    **왜 서명 URL 이 아닌지는 이 파일 첫머리에 있다**(R2 에 CORS 가 없다).
    """
    if kind not in DECK_KINDS:
        raise HTTPException(status_code=404, detail="모르는 갈래입니다.")
    # 한 자리에 파일이 둘이면 늦게 올라온 것. **목록과 같은 것을 집어야 한다** —
    # 어긋나면 화면이 센 크기와 실제로 오는 바이트가 다르다.
    asset = db.scalars(
        select(Asset)
        .where(Asset.subject == nfc(subject), Asset.run_id == run_id, Asset.kind == DECK_KINDS[kind])
        .order_by(Asset.uploaded_at.desc(), Asset.id.desc())
    ).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="덱을 찾을 수 없습니다.")
    opened = storage_or_503().open_stream(asset.object_key)
    if opened is None:
        # 표에는 있는데 저장소에 없다. 다시 굽는 중에 갈렸을 수 있다 — 화면이
        # 그 한 편만 빼고 나머지를 담도록 404 로 답한다.
        raise HTTPException(status_code=404, detail="덱 파일이 저장소에 없습니다.")
    chunks, size = opened
    return StreamingResponse(
        chunks,
        media_type=asset.content_type or "application/octet-stream",
        headers={"Content-Length": str(size), "Cache-Control": "private, max-age=0"},
    )


@router.post("/bundles/grabs")
def put_grabs(
    payload: DeckRefs,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """받아 갔다고 적는다. **브라우저가 파일을 손에 넣은 뒤에 부른다.**

    다음에 누를 때 「안 받은 것만」이 이 표를 읽는다(`read_decks`). 그래서 여기서
    조용히 실패하면 같은 덱을 매번 다시 받게 되고, 반대로 너무 일찍 적으면 받은
    적 없는 덱이 영영 목록에서 빠진다 — 파일이 만들어진 뒤라는 것이 이 경로의
    전부다.
    """
    refs = _checked(payload.decks)
    found = _assets_for(db, refs)
    keys = [
        (asset.subject, asset.run_id, asset.kind)
        for ref in refs
        if (asset := found.get((nfc(ref.subject), ref.run_id, DECK_KINDS[ref.kind]))) is not None
    ]
    return {"recorded": record_grabs(db, user.id, keys)}


def _checked(refs: list[DeckRef]) -> list[DeckRef]:
    """갈래 이름과 개수만 본다. 있는 덱인지는 `_assets_for` 가 답한다."""
    if not refs:
        raise HTTPException(status_code=422, detail="덱을 하나도 안 골랐습니다.")
    if len(refs) > MAX_DECKS:
        raise HTTPException(status_code=422, detail=f"한 번에 {MAX_DECKS}편까지만 됩니다.")
    bad = sorted({ref.kind for ref in refs} - set(DECK_KINDS))
    if bad:
        raise HTTPException(status_code=422, detail=f"모르는 갈래입니다: {', '.join(bad)}")
    return refs


def _assets_for(db: Session, refs: list[DeckRef]) -> dict[tuple[str, str, str], Asset]:
    """가리킨 덱들의 자산을 한 번에 집어 온다.

    **과목·run_id 를 각각 `IN` 으로 좁히면 교차곱이 섞여 들어온다** — 같은 교시에
    여러 과목이 열리므로 `run_id` 단독은 유일하지 않다. 넓게 받아서 정확한 짝만
    남긴다(`common.material_marks` 와 같은 손질이다).
    """
    wanted = {(nfc(ref.subject), ref.run_id, DECK_KINDS[ref.kind]) for ref in refs}
    rows = db.scalars(
        select(Asset).where(
            Asset.subject.in_({subject for subject, _, _ in wanted}),
            Asset.run_id.in_({run_id for _, run_id, _ in wanted}),
            Asset.kind.in_({kind for _, _, kind in wanted}),
        )
    ).all()
    return {
        (asset.subject, asset.run_id, asset.kind): asset
        for asset in rows
        if (asset.subject, asset.run_id, asset.kind) in wanted
    }
