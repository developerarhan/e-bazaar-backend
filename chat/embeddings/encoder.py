"""
Wraps the sentence-transformers embedding model.
 
Singleton pattern: model is loaded ONCE when the Django
process starts, then reused for every embedding call.
Loading the model takes ~2 seconds and ~80MB RAM —
we don't want that cost on every request.
 
Model: all-MiniLM-L6-v2
  - Outputs 384-dimensional vectors
  - Fast, good quality for semantic search
  - Widely used in production RAG systems
  - ~80MB download, cached in ~/.cache/huggingface/
"""
 
import logging
import numpy as np
 
logger = logging.getLogger('chat')

# Module-level singleton — loaded once, reused forever
_model = None

def get_model():
    """
    Returns the embedding model, loading it if not yet loaded.
    Thread-safe in production (gunicorn workers each get their
    own copy since they're separate processes).
    """
    global _model

    if _model is None:
        logger.info("Loading sentence-transformer embedding model...")
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embedding model loaded successfully")
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
            raise
 
    return _model


def embed_text(text: str) -> list[float]:
    """
     Embeds a single string into a 384-dim vector.
 
    Args:
        text: str — the text to embed
 
    Returns:
        list[float] — 384 floats representing the text
    """
    model = get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embeds multiple strings in one batch.
    Much faster than calling embed_text() in a loop.
 
    Args:
        texts: list of strings
 
    Returns:
        list of 384-dim float lists
    """
    if not texts:
        return []

    model = get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,   # process 32 at a time
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def vector_to_pg_string(vector: list[float]) -> str:
    """
    Converts a Python float list to pgvector's string format.
 
    pgvector stores vectors as '[0.1, 0.2, ...]' strings.
    This is the format needed for raw SQL insertion.
    """
    return '[' + ','.join(f'{x:.8f}' for x in vector) + ']'


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Computes cosine similarity between two vectors.
    Used in tests to verify embeddings are working.
    Not used in production (pgvector handles this in SQL).
    """
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
