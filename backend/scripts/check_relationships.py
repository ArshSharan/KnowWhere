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
    pool = await asyncpg.create_pool(_asyncpg_url(settings.database_url), ssl='require', statement_cache_size=0)
    try:
        async with pool.acquire() as conn:
            counts = await conn.fetch('SELECT relationship, count(*) FROM fact_relationships GROUP BY relationship')
            print('Counts:', [dict(c) for c in counts])
            
            for rel in ['corroborates', 'contradicts', 'reconciled_by_context']:
                print(f'\n=== {rel.upper()} ===')
                rows = await conn.fetch('''
                    SELECT fr.relationship, fr.basis, fr.confidence, fr.explanation,
                           fa.attribute AS fa_attr, fa.value AS fa_val, fa.unit AS fa_unit, fa.fiscal_year AS fa_fy, fa.page_number AS fa_p, fa.verbatim_quote AS fa_q,
                           da.title AS da_title,
                           fb.attribute AS fb_attr, fb.value AS fb_val, fb.unit AS fb_unit, fb.fiscal_year AS fb_fy, fb.page_number AS fb_p, fb.verbatim_quote AS fb_q,
                           db.title AS db_title
                    FROM fact_relationships fr
                    JOIN facts fa ON fa.id = fr.fact_a_id
                    JOIN facts fb ON fb.id = fr.fact_b_id
                    JOIN documents da ON da.id = fa.document_id
                    JOIN documents db ON db.id = fb.document_id
                    WHERE fr.relationship = $1
                    ORDER BY fr.confidence DESC
                    LIMIT 4
                ''', rel)
                for r in rows:
                    print(f"Basis: {r['basis']} | Conf: {r['confidence']}")
                    print(f"Doc A ({r['da_title']}, p.{r['fa_p']}): {r['fa_attr']} = {r['fa_val']} {r['fa_unit']} ({r['fa_fy']})")
                    print(f"  Quote A: {r['fa_q']}")
                    print(f"Doc B ({r['db_title']}, p.{r['fb_p']}): {r['fb_attr']} = {r['fb_val']} {r['fb_unit']} ({r['fb_fy']})")
                    print(f"  Quote B: {r['fb_q']}")
                    print(f"Explanation: {r['explanation']}")
                    print('---')
    finally:
        await pool.close()

if __name__ == '__main__':
    asyncio.run(main())
