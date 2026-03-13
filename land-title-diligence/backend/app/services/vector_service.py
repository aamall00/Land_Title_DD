"""Vector Service — stores and retrieves embeddings via Supabase pgvector."""

import logging
from typing import Optional
from uuid import UUID

from app.database import get_supabase
from app.services.embedding_service import embed_texts, embed_query, chunk_text

logger = logging.getLogger(__name__)


def store_document_embeddings(
    document_id: str,
    property_id: str,
    ocr_text: str,
    doc_type: str,
    extra_metadata: dict | None = None,
) -> int:
    """Chunk OCR text, embed, and persist to the embeddings table.
    Returns the number of chunks stored.
    """
    chunks = chunk_text(ocr_text)
    if not chunks:
        logger.warning(f"No chunks produced for document {document_id}")
        return 0

    vectors = embed_texts(chunks)
    db = get_supabase()

    rows = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        metadata = {
            "doc_type": doc_type,
            "chunk_index": i,
            **(extra_metadata or {}),
        }
        rows.append({
            "document_id": str(document_id),
            "property_id": str(property_id),
            "chunk_index": i,
            "chunk_text": chunk,
            "embedding": vec,
            "metadata": metadata,
        })

    # Insert in batches of 100
    batch_size = 100
    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start : batch_start + batch_size]
        db.table("embeddings").insert(batch).execute()

    logger.info(f"Stored {len(rows)} chunks for document {document_id}")
    return len(rows)


def similarity_search(
    query: str,
    property_id: str,
    top_k: int = 6,
    doc_types: list[str] | None = None,
) -> list[dict]:
    """Hybrid search: vector similarity + optional doc_type filter.
    Returns list of {document_id, chunk_text, metadata, similarity}.
    """
    query_vec = embed_query(query)
    db = get_supabase()

    result = db.rpc(
        "match_embeddings",
        {
            "query_embedding": query_vec,
            "target_property_id": str(property_id),
            "match_count": top_k,
            "doc_types": doc_types,
        },
    ).execute()

    return result.data or []


def delete_document_embeddings(document_id: str) -> None:
    """Remove all embedding rows for a document."""
    db = get_supabase()
    db.table("embeddings").delete().eq("document_id", str(document_id)).execute()
    logger.info(f"Deleted embeddings for document {document_id}")


def delete_property_embeddings(property_id: str) -> None:
    """Remove all embeddings for an entire property."""
    db = get_supabase()
    db.table("embeddings").delete().eq("property_id", str(property_id)).execute()
    logger.info(f"Deleted all embeddings for property {property_id}")
