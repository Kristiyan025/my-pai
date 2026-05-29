"""
Image Text Extractor utility for SDSA Agent.
Extracts text from images using Tesseract OCR.
"""

import os
from io import BytesIO
from typing import Optional
import pytesseract
from PIL import Image


# Configure Tesseract path if needed (for Windows)
TESSERACT_CMD = os.getenv("TESSERACT_CMD", None)
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def extract_text(image_data: bytes, language: str = "eng") -> str:
    """
    Extract text from an image using OCR.
    
    Args:
        image_data: Raw image bytes
        language: Tesseract language code (default: 'eng')
        
    Returns:
        Extracted text string
    """
    try:
        # Load image
        image = Image.open(BytesIO(image_data))
        
        # Convert to RGB if needed (Tesseract works best with RGB)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # Extract text using Tesseract
        text = pytesseract.image_to_string(image, lang=language)
        
        # Clean up the text
        text = text.strip()
        
        return text
    except Exception as e:
        print(f"OCR extraction failed: {e}")
        return ""


def extract_text_with_confidence(image_data: bytes, language: str = "eng") -> dict:
    """
    Extract text from an image with confidence scores.
    
    Args:
        image_data: Raw image bytes
        language: Tesseract language code
        
    Returns:
        Dict with 'text' and 'confidence' keys
    """
    try:
        image = Image.open(BytesIO(image_data))
        
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # Get detailed data
        data = pytesseract.image_to_data(image, lang=language, output_type=pytesseract.Output.DICT)
        
        # Calculate average confidence
        confidences = [int(c) for c in data['conf'] if int(c) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Get text
        text = pytesseract.image_to_string(image, lang=language).strip()
        
        return {
            'text': text,
            'confidence': avg_confidence,
            'word_count': len(data['text'])
        }
    except Exception as e:
        return {'text': '', 'confidence': 0, 'word_count': 0, 'error': str(e)}


def is_tesseract_available() -> bool:
    """Check if Tesseract is installed and available."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
