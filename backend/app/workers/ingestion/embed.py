"""Embedding worker: sentence-transformers → Qdrant upsert."""
import uuid
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SourceChunk, Source
from app.models.source import SourceStatus


def embed_source(source_id: str):
    from sentence_transformers import SentenceTransformer
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct

    engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
    with Session(engine) as db:
        source = db.get(Source, uuid.UUID(source_id))
        if not source:
            return

        chunks = db.execute(
            select(SourceChunk).where(SourceChunk.source_id == source.id)
        ).scalars().all()

        if not chunks:
            logger.warning(f"No chunks for source {source_id}")
            return

        model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
        texts = [c.text for c in chunks]
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)

        client = QdrantClient(url=settings.qdrant_url)
        _ensure_collection(client)

        points = []
        for chunk, vec in zip(chunks, embeddings):
            point_id = str(chunk.id)
            points.append(PointStruct(
                id=point_id,
                vector=vec.tolist(),
                payload={
                    "course_id": str(source.course_id),
                    "source_id": str(source.id),
                    "source_type": source.type.value,
                    "chunk_index": chunk.chunk_index,
                    "text_preview": chunk.text[:200],
                    "location": chunk.location,
                }
            ))
            chunk.qdrant_point_id = point_id
            chunk.embedded_at = datetime.now(timezone.utc)

        client.upsert(collection_name=settings.qdrant_collection, points=points)
        source.status = SourceStatus.indexed
        source.indexed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Source {source_id} indexed: {len(points)} vectors")


def _ensure_collection(client):
    from qdrant_client.models import Distance, VectorParams
    collections = client.get_collections().collections
    names = [c.name for c in collections]
    if settings.qdrant_collection not in names:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
        )
