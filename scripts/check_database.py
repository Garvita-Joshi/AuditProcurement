"""Check that AuditAI can connect to its configured PostgreSQL database."""
import sys
from pathlib import Path

# Permit `python scripts/check_database.py` from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from backend.app.db import engine


def main() -> None:
    """Connect to PostgreSQL and print its version and available tables."""
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version()")).scalar_one()
        tables = connection.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
        ).scalars().all()

    print("Database connection: successful")
    print(f"PostgreSQL: {version}")
    print("Tables:", ", ".join(tables) if tables else "none yet")


if __name__ == "__main__":
    main()
