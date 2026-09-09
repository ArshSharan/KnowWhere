"""
Diagnostic: check entity distribution, facts-per-entity, and sample candidate pairs.
Run: .venv\Scripts\python -m scripts.diagnose_entities
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

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
            # 1. All entities
            entities = await conn.fetch(
                "SELECT id, canonical_name, array_length(aliases, 1) AS alias_count "
                "FROM entities ORDER BY alias_count DESC NULLS LAST"
            )
            print("=== ALL ENTITIES ===")
            for e in entities:
                print(f"  {e['id']} | {e['canonical_name']} | aliases: {e['alias_count']}")

            # 2. Facts per entity per document
            print("\n=== FACTS PER ENTITY PER DOCUMENT ===")
            rows = await conn.fetch("""
                SELECT e.canonical_name, d.title, COUNT(f.id) AS fact_count
                FROM facts f
                JOIN entities e ON e.id = f.entity_id
                JOIN documents d ON d.id = f.document_id
                GROUP BY e.id, e.canonical_name, d.id, d.title
                ORDER BY e.canonical_name, d.title
            """)
            for r in rows:
                print(f"  [{r['canonical_name']}] | {r['title'][:50]} | {r['fact_count']} facts")

            # 3. Relationship distribution
            print("\n=== CURRENT RELATIONSHIP DISTRIBUTION ===")
            rel_counts = await conn.fetch(
                "SELECT relationship, COUNT(*) AS cnt FROM fact_relationships GROUP BY relationship"
            )
            for r in rel_counts:
                print(f"  {r['relationship']}: {r['cnt']}")

            # 4. Sample 3 facts from new doc (highest doc_id by created_at) and show what their entity_id is
            print("\n=== SAMPLE FACTS FROM EACH DOCUMENT (entity_id check) ===")
            docs = await conn.fetch(
                "SELECT id, title FROM documents ORDER BY created_at DESC LIMIT 5"
            )
            for doc in docs:
                sample_facts = await conn.fetch("""
                    SELECT f.id, f.attribute, f.value, f.entity_id, e.canonical_name
                    FROM facts f
                    JOIN entities e ON e.id = f.entity_id
                    WHERE f.document_id = $1
                    LIMIT 3
                """, doc['id'])
                print(f"\n  Doc: {doc['title'][:60]}")
                for sf in sample_facts:
                    print(f"    Fact: {sf['attribute']} = {sf['value']} | entity: {sf['canonical_name']} ({sf['entity_id']})")

            # 5. Check if any facts SHARE the same entity_id across documents
            print("\n=== ENTITY IDs APPEARING IN MULTIPLE DOCUMENTS ===")
            shared = await conn.fetch("""
                SELECT e.canonical_name, e.id AS entity_id, COUNT(DISTINCT f.document_id) AS doc_count
                FROM facts f
                JOIN entities e ON e.id = f.entity_id
                GROUP BY e.id, e.canonical_name
                HAVING COUNT(DISTINCT f.document_id) > 1
                ORDER BY doc_count DESC
            """)
            if not shared:
                print("  *** NONE — facts from different documents share NO entity_id. This is the bug! ***")
            else:
                for r in shared:
                    print(f"  {r['canonical_name']} ({r['entity_id']}) appears in {r['doc_count']} docs")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
