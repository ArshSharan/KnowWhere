import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio, asyncpg
from app.config import get_settings
from app.db.connection import _asyncpg_url

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    settings = get_settings()
    pool = await asyncpg.create_pool(_asyncpg_url(settings.database_url), ssl="require", statement_cache_size=0)
    try:
        async with pool.acquire() as conn:
            for cat in ['corroborates', 'contradicts', 'reconciled_by_context']:
                print(f"\n{'='*25} {cat.upper()} {'='*25}")
                rows = await conn.fetch("""
                    SELECT fr.basis, fr.confidence, fr.explanation,
                           fa.attribute as a_attr, fa.value as a_val, fa.unit as a_unit, fa.fiscal_year as a_fy,
                           fa.page_number as a_p, fa.verbatim_quote as a_q, da.title as a_doc,
                           fb.attribute as b_attr, fb.value as b_val, fb.unit as b_unit, fb.fiscal_year as b_fy,
                           fb.page_number as b_p, fb.verbatim_quote as b_q, db.title as b_doc
                    FROM fact_relationships fr
                    JOIN facts fa ON fa.id = fr.fact_a_id
                    JOIN facts fb ON fb.id = fr.fact_b_id
                    JOIN documents da ON da.id = fa.document_id
                    JOIN documents db ON db.id = fb.document_id
                    WHERE fr.relationship = $1
                    ORDER BY fr.confidence DESC
                    LIMIT 2
                """, cat)
                for r in rows:
                    print(f"\n[Basis: {r['basis']} | Conf: {r['confidence']}]")
                    print(f"  Fact A [{r['a_doc'][:30]} p.{r['a_p']}]: {r['a_attr']} = {r['a_val']} {r['a_unit']} (FY: {r['a_fy']})")
                    print(f"    Quote A: \"{r['a_q'][:100]}\"")
                    print(f"  Fact B [{r['b_doc'][:30]} p.{r['b_p']}]: {r['b_attr']} = {r['b_val']} {r['b_unit']} (FY: {r['b_fy']})")
                    print(f"    Quote B: \"{r['b_q'][:100]}\"")
                    print(f"  Explanation: {r['explanation']}")
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
