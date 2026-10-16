"""Generate a fresh CTG AI schema offline; never connect to PostgreSQL."""
import argparse
import importlib
import sys
from pathlib import Path

from sqlalchemy import create_mock_engine

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def build_schema():
    from app.core.database import Base

    for path in sorted((BACKEND / "app/models").glob("*.py")):
        if path.stem != "__init__":
            importlib.import_module("app.models." + path.stem)

    assert "users" not in Base.metadata.tables
    assert "user_roles" not in Base.metadata.tables
    output = [
        "-- CTG AI: fresh database schema generated offline from current ORM.",
        "-- Contains no data or credentials. Not a migration for an existing database.",
        "-- Historical ctg_init.sql / ctg_01_schema.sql are pre-cleanup snapshots.",
        "BEGIN;",
        "CREATE EXTENSION IF NOT EXISTS vector;",
    ]

    def compile_statement(sql, *args, **kwargs):
        output.append(str(sql.compile(dialect=engine.dialect)).strip() + ";")

    engine = create_mock_engine("postgresql://", compile_statement)
    Base.metadata.create_all(engine, checkfirst=False)
    output.append("COMMIT;")
    return "\n\n".join(output) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BACKEND / "database/ctg_ai_schema.sql")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_schema(), encoding="utf-8")
    print("Generated schema:", args.output)
