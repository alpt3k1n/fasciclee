import uuid
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, ScoredPoint
)
from app.config import settings

_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url)
    return _client


async def ensure_collection():
    client = get_qdrant()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if settings.qdrant_collection not in names:
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
        )


async def upsert_chunk(
    chunk_id: str,
    vector: list[float],
    payload: dict,
):
    client = get_qdrant()
    await client.upsert(
        collection_name=settings.qdrant_collection,
        points=[PointStruct(id=chunk_id, vector=vector, payload=payload)],
    )


async def search_chunks(
    query_vector: list[float],
    course_id: str,
    limit: int = 20,
) -> list[ScoredPoint]:
    client = get_qdrant()
    results = await client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        query_filter=Filter(
            must=[FieldCondition(key="course_id", match=MatchValue(value=course_id))]
        ),
        limit=limit,
    )
    return results
