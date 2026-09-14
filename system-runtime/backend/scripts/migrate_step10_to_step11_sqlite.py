"""Small SQLite migration helper for local Step 10 -> Step 11 databases.

Back up the database file before running this script. It only adds nullable
Judgment metadata columns and an index; it does not rewrite old history.
"""

import sys
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine


REQUIRED_COLUMNS = {
    "reevaluation_trigger": "VARCHAR(32)",
    "decision_snapshot": "JSON",
    "decision_fingerprint": "VARCHAR(64)",
}


def main() -> None:
    if engine.dialect.name != "sqlite":
        raise SystemExit("This helper is intentionally SQLite-only. Use a real migration tool for PostgreSQL.")

    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns("judgments")}

    with engine.begin() as connection:
        for name, sql_type in REQUIRED_COLUMNS.items():
            if name in existing:
                print(f"skip: judgments.{name} already exists")
                continue
            connection.execute(text(f"ALTER TABLE judgments ADD COLUMN {name} {sql_type}"))
            print(f"added: judgments.{name}")

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_judgments_decision_fingerprint "
                "ON judgments (decision_fingerprint)"
            )
        )
        print("index ready: ix_judgments_decision_fingerprint")

    print("Step 11 SQLite migration complete. Existing rows remain unchanged and may have NULL Step 11 metadata.")


if __name__ == "__main__":
    main()
