"""Embedding Service — converts text chunks to dense vectors.

Uses `intfloat/multilingual-e5-large` (768-dim) which handles
Kannada and English text in the same embedding space.
"""

import logging
from functools import lru_cache
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_model():
    """Load the embedding model once and cache it."""
    from sentence_transformers import SentenceTransformer
    s = get_settings()
    logger.info(f"Loading embedding model: {s.embedding_model}")
    model = SentenceTransformer(s.embedding_model)
    logger.info("Embedding model loaded.")
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts.
    multilingual-e5 requires a prefix: 'query: ' or 'passage: '
    We always use 'passage: ' for storage.
    """
    if not texts:
        return []
    model = _get_model()
    prefixed = [f"passage: {t}" for t in texts]
    vectors = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> list[float]:
    """Embed a single query string.
    Use 'query: ' prefix for retrieval.
    """
    model = _get_model()
    vec = model.encode(f"query: {query}", normalize_embeddings=True)
    return vec.tolist()


def chunk_text(text: str, chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> list[str]:
    """Split text into overlapping chunks while respecting sentence boundaries."""
    s = get_settings()
    chunk_size = chunk_size or s.chunk_size
    overlap = overlap or s.chunk_overlap

    if not text or not text.strip():
        return []

    # Split on sentence-ish boundaries first
    import re
    sentences = re.split(r'(?<=[.।\n])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) + 1 <= chunk_size:
            current = (current + " " + sent).strip()
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap from end of previous
            if overlap > 0 and current:
                overlap_text = current[-overlap:]
                current = (overlap_text + " " + sent).strip()
            else:
                current = sent

    if current:
        chunks.append(current)

    return chunks
