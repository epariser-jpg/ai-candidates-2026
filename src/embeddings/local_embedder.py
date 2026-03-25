"""Local embedding generation using sentence-transformers."""

import numpy as np

from src.config import EMBEDDING_MODEL, EMBEDDING_DIM

_model = None


def get_model():
    """Lazy-load the embedding model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Returns list of float vectors (384-dim for all-MiniLM-L6-v2).
    """
    model = get_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Generate an embedding for a search query."""
    model = get_model()
    embedding = model.encode([query], normalize_embeddings=True)
    return embedding[0].tolist()
