"""
Image Captioner utility for SDSA Agent.
Generates textual descriptions of images using LLaVA via Ollama.
"""

import os
import base64
from typing import Optional
import httpx

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
IMAGE_CAPTION_MODEL = os.getenv("IMAGE_CAPTION_MODEL", "llava:7b")


async def caption_image(image_data: bytes, prompt: str = "Describe this image in detail.") -> str:
    """
    Generate a caption/description for an image using LLaVA model.
    
    Args:
        image_data: Raw image bytes
        prompt: Optional custom prompt for the model
        
    Returns:
        Generated caption string
    """
    # Convert image to base64
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    # Prepare request for Ollama
    request_data = {
        "model": IMAGE_CAPTION_MODEL,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
    except Exception as e:
        print(f"Image captioning failed: {e}")
        return ""


def caption_image_sync(image_data: bytes, prompt: str = "Describe this image in detail.") -> str:
    """
    Synchronous version of caption_image.
    """
    import httpx
    
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    request_data = {
        "model": IMAGE_CAPTION_MODEL,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False
    }
    
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
    except Exception as e:
        print(f"Image captioning failed: {e}")
        return ""


async def describe_image_for_search(image_data: bytes) -> str:
    """
    Generate a search-optimized description of an image.
    """
    prompt = """Describe this image concisely for search indexing. Include:
    - Main subjects/objects
    - Actions or scenes
    - Colors and visual style
    - Any text visible in the image
    Keep the description factual and keyword-rich."""
    
    return await caption_image(image_data, prompt)
