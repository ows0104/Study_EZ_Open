"""운영 DB에 족보 회독 표 `jokbo_round` 하나만 만든다(족보 회독 PR 병합 전에).

init-db 전체(호환 칼럼·권한 옮기기)를 돌리지 않고 이 표만 create_all 한다.
이미 있으면 건드리지 않는다. 기존 표·데이터는 읽지도 바꾸지도 않는다. RLS는 만들 때 켠다.

    cd server
    .venv\\Scripts\\python.exe ../docs/changes/2026-11-14-jokbo-read/create_table.py <운영 .env 경로>
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

if len(sys.argv) != 2 or not Path(sys.argv[1]).is_file():
    raise SystemExit("운영 .env 파일 경로를 하나 주세요.")
load_dotenv(sys.argv[1], override=True)
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "server"))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.models.jokbo import JokboRound  # noqa: E402

TABLES = [JokboRound.__table__]

if engine.dialect.name != "postgresql":
    raise SystemExit(f"postgres가 아닙니다({engine.dialect.name}). 운영 .env인지 확인하세요.")

before = set(inspect(engine).get_table_names())
Base.metadata.create_all(engine, tables=TABLES)
after = set(inspect(engine).get_table_names())

with engine.connect() as conn:
    for table in TABLES:
        rls = conn.execute(text("select relrowsecurity from pg_class where relname = :n"), {"n": table.name}).scalar()
        state = "새로 만듦" if table.name not in before else "이미 있음(그대로 둠)"
        print(f"{table.name}: {state if table.name in after else '없음!'} · RLS {'켜짐' if rls else '꺼짐!'}")
