"""산출물을 서버로 밀어 넣는다. 로컬 러너의 마지막 단계다.

    python -m studyez publish 병리학 --dry-run     무엇이 올라갈지만 본다
    python -m studyez publish 병리학
    python -m studyez publish --run-id 260814_05   그 run을 쓰는 한 편만

계약은 `docs/artifact-contract.md`, 엔드포인트는 `server/README.md`에 있다.
여기서는 **아무것도 만들지 않는다.** 이미 만들어 둔 것을 모아 올릴 뿐이다.

## 사람이 안 불러도 돈다

두 자리에서 걸린다. 편이 끝날 때 `studyez done <run_id>`가 그 편을 밀고, 하루
한 번 `scripts/nightly-publish.ps1`이 `--all`로 놓친 것을 쓸어담는다. 겹쳐
돌아도 되는 이유는 아래 「같은 것을 다시 밀지 않는다」다.

사람 없이 나가도 되는지는 `studyez.gate`가 편마다 본다. 막힌 편은 강의록만
나가고 덱은 미뤄지므로, **자동 실행이 덱을 조용히 내보내는 일은 없다.**

## 한 강의의 자료가 두 군데서 온다

    올해 필기 PDF · Main-Quiz 덱 · run.meta        runs/<올해 run_id>/
    작년 필기 PDF · Pre-Quiz 덱 · 예습 대화         runs/<작년 run_id>/

Pre-Quiz는 **작년 필기로 만든다**(족보가 정리돼 붙은 쪽이 작년이다). 그래서
`pre_*`와 `preview.md`는 작년 run 디렉터리에 있는데 붙일 자리는 올해 강의다.
작년 짝은 `studyez.matching`이 정하고 **확정인 것만 쓴다** — 어긋난 짝을 붙이면
남의 강의 예습이 올라간다.

## 슬라이드 이미지는 Pre-Quiz가 있을 때만 올린다

`media/*.png`를 읽는 곳은 서버에 한 군데뿐이다. 웹 Pre-Quiz의 오답 해설이
`slide_no`로 찾는다(`server/app/routes/prequiz.py`의 `slide_url`). 그 자리는
`(과목, run_id, slide_no)`로만 찾으므로 올해 슬라이드와 작년 슬라이드를 한
강의에 같이 올리면 같은 번호가 둘이 되어 어느 쪽이 뜰지 알 수 없다. 그래서
**`pre_items`가 가리키는 쪽(작년)의 이미지만** 올린다. Pre-Quiz가 없는 강의는
아직 아무도 읽지 않으므로 올리지 않는다 — 편당 12~27MB다.

## 같은 것을 다시 밀지 않는다

강의록 PDF가 편당 5~56MB이고 한 과목이 15편이다. 표시가 없으면 돌릴 때마다
수백 MB를 다시 민다. `runs/published.json`에 (크기, mtime)을 적어 두고 바뀐
것만 올린다. `--force`면 표시를 무시한다.

다만 목록 확인(`uploads` → `uploads/complete`)은 표시와 무관하게 매번 한다.
서버가 실제로 R2를 HEAD해 보고 없는 것을 `missing`으로 돌려주므로, 표시가
거짓말을 해도(중간에 끊겼거나 버킷에서 지워졌거나) 그 자리에서 드러난다.
"""

from __future__ import annotations

import json
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import ahead, filenames, gate, matching
from . import preview as preview_mod
from .filenames import LectureFile
from .watch import assign_run_ids

# 배포된 API. `docs/handoff.md`의 주소이고 --api나 STUDYEZ_API_BASE_URL로 바꾼다.
DEFAULT_API_BASE = "https://studyez-api-97999573571.asia-northeast3.run.app"

LEDGER_NAME = "published.json"

# 서명 URL은 content-type까지 서명한다(botocore가 SignedHeaders에 넣는다).
# 여기서 정한 값과 PUT의 헤더가 다르면 R2가 SignatureDoesNotMatch로 막는다.
CONTENT_TYPES = {".pdf": "application/pdf", ".png": "image/png"}
DEFAULT_CONTENT_TYPE = "application/octet-stream"

UPLOAD_RETRIES = 3


class PublishError(RuntimeError):
    """서버가 거절했거나 연결이 끊겼다. 어느 요청이었는지까지 담는다."""


def content_type(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), DEFAULT_CONTENT_TYPE)


def human(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f}MB"
    # 1KB 아래를 0KB로 적으면 크기를 말한 것이 아니라 안 말한 것이 된다. 다만
    # 진짜 0은 0으로 적는다 — "올린 것 없음"과 "작은 것 하나"는 다른 말이다.
    return f"{max(1, size // 1024)}KB" if size else "0KB"


@dataclass(frozen=True)
class Upload:
    """올릴 파일 하나. `kind`는 계약의 다섯 가지뿐이다."""

    kind: str
    path: Path

    @property
    def filename(self) -> str:
        # Synology 파일명 일부가 NFD다. 서버도 NFC로 모으지만 여기서 맞춰 두어야
        # 표시(`published.json`)와 서버의 키가 같은 문자열이 된다.
        return unicodedata.normalize("NFC", self.path.name)

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    @property
    def mtime(self) -> int:
        return int(self.path.stat().st_mtime)

    @property
    def key(self) -> str:
        return f"{self.kind}/{self.filename}"

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "filename": self.filename,
            "sizeBytes": self.size,
            "contentType": content_type(self.path),
        }


@dataclass
class LecturePlan:
    """한 편이 서버에 밀어 넣을 것 전부."""

    subject: str
    run_id: str
    item: LectureFile
    # 작년 run. Pre-Quiz 산출물이 거기 있어서 `--run-id`가 이쪽으로도 찾아온다
    # (`/prequiz`는 작년 필기로 돌므로 끝난 run_id가 올해 것이 아니다).
    prev_run_id: str = ""
    uploads: list[Upload] = field(default_factory=list)
    run_meta: dict[str, Path] = field(default_factory=dict)   # {"main"|"pre": 경로}
    pre_items: Path | None = None
    preview_url: str = ""
    notes: list[str] = field(default_factory=list)            # 사람이 봐야 할 것
    blocking: list[str] = field(default_factory=list)         # 사람 없이 올리면 안 될 이유
    # 아직 필기가 없는 강의. 시간표 칸에서 세운 자리다. **올해 필기만 없을 뿐
    # Pre-Quiz는 다 붙는다** — 예습이 필요한 쪽이 이쪽이라 그러라고 세운 자리다.
    ahead: bool = False

    @property
    def label(self) -> str:
        return f"{self.subject}/{self.run_id}"

    @property
    def payload(self) -> dict[str, Any]:
        """`POST /api/admin/lectures`의 한 줄. 계약 §강의 하나당 서버가 받는 것."""
        return {
            "subject": self.subject,
            "runId": self.run_id,
            "uid": self.item.uid,
            "date": self.item.date,
            "slot": self.item.slot,
            "slotEnd": self.item.slot_end,
            "startTime": self.item.start_time,
            "title": self.item.title,
            "professors": list(self.item.professors),
            # 필기가 아직 없으면 필기자도 판도 없다. `v1`로 적으면 1판이 올라온
            # 것처럼 보이고 화면이 "필기 v1"이라고 말한다.
            "author": "" if self.ahead else self.item.author,
            "version": None if self.ahead else self.item.version,
        }

    def kinds(self) -> str:
        counts: dict[str, int] = {}
        for upload in self.uploads:
            counts[upload.kind] = counts.get(upload.kind, 0) + 1
        return " ".join(k if n == 1 else f"{k}×{n}" for k, n in counts.items())


# ------------------------------------------------------------------ 계획 세우기


def _preview_url(path: Path) -> str:
    """`preview.md` 머리의 출처 주소. 머리글을 쓰는 쪽에 붙여 두었다."""
    return preview_mod.read_url(path)


def _owns(run_dir: Path, item: LectureFile) -> tuple[bool, str]:
    """이 디렉터리가 정말 이 강의의 것인가. (맞나, 사람이 봐야 할 말)

    `run_id`는 날짜_교시라서 **과목을 포함하지 않는다**(계약 §run_id). 다른 과목이
    같은 교시에 돌면 `runs/260813_03`을 두 강의가 나눠 갖게 되므로, prep.json이
    적어 둔 원본 PDF로 확인한다. 이 확인이 없으면 남의 덱을 올릴 수 있다.
    """
    prep = run_dir / "prep.json"
    if not prep.is_file():
        return False, ""
    try:
        source = str(json.loads(prep.read_text(encoding="utf-8")).get("source_pdf", ""))
    except (OSError, ValueError):
        return False, f"{run_dir.name}/prep.json을 읽지 못했다 — 산출물을 올리지 않는다"

    parsed = filenames.parse(source) if source else None
    if parsed is None:
        return False, f"{run_dir.name}/prep.json의 원본을 읽지 못했다 — 산출물을 올리지 않는다"
    if parsed.uid != item.uid:
        which = "같은 교시의 다른 강의가 쓴 자리다" if parsed.key == item.key else "다른 강의의 것이다"
        return False, f"{run_dir.name}은 {which} ({Path(source).name[:44]}) — 산출물을 올리지 않는다"
    if parsed.version != item.version:
        return True, (f"{run_dir.name}의 산출물은 v{parsed.version}로 만들었는데 필기는 "
                      f"v{item.version}이다 — 덱을 다시 만들어야 한다")
    return True, ""


def _main_apkg(run_dir: Path) -> Path | None:
    """Main-Quiz 덱. `_예습`으로 끝나는 것은 Pre-Quiz 덱이라 뺀다."""
    decks = [p for p in sorted(run_dir.glob("*.apkg")) if not p.stem.endswith("_예습")]
    return decks[0] if decks else None


def _pre_apkg(run_dir: Path) -> Path | None:
    decks = [p for p in sorted(run_dir.glob("*.apkg")) if p.stem.endswith("_예습")]
    return decks[0] if decks else None


def _add_this_year(plan: LecturePlan, run_dir: Path) -> None:
    """올해 run 디렉터리에서 나오는 것 — Main-Quiz."""
    deck = _main_apkg(run_dir)
    if deck:
        plan.uploads.append(Upload("main_apkg", deck))
    meta = run_dir / "run.meta.json"
    if meta.is_file():
        plan.run_meta["main"] = meta
    verdict = gate.inspect(run_dir, deck, meta if meta.is_file() else None, "Main-Quiz")
    plan.notes += verdict.notes
    plan.blocking += verdict.blocking


def _add_prev_year(plan: LecturePlan, run_dir: Path) -> None:
    """작년 run 디렉터리에서 나오는 것 — Pre-Quiz와 예습 대화.

    슬라이드 이미지는 `pre_items`가 있을 때만 따라 올린다. 오답 해설이 그
    번호로 찾는 유일한 소비자이고, 없으면 아무도 읽지 않는다.
    """
    deck = _pre_apkg(run_dir)
    if deck:
        plan.uploads.append(Upload("pre_apkg", deck))
    meta = run_dir / "pre_run.meta.json"
    if meta.is_file():
        plan.run_meta["pre"] = meta
    verdict = gate.inspect(run_dir, deck, meta if meta.is_file() else None, "Pre-Quiz", "pre_")
    plan.notes += verdict.notes
    plan.blocking += verdict.blocking

    items = run_dir / "pre_items.final.json"
    if items.is_file():
        plan.pre_items = items
        for image in sorted((run_dir / "media").glob("*.png")):
            plan.uploads.append(Upload("media", image))

    preview = run_dir / "preview.md"
    if preview.is_file():
        url = _preview_url(preview)
        if url:
            plan.preview_url = url
        else:
            plan.notes.append(f"{run_dir.name}/preview.md에서 출처 주소를 못 읽었다 — 예습 링크를 올리지 않는다")


# 강의록. 파이프라인이 없어도 존재하고, 덱과 무관하게 학생에게 필요하다.
NOTES_KINDS = ("notes_current", "notes_prev")


def hold_artifacts(plan: LecturePlan, why: str = "--notes-only") -> None:
    """강의록만 남기고 파이프라인 산출물을 다음으로 미룬다.

    `--notes-only`로 사람이 부르거나, `studyez.gate`가 막을 것을 찾았을 때 부른다.
    강의록은 그 검토와 무관한 자료라 먼저 나가도 되고, 먼저 나가야 칸이 열린다.

    미룬 것은 지우지 않고 **무엇을 미뤘는지 적는다.** 조용히 빠지면 다음 사람이
    "이 강의는 원래 덱이 없다"고 읽는다.
    """
    held: list[str] = []
    counts: dict[str, int] = {}
    for upload in plan.uploads:
        if upload.kind not in NOTES_KINDS:
            counts[upload.kind] = counts.get(upload.kind, 0) + 1
    held += [kind if n == 1 else f"{kind}×{n}" for kind, n in counts.items()]
    held += [f"run-meta {kind}" for kind in sorted(plan.run_meta)]
    if plan.pre_items:
        held.append("pre-items")
    if plan.preview_url:
        held.append("예습 링크")

    plan.uploads = [upload for upload in plan.uploads if upload.kind in NOTES_KINDS]
    plan.run_meta.clear()
    plan.pre_items = None
    plan.preview_url = ""
    if held:
        plan.notes.append(f"미룬 것 ({why}): {' · '.join(held)}")


def plan_subject(
    root: Path,
    subject: str,
    this_year: str,
    prev_year: str,
    runs_dir: Path,
    notes_only: bool = False,
    gated: bool = True,
    timetable: Path | None = None,
) -> tuple[list[LecturePlan], list[str]]:
    """과목 하나가 올릴 것 전부. (계획, 스캔 경고)

    `match`·`watch`와 같은 눈으로 폴더를 읽는다. 읽지 못한 파일을 조용히 버리지
    않는 것도 같다 — 여기서 빠지면 그 강의는 사이트에 통째로 없다.
    """
    warnings: list[str] = []
    this_scan = filenames.scan(root / subject / "필기" / this_year, expect_year=this_year)
    prev_scan = filenames.scan(root / subject / "필기" / prev_year, expect_year=prev_year)

    for scan, label in ((this_scan, this_year), (prev_scan, prev_year)):
        for path in scan.conflicts:
            warnings.append(f"{subject}: 충돌 사본 제외 — {label}/{path.name[:56]}")
        for stray in scan.misfiled:
            warnings.append(f"{subject}: {label} 폴더에 {stray.date[:4]}년 파일 — {stray.title[:40]}")
        for path in scan.unparsed:
            warnings.append(f"{subject}: 파일명을 읽지 못함 — {label}/{path.name[:56]}")

    this_files = filenames.latest_versions(this_scan.files)
    prev_files = filenames.latest_versions(prev_scan.files)
    run_ids = assign_run_ids(this_files)
    prev_run_ids = assign_run_ids(prev_files)
    matches = {m.this_year.uid: m for m in matching.match_years(this_files, prev_files)}

    plans: list[LecturePlan] = []
    for item in this_files:
        plan = LecturePlan(subject=subject, run_id=run_ids[item.uid], item=item)
        plan.uploads.append(Upload("notes_current", item.path))

        run_dir = runs_dir / plan.run_id
        owned, note = _owns(run_dir, item)
        if note:
            # 판이 어긋난 것(v1로 만든 덱, v3 필기)은 낡은 덱이 올라간다는 뜻이라
            # 사람 없이 내보내면 안 된다. 남의 자리인 경우는 애초에 안 붙는다.
            (plan.blocking if owned else plan.notes).append(note)
        if owned:
            _add_this_year(plan, run_dir)

        match = matches.get(item.uid)
        if match and match.confident and match.prev_year is not None:
            prev = match.prev_year
            plan.uploads.append(Upload("notes_prev", prev.path))
            plan.prev_run_id = prev_run_ids[prev.uid]
            prev_dir = runs_dir / plan.prev_run_id
            prev_owned, prev_note = _owns(prev_dir, prev)
            if prev_note:
                plan.notes.append(prev_note)
            if prev_owned:
                _add_prev_year(plan, prev_dir)
        elif match and match.prev_year is not None:
            plan.notes.append(
                f"작년 짝이 확정이 아니다 ({match.score:.2f}, 후보 {match.prev_year.title[:26]}) — "
                f"작년 강의록·예습을 올리지 않는다. `python -m studyez match {subject}`로 확인하라")
        else:
            plan.notes.append("작년 짝이 없다 — 작년 강의록·예습 자리는 비워 둔다")

        if notes_only:
            hold_artifacts(plan)
        elif gated and plan.blocking:
            hold_artifacts(plan, why="검문")
        plans.append(plan)

    if timetable is not None:
        # 아직 필기가 없는 강의. **예습이 필요한 쪽이 이쪽이다.**
        seats, ahead_warnings = ahead.plan(subject, this_files, prev_files, timetable, runs_dir)
        warnings += ahead_warnings
        for seat in seats:
            plan = LecturePlan(subject=subject, run_id=seat.cell.key,
                               item=seat.cell.as_lecture(), ahead=True)
            if seat.prev is not None:
                plan.uploads.append(Upload("notes_prev", seat.prev.path))
                plan.prev_run_id = prev_run_ids.get(seat.prev.uid, "")
                if seat.source == "confirmed":
                    plan.notes.append(f"작년 짝은 사람이 확인해 준 것이다 (runs/{ahead.PAIRS_DIR}/{subject}.json)")

                # Pre-Quiz도 여기서 붙인다. 한동안 작년 강의록만 붙였는데, 덱이
                # 붙는 자리가 **올해 필기가 올라온 뒤로 밀렸다** — 강의가 지나간
                # 뒤다. 강의 직전에 푸는 퀴즈가 강의 다음 날 도착하는 셈이었다.
                prev_dir = runs_dir / plan.prev_run_id if plan.prev_run_id else None
                if prev_dir is not None:
                    prev_owned, prev_note = _owns(prev_dir, seat.prev)
                    if prev_note:
                        plan.notes.append(prev_note)
                    if prev_owned:
                        _add_prev_year(plan, prev_dir)

            # 위쪽 편과 같은 검문을 받는다. 필기가 없다는 것이 덱을 덜 보는
            # 이유가 되지는 않는다.
            if notes_only:
                hold_artifacts(plan)
            elif gated and plan.blocking:
                hold_artifacts(plan, why="검문")
            plans.append(plan)

    # 필기가 있는 편과 아직 없는 편이 날짜순으로 섞여야 진도 순서로 읽힌다.
    plans.sort(key=lambda plan: (plan.item.date, plan.run_id))
    return plans, warnings


# ------------------------------------------------------------------ 서버


class Client:
    """러너 토큰으로 부르는 API. 실패는 삼키지 않는다."""

    def __init__(self, base: str, token: str, timeout: int = 600) -> None:
        self.base = base.rstrip("/")
        self.token = token
        self.timeout = timeout

    def call(self, method: str, path: str, payload: Any = None) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        return self._open(request)

    def put_file(self, url: str, path: Path) -> None:
        """서명 URL에 파일 본문을 민다.

        content-type이 서명에 들어 있으므로 발급 때 적어 보낸 값과 **같은 헤더**를
        달아야 한다. Content-Length도 직접 넣는다 — 파일 객체를 주면 urllib이
        길이를 모르고 chunked로 보내는데 R2가 그걸 서명과 함께 받지 않는다.

        주소가 상대 경로로 올 수 있다. local-test 모드에서 R2 대신 서버 자신이
        파일을 받는데, `PUBLIC_API_BASE_URL`이 비어 있으면 `/api/local-storage/…`
        만 온다. 같은 서버가 받을 자리이므로 API 주소에 이어 붙인다.
        """
        size = path.stat().st_size
        with path.open("rb") as handle:
            request = urllib.request.Request(
                urllib.parse.urljoin(f"{self.base}/", url),
                data=handle,
                method="PUT",
                headers={"Content-Type": content_type(path), "Content-Length": str(size)},
            )
            self._open(request, parse=False)

    def _open(self, request: urllib.request.Request, parse: bool = True) -> Any:
        where = f"{request.get_method()} {request.full_url.split('?')[0]}"
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace").strip()[:300]
            raise PublishError(f"{exc.code} {where} — {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise PublishError(f"{where} 실패 — {exc}") from exc
        return json.loads(body) if parse and body else None


def lecture_path(subject: str, run_id: str, tail: str = "") -> str:
    quoted = urllib.parse.quote(unicodedata.normalize("NFC", subject), safe="")
    return f"/api/admin/lectures/{quoted}/{urllib.parse.quote(run_id, safe='')}{tail}"


# ------------------------------------------------------------------ 표시(ledger)


def _read_ledger(runs_dir: Path) -> dict[str, Any]:
    path = runs_dir / LEDGER_NAME
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_ledger(runs_dir: Path, api_base: str) -> dict[str, dict[str, dict[str, int]]]:
    """이 서버에 올린 것의 표시.

    **서버마다 따로 센다.** 로컬 테스트 서버와 운영 서버에 같은 자료를 올리는데,
    한 칸만 두면 로컬에 한 번 올리는 순간 운영 기록이 지워지고 다음 배포가
    389MB를 처음부터 다시 민다.
    """
    return _read_ledger(runs_dir).get("apis", {}).get(api_base, {})


def save_ledger(runs_dir: Path, api_base: str, uploaded: dict[str, dict[str, dict[str, int]]]) -> None:
    raw = _read_ledger(runs_dir)
    apis = raw.get("apis")
    if not isinstance(apis, dict):
        apis = {}
    apis[api_base] = uploaded
    (runs_dir / LEDGER_NAME).write_text(
        json.dumps({"apis": apis}, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ 실행


@dataclass
class Report:
    lectures: int = 0
    linked: int = 0
    unlinked: int = 0
    uploaded: int = 0
    uploaded_bytes: int = 0
    skipped: int = 0
    run_meta: int = 0
    pre_items: int = 0
    previews: int = 0
    failures: list[str] = field(default_factory=list)


def publish(
    plans: list[LecturePlan],
    client: Client,
    runs_dir: Path,
    *,
    force: bool = False,
    log: Callable[[str], None] = print,
) -> Report:
    """계획대로 민다. 한 편이 실패해도 나머지는 계속 간다."""
    report = Report(lectures=len(plans))
    if not plans:
        return report

    answer = client.call("POST", "/api/admin/lectures", [plan.payload for plan in plans])
    report.linked = int(answer.get("linked", 0))
    report.unlinked = int(answer.get("unlinked", 0))
    log(f"  강의 {answer.get('received', 0)}편 등록 — 시간표에 붙은 것 {report.linked}, "
        f"안 붙은 것 {report.unlinked}")

    uploaded = load_ledger(runs_dir, client.base)
    for plan in plans:
        try:
            _publish_one(plan, client, uploaded, report, force=force, log=log)
        except PublishError as exc:
            report.failures.append(f"{plan.label} — {exc}")
            log(f"    ✗ {plan.label} — {exc}")
        except Exception as exc:                        # noqa: BLE001
            # 한 편 때문에 나머지 열세 편을 잃지 않는다. PublishError만 잡았더니
            # 서버가 상대 주소를 준 날 urllib의 ValueError가 실행을 통째로 죽였다.
            report.failures.append(f"{plan.label} — {type(exc).__name__}: {exc}")
            log(f"    ✗ {plan.label} — {type(exc).__name__}: {exc}")
        finally:
            # 한 편이 끝날 때마다 적는다. 중간에 멈춰도 다음 실행이 이어 간다.
            save_ledger(runs_dir, client.base, uploaded)
    return report


def _publish_one(
    plan: LecturePlan,
    client: Client,
    uploaded: dict[str, dict[str, dict[str, int]]],
    report: Report,
    *,
    force: bool,
    log: Callable[[str], None],
) -> None:
    base = lecture_path(plan.subject, plan.run_id)
    payloads = [upload.payload() for upload in plan.uploads]

    signed = client.call("POST", f"{base}/uploads", payloads)
    urls = {entry["filename"]: entry["uploadUrl"] for entry in signed["files"]}

    # 서버가 R2를 HEAD해 본다. 여기서 나온 `missing`이 표시보다 세다 — 표시가
    # 있어도 버킷에 없으면 다시 올려야 하고, 없어도 버킷에 있으면 등록만 하면 된다.
    done = uploaded.setdefault(plan.label, {})
    present = client.call("POST", f"{base}/uploads/complete", payloads)
    missing = set(present.get("missing", []))

    pending = [
        upload for upload in plan.uploads
        if force
        or upload.filename in missing
        or done.get(upload.key, {}).get("size") != upload.size
        or done.get(upload.key, {}).get("mtime") != upload.mtime
    ]
    report.skipped += len(plan.uploads) - len(pending)

    if pending:
        total = sum(upload.size for upload in pending)
        log(f"    {plan.label} — 올릴 것 {len(pending)}개 ({human(total)})")
    for upload in pending:
        started = time.monotonic()
        _put_with_retry(client, urls[upload.filename], upload)
        report.uploaded += 1
        report.uploaded_bytes += upload.size
        done[upload.key] = {"size": upload.size, "mtime": upload.mtime}
        log(f"      {upload.kind:<14} {upload.filename[:46]:<46} "
            f"{human(upload.size):>8}  {time.monotonic() - started:.1f}초")

    if pending:
        checked = client.call("POST", f"{base}/uploads/complete", [u.payload() for u in pending])
        for name in checked.get("missing", []):
            # 올렸다는데 서버가 못 찾는다. 세지 않고 표시도 지운다.
            report.failures.append(f"{plan.label} — 올렸는데 서버가 못 찾는다: {name}")
            for upload in pending:
                if upload.filename == name:
                    done.pop(upload.key, None)

    for quiz_kind, path in sorted(plan.run_meta.items()):
        client.call("PUT", f"{base}/run-meta/{quiz_kind}",
                    json.loads(path.read_text(encoding="utf-8")))
        report.run_meta += 1

    if plan.pre_items is not None:
        raw = json.loads(plan.pre_items.read_text(encoding="utf-8"))
        payload = raw if isinstance(raw, dict) else {"items": raw}
        answer = client.call("PUT", f"{base}/pre-items", payload)
        report.pre_items += int(answer.get("itemCount", 0))

    if plan.preview_url:
        client.call("PUT", f"{base}/preview", {"provider": _provider(plan.preview_url),
                                               "shareUrl": plan.preview_url})
        report.previews += 1


def _provider(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if "claude" in host:
        return "claude"
    if "gemini" in host or "google" in host:
        return "gemini"
    return "chatgpt"


def _put_with_retry(client: Client, url: str, upload: Upload) -> None:
    """끊긴 업로드는 다시 시도한다. 30~56MB짜리가 한 번 튄다고 편을 버리지 않는다."""
    for attempt in range(1, UPLOAD_RETRIES + 1):
        try:
            client.put_file(url, upload.path)
            return
        except PublishError:
            if attempt == UPLOAD_RETRIES:
                raise
            time.sleep(2 * attempt)
