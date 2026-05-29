"""
Text Embedder utility for SDSA Agent.
Generates text vector embeddings using sentence-transformers.
"""

import os
from typing import List, Optional
import numpy as np

# Lazy loading of model to conserve GPU memory
_model = None
_model_name = os.getenv("TEXT_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def get_model():
    """Get or load the embedding model (lazy loading)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_model_name)
    return _model


def unload_model():
    """Unload model to free GPU memory."""
    global _model
    if _model is not None:
        del _model
        _model = None
        # Force garbage collection
        import gc
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except ImportError:
            pass


def embed_text(text: str) -> List[float]:
    """
    Generate a text embedding for the given text.
    
    Args:
        text: Input text to embed
        
    Returns:
        List of floats representing the embedding vector
    """
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts (batch processing).
    
    Args:
        texts: List of input texts
        
    Returns:
        List of embedding vectors
    """
    if not texts:
        return []
    
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


def get_embedding_dimension() -> int:
    """Get the dimension of the embedding vectors."""
    model = get_model()
    return model.get_sentence_embedding_dimension()
