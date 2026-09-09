"""
Fix documents stuck in 'reconciling' status after server restart.
Run: .venv\Scripts\python -m scripts.fix_stuck_docs
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import asyncpg
from app.config import get_settings
from app.db.connection import _asyncpg_url


async def main():
    settings = get_settings()
    pool = await asyncpg.create_pool(
        _asyncpg_url(settings.database_url), ssl="require", statement_cache_size=0
    )
    try:
        async with pool.acquire() as conn:
            stuck = await conn.fetch(
                "SELECT id, title, status FROM documents WHERE status = 'reconciling'"
            )
            if not stuck:
                print("No stuck documents found.")
                return

            for d in stuck:
                print(f"  Fixing: {d['title']} ({d['id']}) — was '{d['status']}'")
                await conn.execute(
                    "UPDATE documents SET status = 'done', updated_at = NOW() WHERE id = $1",
                    d['id']
                )

            print(f"\nFixed {len(stuck)} stuck documents -> 'done'")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
