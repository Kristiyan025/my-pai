"""
Text Summarizer utility for SDSA Agent.
Summarizes text chunks using an LLM via Ollama.
"""

import os
from typing import Optional
import httpx

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "llama3.2:3b")


async def summarize_text(text: str, max_length: int = 100) -> str:
    """
    Summarize a text chunk using an LLM.
    
    Args:
        text: Input text to summarize
        max_length: Approximate maximum length of summary in words
        
    Returns:
        Summarized text string
    """
    if not text or len(text.strip()) < 50:
        return text.strip()
    
    prompt = f"""Summarize the following text in about {max_length} words or less. 
Keep the key information and main points. Be concise.

Text to summarize:
{text}

Summary:"""
    
    request_data = {
        "model": SUMMARIZER_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": max_length * 2  # Rough token estimate
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
    except Exception as e:
        print(f"Text summarization failed: {e}")
        # Return first part of text as fallback
        words = text.split()
        return " ".join(words[:max_length]) + ("..." if len(words) > max_length else "")


def summarize_text_sync(text: str, max_length: int = 100) -> str:
    """
    Synchronous version of summarize_text.
    """
    if not text or len(text.strip()) < 50:
        return text.strip()
    
    prompt = f"""Summarize the following text in about {max_length} words or less. 
Keep the key information and main points. Be concise.

Text to summarize:
{text}

Summary:"""
    
    request_data = {
        "model": SUMMARIZER_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": max_length * 2
        }
    }
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
    except Exception as e:
        print(f"Text summarization failed: {e}")
        words = text.split()
        return " ".join(words[:max_length]) + ("..." if len(words) > max_length else "")


async def extract_keywords(text: str, max_keywords: int = 10) -> list:
    """
    Extract keywords from text for better search indexing.
    """
    prompt = f"""Extract the {max_keywords} most important keywords or key phrases from the following text.
Return only the keywords, one per line, no numbering or bullets.

Text:
{text}

Keywords:"""
    
    request_data = {
        "model": SUMMARIZER_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 100
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            keywords_text = result.get("response", "")
            
            # Parse keywords
            keywords = [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
            return keywords[:max_keywords]
    except Exception as e:
        print(f"Keyword extraction failed: {e}")
        return []
