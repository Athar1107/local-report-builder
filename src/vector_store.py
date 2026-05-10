"""
vector_store.py
---------------
Unified FAISS vector store holding both caption chunks and report section
chunks from previous-year reports.

Each entry has a 'kind' field: "caption" or "section".
This allows the caption generator and report generator to retrieve
from the same store but filter by what they need.
"""

import pickle
from pathlib import Path

import faiss
import numpy as np

from .embedder import embed, embed_one
from .config   import VECTOR_STORE_PATH


class KnowledgeStore:
    """
    FAISS IndexFlatIP (cosine similarity on L2-normalised vectors).
    Stores both captions and report sections from previous-year reports.
    """

    def __init__(self, store_path: str | Path = VECTOR_STORE_PATH):
        self.store_path: Path       = Path(store_path)
        self.texts:      list[str]  = []    # the text that was embedded
        self.metadata:   list[dict] = []    # kind, source, heading, content, etc.
        self._index:     faiss.Index | None = None

    # ── Add ────────────────────────────────────────────────────────────────────

    def add(self, entries: list[dict]) -> int:
        """
        Embed and index a list of entries.

        Each entry must have:
          - "text"   : str  — the string to embed (used for retrieval)
          - "kind"   : str  — "caption" or "section"
          - "source" : str  — source filename

        Optional fields (stored in metadata, not embedded):
          - "heading", "content"  (for section entries)

        Returns number of entries added.
        """
        if not entries:
            return 0

        texts = [e["text"] for e in entries]
        vecs  = embed(texts)

        if self._index is None:
            self._index = faiss.IndexFlatIP(vecs.shape[1])

        self._index.add(vecs)
        self.texts.extend(texts)
        self.metadata.extend(entries)
        return len(entries)

    # ── Retrieve ───────────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 5,
                 kind: str | None = None) -> list[dict]:
        """
        Find the most similar entries to a query string.

        Args:
            query  : Free-text query.
            top_k  : Max results to return.
            kind   : If set, filters results to only "caption" or "section".

        Returns:
            List of dicts with keys: text, kind, source, score, rank,
            plus any extra metadata (heading, content) for section entries.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        # Over-fetch when filtering by kind so we have enough after filtering
        fetch_k = top_k * 4 if kind else top_k
        fetch_k = min(fetch_k, self._index.ntotal)

        q = embed_one(query)
        scores, indices = self._index.search(q, fetch_k)

        results = []
        rank    = 1
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            entry = self.metadata[idx]
            if kind and entry.get("kind") != kind:
                continue
            results.append({
                **entry,
                "score": float(score),
                "rank":  rank,
            })
            rank += 1
            if len(results) >= top_k:
                break

        return results

    # ── Persistence ────────────────────────────────────────────────────────────

    def save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "texts":       self.texts,
            "metadata":    self.metadata,
            "index_bytes": faiss.serialize_index(self._index) if self._index else None,
        }
        with open(self.store_path, "wb") as f:
            pickle.dump(payload, f)

    def load(self) -> bool:
        if not self.store_path.exists():
            return False
        with open(self.store_path, "rb") as f:
            payload = pickle.load(f)
        self.texts    = payload["texts"]
        self.metadata = payload["metadata"]
        if payload["index_bytes"] is not None:
            self._index = faiss.deserialize_index(payload["index_bytes"])
        return True

    # ── Stats ──────────────────────────────────────────────────────────────────

    def count(self, kind: str | None = None) -> int:
        if kind:
            return sum(1 for m in self.metadata if m.get("kind") == kind)
        return len(self.texts)

    def sources(self) -> list[str]:
        seen = []
        for m in self.metadata:
            s = m.get("source", "unknown")
            if s not in seen:
                seen.append(s)
        return seen

    def __len__(self)  -> int:  return len(self.texts)
    def __repr__(self) -> str:
        return (f"KnowledgeStore("
                f"captions={self.count('caption')}, "
                f"sections={self.count('section')}, "
                f"sources={self.sources()})")
