"""Runner 명령의 인자, 자료 준비, 산출물 관리를 나누어 둔다."""

from pathlib import Path

DEFAULT_ROOT = Path.home() / "SynologyDrive"
REPO_ROOT = Path(__file__).resolve().parents[2]
