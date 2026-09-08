import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio, asyncpg
from app.config import get_settings
from app.db.connection import _asyncpg_url
from app.services.reconciler import reconcile_pair
from openai import AsyncOpenAI

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    pool = await asyncpg.create_pool(_asyncpg_url(settings.database_url), ssl="require", statement_cache_size=0)
    
    try:
        async with pool.acquire() as conn:
            # 1. Merge entity IDs for Delhivery aliases
            canonical_id = await conn.fetchval("""
                SELECT id FROM entities WHERE canonical_name = 'Delhivery Limited' LIMIT 1
            """)
            print(f"Canonical Delhivery Limited ID: {canonical_id}")
            
            # Find duplicate entities: 'Delhivery', 'Company', 'the Company', 'Our Company'
            alias_entities = await conn.fetch("""
                SELECT id, canonical_name FROM entities 
                WHERE canonical_name IN ('Delhivery', 'Company', 'the Company', 'Our Company')
            """)
            print("Entities to merge into Delhivery Limited:")
            alias_ids = []
            for ae in alias_entities:
                print(f"  {ae['canonical_name']} ({ae['id']})")
                alias_ids.append(ae['id'])
                
            if alias_ids and canonical_id:
                # Update facts pointing to alias entities
                updated_facts = await conn.execute("""
                    UPDATE facts SET entity_id = $1 WHERE entity_id = ANY($2)
                """, canonical_id, alias_ids)
                print(f"Updated facts to canonical entity: {updated_facts}")
                
                # Update aliases array on canonical entity
                await conn.execute("""
                    UPDATE entities 
                    SET aliases = ARRAY['Delhivery', 'Company', 'the Company', 'Our Company', 'Delhivery Ltd.']
                    WHERE id = $1
                """, canonical_id)
                
                # Delete merged entities from entities table
                await conn.execute("""
                    DELETE FROM entities WHERE id = ANY($1)
                """, alias_ids)
                print("Deleted alias entity records.")

            # 2. Let's see how many facts now belong to Delhivery Limited across documents
            doc_facts = await conn.fetch("""
                SELECT d.title, count(*) as count
                FROM facts f
                JOIN documents d ON d.id = f.document_id
                WHERE f.entity_id = $1
                GROUP BY d.title
            """, canonical_id)
            print("\nFacts for Delhivery Limited by document:")
            for df in doc_facts:
                print(f"  {df['title']}: {df['count']} facts")

    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
