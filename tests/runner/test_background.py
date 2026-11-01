import json
import os
import sys

import pytest

from runner.background import launch


def test_background_keeps_utf8_output_and_appends_without_consuming_input(tmp_path):
    log = tmp_path / "output.log"
    log.write_text("기존 기록\n", encoding="utf-8")
    process = launch([sys.executable, "-c", "import sys; print('검수 기록'); print(repr(sys.stdin.read()))"],
                     cwd=tmp_path, log=log)
    assert process.wait(timeout=15) == 0
    assert log.read_text(encoding="utf-8").splitlines() == ["기존 기록", "검수 기록", "''"]


@pytest.mark.skipif(os.name != "nt", reason="Windows console creation contract")
def test_windows_child_has_no_console(tmp_path):
    log = tmp_path / "console.log"
    process = launch([sys.executable, "-c", "import ctypes,json; print(json.dumps({'console':bool(ctypes.windll.kernel32.GetConsoleWindow())}))"],
                     cwd=tmp_path, log=log)
    assert process.wait(timeout=15) == 0
    assert json.loads(log.read_text(encoding="utf-8"))["console"] is False
