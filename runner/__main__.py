"""`python -m runner` 진입점. 명령 구현은 runner/cli/에서 관리한다.

기존 helper import를 유지하며, 콘솔 설정 뒤 CLI로 넘긴다.
"""

import sys
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 콘솔 기본 cp949로는 한글이 깨진다.
for _stream in (sys.stdout, sys.stderr):
    with suppress(Exception):
        _stream.reconfigure(encoding="utf-8")

# 재노출은 기존 helper import를 위한 것이다. 콘솔 설정 뒤에 불러온다.
from runner.cli import DEFAULT_ROOT, REPO_ROOT  # noqa: E402, F401
from runner.cli.artifacts import (  # noqa: E402, F401
    KEEP_ON_IMPORT,
    RE_WORK_DIR,
    import_dirs,
    run_chosen,
    run_import,
    run_promote,
    run_rebuild,
    run_release,
)
from runner.cli.main import main, run_bank  # noqa: E402, F401
from runner.cli.materials import (  # noqa: E402, F401
    OLDER_JOKBO_YEARS,
    notes_dir,
    older_pdfs,
    practical_pdfs,
    remembered_practical,
    report_subject,
    run_jokbo,
    run_preview,
)

if __name__ == "__main__":
    raise SystemExit(main())
