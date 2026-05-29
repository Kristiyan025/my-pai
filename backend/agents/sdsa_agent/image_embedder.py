"""
Image Embedder utility for SDSA Agent.
Generates vision embeddings for images using CLIP.
"""

import os
from typing import List, Optional
from io import BytesIO
import base64

# Lazy loading of model to conserve GPU memory
_model = None
_processor = None
_model_name = os.getenv("IMAGE_EMBEDDING_MODEL", "openai/clip-vit-base-patch32")


def get_model():
    """Get or load the CLIP model (lazy loading)."""
    global _model, _processor
    if _model is None:
        from transformers import CLIPModel, CLIPProcessor
        import torch
        
        _processor = CLIPProcessor.from_pretrained(_model_name)
        _model = CLIPModel.from_pretrained(_model_name)
        
        # Move to GPU if available
        if torch.cuda.is_available():
            _model = _model.cuda()
    
    return _model, _processor


def unload_model():
    """Unload model to free GPU memory."""
    global _model, _processor
    if _model is not None:
        del _model
        del _processor
        _model = None
        _processor = None
        # Force garbage collection
        import gc
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except ImportError:
            pass


def embed_image(image_data: bytes) -> List[float]:
    """
    Generate a vision embedding for the given image.
    
    Args:
        image_data: Raw image bytes (PNG, JPEG, etc.)
        
    Returns:
        List of floats representing the embedding vector
    """
    from PIL import Image
    import torch
    
    model, processor = get_model()
    
    # Load image from bytes
    image = Image.open(BytesIO(image_data)).convert("RGB")
    
    # Process image
    inputs = processor(images=image, return_tensors="pt")
    
    # Move to GPU if available
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}
    
    # Generate embedding
    with torch.no_grad():
        image_features = model.get_image_features(**inputs)
    
    # Normalize
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    
    return image_features.cpu().numpy().flatten().tolist()


def embed_image_base64(image_base64: str) -> List[float]:
    """
    Generate embedding from base64-encoded image.
    
    Args:
        image_base64: Base64-encoded image string
        
    Returns:
        Embedding vector
    """
    image_data = base64.b64decode(image_base64)
    return embed_image(image_data)


def embed_images(images_data: List[bytes]) -> List[List[float]]:
    """
    Generate embeddings for multiple images (batch processing).
    
    Args:
        images_data: List of raw image bytes
        
    Returns:
        List of embedding vectors
    """
    if not images_data:
        return []
    
    from PIL import Image
    import torch
    
    model, processor = get_model()
    
    # Load all images
    images = [Image.open(BytesIO(data)).convert("RGB") for data in images_data]
    
    # Process images
    inputs = processor(images=images, return_tensors="pt", padding=True)
    
    # Move to GPU if available
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}
    
    # Generate embeddings
    with torch.no_grad():
        image_features = model.get_image_features(**inputs)
    
    # Normalize
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    
    return image_features.cpu().numpy().tolist()
