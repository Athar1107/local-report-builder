"""
embedder.py
-----------
Local text embeddings via sentence-transformers.
No API. Model cached at ~/.cache/huggingface/hub/ after first download.
"""

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from .config import EMBED_MODEL


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    """Load once, cache for the process lifetime."""
    return SentenceTransformer(EMBED_MODEL)


def embed(texts: list[str]) -> np.ndarray:
    """
    Embed a list of strings → L2-normalised float32 vectors.
    Shape: (len(texts), embedding_dim).
    """
    if not texts:
        dim = _model().get_sentence_embedding_dimension()
        return np.empty((0, dim), dtype=np.float32)
    vecs = _model().encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vecs.astype(np.float32)


def embed_one(text: str) -> np.ndarray:
    """Embed a single string → shape (1, dim)."""
    return embed([text])
