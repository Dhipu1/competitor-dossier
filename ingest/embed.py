"""Turns text into embeddings — vectors that represent meaning.

Two pieces of text with similar meaning produce vectors pointing in a similar
direction, even with no words in common. That's what lets a search for
"what do they charge" find a section titled "Pricing".

We run the model locally via fastembed (ONNX runtime, no GPU or API key
needed). Swapping to a hosted provider later means changing only this file —
everything downstream just consumes vectors.
"""

from functools import lru_cache
from typing import List

import numpy as np

# 384 numbers per vector. Small, fast, and strong on retrieval benchmarks for
# its size — a bigger model would cost more time/memory for marginal gain here.
MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _model():
    """Loads the model once and reuses it — loading takes seconds, embedding is fast."""
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=MODEL_NAME)


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embeds a list of texts, returning one unit-length row per text."""
    vectors = np.array(list(_model().embed(texts)), dtype=np.float32)
    return _normalize(vectors)


def embed_query(text: str) -> np.ndarray:
    """Embeds a single search query, returning one unit-length vector."""
    return embed_texts([text])[0]


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """Scales every vector to length 1.

    Once all vectors are length 1, comparing two of them is just a dot
    product, and the result falls in a predictable -1..1 range where 1 means
    "same direction / same meaning".
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1  # a zero vector has no direction; leave it be
    return vectors / norms


def to_blob(vector: np.ndarray) -> bytes:
    """Packs a vector into raw bytes for storage in SQLite."""
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    """Unpacks a stored vector."""
    return np.frombuffer(blob, dtype=np.float32)
