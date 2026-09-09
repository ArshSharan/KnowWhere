"""
Find the specific fact UUIDs being reconciled in logs and see what their entity/attribute is.
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

# The UUIDs we saw in the terminal reconciliation logs
SAMPLE_IDS = [
    "575f371b-b9b1-432f-bcf3-0f574249eb12",
    "a3c9d989-15e1-4756-a810-6f7f8ef43eeb",
    "e2cc6b6e-6324-4e40-82cb-86097b36258a",
    "974c8252-0ffe-4f75-af50-a13a169c6b7e",
    "3b37b09f-3251-4bc3-bd4b-7c8727f3c75c",
    "d144a034-6c88-4178-9941-8e309a7450ee",
]


async def main():
    settings = get_settings()
    pool = await asyncpg.create_pool(
        _asyncpg_url(settings.database_url), ssl="require", statement_cache_size=0
    )
    try:
        async with pool.acquire() as conn:
            # 1. What document had reconcile called on it?
            print("=== RECENT DOCUMENTS ===")
            docs = await conn.fetch(
                "SELECT id, title, status, created_at FROM documents ORDER BY created_at DESC LIMIT 6"
            )
            for d in docs:
                print(f"  {d['id']} | {d['status']} | {d['title']}")

            # 2. Identify which document the sample fact IDs belong to and what they are
            print("\n=== SAMPLE FACT DETAILS (from terminal logs) ===")
            for fid in SAMPLE_IDS:
                row = await conn.fetchrow("""
                    SELECT f.id, f.attribute, f.value, f.unit, f.fiscal_year,
                           e.canonical_name AS entity_name, d.title AS doc_title,
                           f.verbatim_quote
                    FROM facts f
                    JOIN entities e ON e.id = f.entity_id
                    JOIN documents d ON d.id = f.document_id
                    WHERE f.id = $1
                """, fid)
                if row:
                    print(f"\n  Fact: {row['id']}")
                    print(f"    Doc: {row['doc_title']}")
                    print(f"    Entity: {row['entity_name']}")
                    print(f"    Attribute: {row['attribute']} = {row['value']} {row['unit'] or ''} ({row['fiscal_year'] or 'no FY'})")
                    print(f"    Quote: {row['verbatim_quote'][:100] if row['verbatim_quote'] else 'N/A'}")
                else:
                    print(f"\n  Fact {fid}: NOT FOUND in DB")

            # 3. Sample what the new unrelated pairs look like in the DB
            print("\n=== LAST 5 UNRELATED PAIRS STORED ===")
            unrelateds = await conn.fetch("""
                SELECT fr.id, fr.confidence, fr.explanation,
                       fa.attribute AS a_attr, fa.value AS a_val,
                       ea.canonical_name AS a_entity, da.title AS a_doc,
                       fb.attribute AS b_attr, fb.value AS b_val,
                       eb.canonical_name AS b_entity, db.title AS b_doc
                FROM fact_relationships fr
                JOIN facts fa ON fa.id = fr.fact_a_id
                JOIN facts fb ON fb.id = fr.fact_b_id
                JOIN entities ea ON ea.id = fa.entity_id
                JOIN entities eb ON eb.id = fb.entity_id
                JOIN documents da ON da.id = fa.document_id
                JOIN documents db ON db.id = fb.document_id
                WHERE fr.relationship = 'unrelated'
                ORDER BY fr.updated_at DESC
                LIMIT 5
            """)
            for r in unrelateds:
                print(f"\n  Pair [{r['id']}] conf={r['confidence']}")
                print(f"    A: {r['a_entity']} | {r['a_attr']} = {r['a_val']} | {r['a_doc'][:40]}")
                print(f"    B: {r['b_entity']} | {r['b_attr']} = {r['b_val']} | {r['b_doc'][:40]}")
                print(f"    Reason: {r['explanation'][:120] if r['explanation'] else 'N/A'}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
