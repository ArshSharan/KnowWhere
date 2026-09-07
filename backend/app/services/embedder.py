"""
Embedding service.

Wraps OpenAI text-embedding-3-small for all embedding needs:
  - Entity canonicalization (entity name strings)
  - Fact embeddings (entity + attribute combined for similarity search)
  - Fact-type registry (fact_type label strings)

Uses batched API calls to minimise latency and cost.
Dimension: 1536 (text-embedding-3-small default).
Cost: ~$0.02 / MTok — negligible at this project's scale.
"""

from __future__ import annotations
import logging
from typing import Optional

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
async def embed_texts(
    texts: list[str],
    client: AsyncOpenAI,
) -> list[list[float]]:
    """
    Embed a list of strings and return a list of float vectors.
    Batches up to 2048 inputs per API call (OpenAI limit).
    """
    settings = get_settings()
    if not texts:
        return []

    # OpenAI embedding API accepts up to 2048 inputs per call
    all_embeddings: list[list[float]] = []
    batch_size = 500  # conservative batch to stay well within limits

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
            dimensions=settings.embedding_dimensions,
        )
        batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


async def embed_one(text: str, client: AsyncOpenAI) -> list[float]:
    """Convenience wrapper for a single string."""
    results = await embed_texts([text], client)
    return results[0]


def fact_embedding_text(entity: str, attribute: str) -> str:
    """
    Canonical text representation used when embedding a fact for similarity search.
    Combining entity + attribute means kNN finds facts about the *same thing*,
    not just facts with semantically similar values.
    """
    return f"{entity} | {attribute}"
