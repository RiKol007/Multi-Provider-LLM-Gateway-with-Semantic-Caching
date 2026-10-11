from sentence_transformers import SentenceTransformer
import numpy as np

# Loads a small, fast, free local model — downloads once, then cached on disk
model = SentenceTransformer("all-MiniLM-L6-v2")


def get_embedding(text: str) -> list[float]:
    """Converts text into a vector (list of numbers) representing its meaning."""
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Measures how similar two vectors are. 1.0 = identical meaning, 0.0 = unrelated."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))