"""올리다 끊기면 다시 시도하는가.

2026-09-14 `refactor-plan` Phase 2(올리는 쪽 둘을 맞대 보기)에서 나왔다.
겹치는 코드는 거의 없었고 — 엔드포인트도 계획도 문지기도 다르다 — **한쪽에만
있는 것이 하나** 있었다. `runner/publish.py` 는 재시도를 달고 그 자리에
「30~56MB짜리가 한 번 튄다고 편을 버리지 않는다」고 적어 두었는데, 땡시 쪽
업로드에는 아예 없었다. 한 과목이 사진 수백 장을 배치로 올린다.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "spotter" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import netput  # noqa: E402


class _Resp:
    def __init__(self, ok=True):
        self.ok = ok

    def raise_for_status(self):
        if not self.ok:
            raise netput.requests.HTTPError("500")


def test_한_번_튀면_다시_시도한다(monkeypatch):
    calls = []

    def fake_put(url, data=None, headers=None, timeout=None):
        calls.append(url)
        return _Resp(ok=len(calls) > 1)     # 첫 번째만 실패

    monkeypatch.setattr(netput.requests, "put", fake_put)
    monkeypatch.setattr(netput.time, "sleep", lambda _s: None)
    netput.put("https://r2/x.jpg", b"bytes", "image/jpeg")
    assert len(calls) == 2


def test_끝까지_안_되면_올려_보낸다(monkeypatch):
    monkeypatch.setattr(netput.requests, "put",
                        lambda *a, **k: (_ for _ in ()).throw(netput.requests.ConnectionError()))
    monkeypatch.setattr(netput.time, "sleep", lambda _s: None)
    with pytest.raises(netput.requests.RequestException):
        netput.put("https://r2/x.jpg", b"bytes", "image/jpeg")


def test_다시_시도하기_전에_파일을_되감는다(monkeypatch):
    """**되감지 않으면 두 번째 시도가 0바이트를 올린다.** 서버는 200을 돌려주고
    사진이 빈 채로 올라간다 — 실패보다 나쁘다."""
    import io
    fh = io.BytesIO(b"abcdef")
    seen = []

    def fake_put(url, data=None, headers=None, timeout=None):
        seen.append(data.read())
        return _Resp(ok=len(seen) > 1)

    monkeypatch.setattr(netput.requests, "put", fake_put)
    monkeypatch.setattr(netput.time, "sleep", lambda _s: None)
    netput.put("https://r2/x.jpg", fh, "image/jpeg")
    assert seen == [b"abcdef", b"abcdef"]


def test_올리는_쪽에_날_PUT_이_안_남아_있다():
    """재시도를 우회하는 길을 남기지 않는다."""
    for name in ("upload_web.py", "upload_subject.py"):
        body = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "requests.put" not in body, name
