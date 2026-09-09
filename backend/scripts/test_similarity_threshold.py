"""
Test what actual candidates generate_candidates() returns for known-good corroborating facts.
We know NWC days (net_working_capital_days) should be a corroboration.
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
from app.services.reconciler import generate_candidates, CANDIDATE_K


async def main():
    settings = get_settings()
    pool = await asyncpg.create_pool(
        _asyncpg_url(settings.database_url), ssl="require", statement_cache_size=0
    )
    try:
        async with pool.acquire() as conn:
            # 1. Find the NWC days fact from the annual report (we know it's a corroboration)
            nwc_facts = await conn.fetch("""
                SELECT f.id, f.attribute, f.value, f.entity_id, f.document_id, f.embedding IS NOT NULL as has_emb,
                       d.title
                FROM facts f
                JOIN documents d ON d.id = f.document_id
                WHERE LOWER(f.attribute) LIKE '%working_capital%'
                   OR LOWER(f.attribute) LIKE '%nwc%'
                   OR (LOWER(f.attribute) LIKE '%net_working%')
            """)
            print(f"=== NWC/Working Capital Facts Found: {len(nwc_facts)} ===")
            for f in nwc_facts:
                print(f"  {f['id']} | {f['attribute']} = {f['value']} | {f['title'][:50]} | has_embedding: {f['has_emb']}")

            # 2. For EACH NWC fact, try generate_candidates with DIFFERENT thresholds
            # to understand why the threshold might be killing good pairs
            entity_id = "eb485d81-1b22-464a-9926-f60b28bc2cc8"  # Delhivery Limited

            print("\n=== CHECKING CANDIDATE SIMILARITY SCORES FOR NWC FACTS ===")
            for nwc in nwc_facts:
                if not nwc['has_emb']:
                    print(f"  SKIP (no embedding): {nwc['attribute']}")
                    continue

                # Get raw similarity scores
                rows = await conn.fetch("""
                    SELECT f.id, f.attribute, f.value,
                           d.title,
                           1 - (f.embedding <=> (SELECT embedding FROM facts WHERE id = $1)::vector) AS similarity
                    FROM facts f
                    JOIN documents d ON d.id = f.document_id
                    WHERE f.entity_id = $2
                      AND f.id != $1
                      AND f.embedding IS NOT NULL
                    ORDER BY similarity DESC
                    LIMIT 15
                """, nwc['id'], entity_id)

                print(f"\n  Fact: {nwc['attribute']} = {nwc['value']} ({nwc['title'][:40]})")
                print(f"  Top candidates (all similarity scores):")
                for r in rows:
                    doc_short = r['title'][:35] if r['title'] else "?"
                    flag = " <-- BELOW 0.70 threshold" if r['similarity'] < 0.70 else " *** PASSES threshold"
                    print(f"    sim={r['similarity']:.3f}{flag} | {r['attribute']} = {r['value']} | {doc_short}")

            # 3. Check PTL growth (30% corroboration)
            print("\n=== CHECKING PTL TONNAGE FACTS ===")
            ptl_facts = await conn.fetch("""
                SELECT f.id, f.attribute, f.value, f.entity_id, d.title,
                       f.embedding IS NOT NULL as has_emb
                FROM facts f
                JOIN documents d ON d.id = f.document_id
                WHERE LOWER(f.attribute) LIKE '%ptl%'
                   OR LOWER(f.attribute) LIKE '%tonnage%'
                   OR LOWER(f.attribute) LIKE '%truckload%'
            """)
            print(f"Found {len(ptl_facts)} PTL/tonnage facts")
            for f in ptl_facts:
                print(f"  {f['attribute']} = {f['value']} | {f['title'][:50]} | emb: {f['has_emb']}")

            # 4. What are the exact candidate similarity scores between the documents' Delhivery Limited facts?
            print("\n=== PAIRWISE SIMILARITY BETWEEN DOC FACTS (sample 5x5) ===")
            doc_facts_sample = await conn.fetch("""
                SELECT f.id, f.attribute, f.value, f.embedding IS NOT NULL as has_emb, d.title
                FROM facts f
                JOIN documents d ON d.id = f.document_id
                WHERE f.entity_id = $1
                  AND f.embedding IS NOT NULL
                  AND d.title != 'Testing_RAG_KnowWhere.pdf'
                ORDER BY d.title, f.attribute
                LIMIT 20
            """, entity_id)
            print(f"Sample Delhivery facts across docs: {len(doc_facts_sample)}")
            for f in doc_facts_sample[:8]:
                print(f"  {f['attribute']} = {f['value']} | {f['title'][:40]}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
