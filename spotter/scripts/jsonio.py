"""JSON 파일 하나를 읽고 쓰는 자리.

`json.load(open(path))` 는 파일을 안 닫는다. CPython 에서는 참조가 끊기는 순간
닫히지만 그건 구현이 그런 것이고, 예외가 나는 경로에서는 그때도 안 닫힌다.
여기 스크립트들은 한 번에 수백 개를 여는 것이 있어서(`map_images` 가 사진마다,
`audit_baked_text` 가 배포본 전체) 그 자리가 실제로 물린다.

**한 줄짜리를 `with` 블록 스무 개로 늘리지 않으려고** 이 모듈을 둔다. 읽는 쪽은
그대로 한 줄이고 닫는 것은 여기서 한 번만 적는다.

    from jsonio import load_json, dump_json

    db = load_json(DB)
    dump_json(OUT, payload)

스크립트를 `python scripts/<이름>.py` 로 돌리면 그 폴더가 `sys.path[0]` 이라
이 형제 import 가 그냥 된다. `build_web.py` 가 `generate_exam` 을 부르는 것과
같은 자리다.
"""

import json


def load_json(path, default=None):
    """JSON 하나. `default` 를 주면 파일이 없을 때 그것을 돌려준다.

    **없는 것과 깨진 것을 가르지 않는다.** 깨진 파일은 그대로 올려 보낸다 —
    이 저장소가 「없다로 읽히는 0」이라 부르는 자리를 여기서 만들지 않는다.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        if default is None:
            raise
        return default


def dump_json(path, obj, indent=2):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent)


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def read_text(path, encoding="utf-8"):
    with open(path, encoding=encoding) as fh:
        return fh.read()


def write_text(path, text, encoding="utf-8", newline=""):
    with open(path, "w", encoding=encoding, newline=newline) as fh:
        fh.write(text)
