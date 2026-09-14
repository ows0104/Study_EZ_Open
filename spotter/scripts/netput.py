"""서명받은 주소에 바이트를 붓는다. **끊기면 다시 시도한다.**

2026-09-14 에 `refactor-plan` Phase 2(올리는 쪽 둘을 맞대 보기)를 하다가 나왔다.
겹치는 코드는 거의 없었지만 — 엔드포인트가 다르고(`/api/admin/lectures` vs
`/api/spotter/admin/…`) 계획·문지기·원장이 통째로 Study_EZ 쪽에만 있다 —
**한쪽에만 있는 것이 하나 있었다.**

    runner/publish.py          재시도 3회. 「30~56MB짜리가 한 번 튄다고
                               편을 버리지 않는다」고 그 자리에 적혀 있다
    spotter/scripts/upload_*   없음. 한 번 튀면 그 실행이 죽는다

땡시 쪽이 더 아쉬운 자리다 — 한 과목이 사진 수백 장을 배치로 올린다.
**잃는 것은 없다**(이미 올린 것은 ETag 로 건너뛰므로 다시 돌리면 이어 간다).
그래도 사람이 다시 쳐야 하는 것과 저절로 잇는 것은 다르다.

여기 있는 것은 그 재시도 하나다. 계획·문지기는 안 옮긴다 — 그쪽은 Study_EZ 의
강의 판 비교(`_owns`)에 묶여 있어서 땡시에 옮길 것이 없다.
"""

import time

import requests

RETRIES = 3
BACKOFF = 2          # 초. 시도마다 곱해서 늘린다 (2s → 4s)


def put(url, data, content_type, timeout=600, retries=RETRIES):
    """PUT 한 번. 실패하면 `retries` 번까지 다시 시도한다.

    **`data` 가 파일 객체면 다시 읽을 수 있게 되감는다.** 안 되감으면 두 번째
    시도가 0바이트를 올리고, 서버는 200을 돌려주며, 사진이 빈 채로 올라간다 —
    실패보다 나쁘다.
    """
    for attempt in range(1, retries + 1):
        try:
            if hasattr(data, "seek"):
                data.seek(0)
            r = requests.put(url, data=data, headers={"Content-Type": content_type},
                             timeout=timeout)
            r.raise_for_status()
            return r
        except (requests.RequestException, OSError):
            if attempt == retries:
                raise
            time.sleep(BACKOFF * attempt)
    raise AssertionError("닿을 수 없는 자리")   # pragma: no cover
