"""SQLite helper for local Step 11 -> Step 12 databases.

Back up the database before running this script. Step 12 adds the
source_verifications audit table. Existing evidence and history rows are not
rewritten.
"""

import sys
from pathlib import Path

from sqlalchemy import inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine
from app.models import SourceVerification


def main() -> None:
    if engine.dialect.name != "sqlite":
        raise SystemExit(
            "This helper is intentionally SQLite-only. Use a real migration tool for PostgreSQL."
        )

    SourceVerification.__table__.create(bind=engine, checkfirst=True)
    tables = set(inspect(engine).get_table_names())
    if "source_verifications" not in tables:
        raise SystemExit("Migration failed: source_verifications table was not created")

    print("table ready: source_verifications")
    print(
        "Step 12 SQLite migration complete. Existing evidence remains unchanged; "
        "new verification records start from the first Step 12 verification."
    )


if __name__ == "__main__":
    main()
