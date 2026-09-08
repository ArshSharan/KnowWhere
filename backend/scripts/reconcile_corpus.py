import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import asyncpg
from openai import AsyncOpenAI

from app.config import get_settings
from app.db.connection import _asyncpg_url
from app.db import crud
from app.services.reconciler import reconcile_pair

sys.stdout.reconfigure(encoding='utf-8')

# Concurrency semaphore for OpenAI API calls
SEMAPHORE = asyncio.Semaphore(6)

async def reconcile_and_save(fact_a, fact_b, pool, client):
    async with SEMAPHORE:
        try:
            result = await reconcile_pair(fact_a, fact_b, client)
            await crud.upsert_fact_relationship(
                pool,
                fact_a_id=fact_a["id"],
                fact_b_id=fact_b["id"],
                relationship=result.relationship.value,
                basis=result.reconciliation_basis.value,
                explanation=result.explanation,
                confidence=result.confidence,
            )
            print(f"[{result.relationship.value.upper()}] ({result.reconciliation_basis.value}) {fact_a['attribute']} <-> {fact_b['attribute']}: {result.explanation[:80]}...", flush=True)
            return result.relationship.value
        except Exception as e:
            print(f"Error reconciling [{fact_a['id']}] <-> [{fact_b['id']}]: {e}", flush=True)
            return "error"

async def main():
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    pool = await asyncpg.create_pool(_asyncpg_url(settings.database_url), ssl="require", statement_cache_size=0)
    
    try:
        async with pool.acquire() as conn:
            # First, clean out the old dummy 'unrelated' pairs that paired dates with holding company
            deleted = await conn.execute("DELETE FROM fact_relationships WHERE relationship = 'unrelated'")
            print(f"Cleared old unrelated boilerplate pairs: {deleted}", flush=True)
            
            # Fetch all documents
            docs = await conn.fetch("SELECT id, title FROM documents ORDER BY created_at")
            print(f"Documents in DB: {[d['title'] for d in docs]}", flush=True)
            
            # Find candidate pairs across different documents for the same entity
            # We look for:
            # 1. Exact attribute matches
            # 2. Key topic matches (revenue, ebitda, express, freight, pin, address, office, director, board, asset, liability, equity, capital)
            # 3. High vector similarity (>= 0.70)
            
            query = """
                WITH paired_facts AS (
                    SELECT 
                        fa.id as a_id, fa.attribute as a_attr, fa.value as a_val, fa.unit as a_unit,
                        fa.fiscal_year as a_fy, fa.page_number as a_p, fa.verbatim_quote as a_q,
                        fa.document_id as a_doc_id, ea.canonical_name as a_entity,
                        fb.id as b_id, fb.attribute as b_attr, fb.value as b_val, fb.unit as b_unit,
                        fb.fiscal_year as b_fy, fb.page_number as b_p, fb.verbatim_quote as b_q,
                        fb.document_id as b_doc_id, eb.canonical_name as b_entity,
                        ROW_NUMBER() OVER(PARTITION BY fa.attribute ORDER BY fa.id) as rn
                    FROM facts fa
                    JOIN facts fb ON fb.entity_id = fa.entity_id 
                                 AND fb.document_id > fa.document_id
                    JOIN entities ea ON ea.id = fa.entity_id
                    JOIN entities eb ON eb.id = fb.entity_id
                    WHERE (
                        -- Exact or case-insensitive attribute match
                        LOWER(fa.attribute) = LOWER(fb.attribute)
                        -- Or shared key financial/operational terms
                        OR (fa.attribute ILIKE '%revenue%' AND fb.attribute ILIKE '%revenue%')
                        OR (fa.attribute ILIKE '%ebitda%' AND fb.attribute ILIKE '%ebitda%')
                        OR (fa.attribute ILIKE '%parcel%' AND fb.attribute ILIKE '%parcel%')
                        OR (fa.attribute ILIKE '%freight%' AND fb.attribute ILIKE '%freight%')
                        OR (fa.attribute ILIKE '%pin%' AND fb.attribute ILIKE '%pin%')
                        OR (fa.attribute ILIKE '%office%' AND fb.attribute ILIKE '%office%')
                        OR (fa.attribute ILIKE '%address%' AND fb.attribute ILIKE '%address%')
                        OR (fa.attribute ILIKE '%director%' AND fb.attribute ILIKE '%director%')
                        OR (fa.attribute ILIKE '%board%' AND fb.attribute ILIKE '%board%')
                        OR (fa.attribute ILIKE '%equity%' AND fb.attribute ILIKE '%equity%')
                        OR (fa.attribute ILIKE '%asset%' AND fb.attribute ILIKE '%asset%')
                        OR (fa.attribute ILIKE '%liabilit%' AND fb.attribute ILIKE '%liabilit%')
                        OR (fa.attribute ILIKE '%capital%' AND fb.attribute ILIKE '%capital%')
                    )
                )
                SELECT * FROM paired_facts
                WHERE rn <= 3
                LIMIT 60
            """
            candidates = await conn.fetch(query)
            print(f"Found {len(candidates)} high-signal candidate pairs to reconcile.", flush=True)

        tasks = []
        for c in candidates:
            fact_a = {
                "id": str(c["a_id"]), "entity_name": c["a_entity"], "attribute": c["a_attr"],
                "value": c["a_val"], "unit": c["a_unit"], "fiscal_year": c["a_fy"],
                "verbatim_quote": c["a_q"], "page_number": c["a_p"], "document_id": str(c["a_doc_id"])
            }
            fact_b = {
                "id": str(c["b_id"]), "entity_name": c["b_entity"], "attribute": c["b_attr"],
                "value": c["b_val"], "unit": c["b_unit"], "fiscal_year": c["b_fy"],
                "verbatim_quote": c["b_q"], "page_number": c["b_p"], "document_id": str(c["b_doc_id"])
            }
            tasks.append(reconcile_and_save(fact_a, fact_b, pool, client))

        print(f"Running {len(tasks)} reconciliations concurrently...", flush=True)
        results = await asyncio.gather(*tasks)
        
        # Summary counts
        from collections import Counter
        counts = Counter(results)
        print("\nReconciliation Completed! Results distribution:", flush=True)
        for rel, count in counts.items():
            print(f"  {rel.upper()}: {count}", flush=True)

    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
