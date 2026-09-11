"""Apply the original schema and additive migrations without deleting existing data."""
import asyncio
import sys
from pathlib import Path
import asyncpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.config import settings


async def migrate():
    connection = await asyncpg.connect(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        async with connection.transaction():
            await connection.execute("SELECT pg_advisory_xact_lock(26104)")
            for path in [ROOT / "init.sql", *sorted((ROOT / "config/migrations").glob("*.sql"))]:
                await connection.execute(path.read_text(encoding="utf-8"))
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(migrate())
    print("Schema migration complete; existing records preserved.")
