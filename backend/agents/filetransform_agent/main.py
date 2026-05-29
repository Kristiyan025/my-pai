"""
File Transform Agent - Handles file format conversions and transformations.

Supports:
- Document conversions (md->pdf, docx->pdf, etc.)
- Image operations (resize, format conversion)
- Text extraction from various formats
"""

import os
import sys
import tempfile
import base64
from typing import Optional, List, Dict, Any
from io import BytesIO

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

app = FastAPI(
    title="File Transform Agent",
    description="File format conversion and transformation service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_URL = os.getenv("WORKSPACE_URL", "http://workspace-agent:8010")
USER_ID = 1


# ============== Request/Response Models ==============

class TransformRequest(BaseModel):
    input_base64: str
    input_format: str
    output_format: str
    options: Optional[Dict[str, Any]] = None


class TransformResponse(BaseModel):
    output_base64: str
    output_format: str
    original_size: int
    transformed_size: int


class ImageResizeRequest(BaseModel):
    input_base64: str
    width: Optional[int] = None
    height: Optional[int] = None
    maintain_aspect: bool = True
    output_format: Optional[str] = None


class PathConvertRequest(BaseModel):
    source_path: str
    output_path: Optional[str] = None
    target_format: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class TextExtractionResult(BaseModel):
    text: str
    format_detected: str
    pages: Optional[int] = None


# ============== Supported Formats ==============

SUPPORTED_CONVERSIONS = {
    # Markdown
    ("md", "html"): "markdown_to_html",
    ("md", "pdf"): "markdown_to_pdf",
    
    # HTML
    ("html", "pdf"): "html_to_pdf",
    ("html", "md"): "html_to_markdown",
    
    # Images
    ("png", "jpg"): "image_convert",
    ("jpg", "png"): "image_convert",
    ("png", "webp"): "image_convert",
    ("jpg", "webp"): "image_convert",
    ("webp", "png"): "image_convert",
    ("webp", "jpg"): "image_convert",
    ("bmp", "png"): "image_convert",
    ("gif", "png"): "image_convert",
    
    # PDF
    ("pdf", "txt"): "pdf_to_text",
    ("pdf", "images"): "pdf_to_images",
    
    # Text
    ("txt", "pdf"): "text_to_pdf",
}


# ============== Conversion Functions ==============

def markdown_to_html(content: bytes, options: Dict = None) -> bytes:
    """Convert Markdown to HTML."""
    import markdown
    
    text = content.decode('utf-8')
    html = markdown.markdown(
        text,
        extensions=['tables', 'fenced_code', 'codehilite', 'toc']
    )
    
    # Wrap in basic HTML document
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
               max-width: 800px; margin: 40px auto; padding: 0 20px; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #f4f4f4; padding: 15px; overflow-x: auto; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    </style>
</head>
<body>
{html}
</body>
</html>"""
    
    return full_html.encode('utf-8')


def markdown_to_pdf(content: bytes, options: Dict = None) -> bytes:
    """Convert Markdown to PDF."""
    # First convert to HTML
    html_content = markdown_to_html(content, options)
    return html_to_pdf(html_content, options)


def html_to_pdf(content: bytes, options: Dict = None) -> bytes:
    """Convert HTML to PDF using weasyprint."""
    try:
        from weasyprint import HTML
        
        html_string = content.decode('utf-8')
        pdf_buffer = BytesIO()
        HTML(string=html_string).write_pdf(pdf_buffer)
        
        return pdf_buffer.getvalue()
        
    except ImportError:
        # Fallback to pdfkit if weasyprint not available
        try:
            import pdfkit
            
            html_string = content.decode('utf-8')
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                pdfkit.from_string(html_string, tmp_path)
                with open(tmp_path, 'rb') as f:
                    return f.read()
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="PDF conversion requires weasyprint or pdfkit"
            )


def html_to_markdown(content: bytes, options: Dict = None) -> bytes:
    """Convert HTML to Markdown."""
    try:
        import html2text
        
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        
        html_string = content.decode('utf-8')
        markdown = h.handle(html_string)
        
        return markdown.encode('utf-8')
        
    except ImportError:
        raise HTTPException(status_code=503, detail="html2text not installed")


def image_convert(content: bytes, output_format: str, options: Dict = None) -> bytes:
    """Convert between image formats."""
    from PIL import Image
    
    img = Image.open(BytesIO(content))
    
    # Handle format-specific requirements
    if output_format.lower() in ('jpg', 'jpeg'):
        output_format = 'JPEG'
        if img.mode == 'RGBA':
            img = img.convert('RGB')
    elif output_format.lower() == 'png':
        output_format = 'PNG'
    elif output_format.lower() == 'webp':
        output_format = 'WEBP'
    
    output = BytesIO()
    img.save(output, format=output_format)
    
    return output.getvalue()


def pdf_to_text(content: bytes, options: Dict = None) -> bytes:
    """Extract text from PDF."""
    try:
        import PyPDF2
        
        pdf_file = BytesIO(content)
        reader = PyPDF2.PdfReader(pdf_file)
        
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        
        full_text = "\n\n".join(text_parts)
        return full_text.encode('utf-8')
        
    except ImportError:
        raise HTTPException(status_code=503, detail="PyPDF2 not installed")


def pdf_to_images(content: bytes, options: Dict = None) -> List[bytes]:
    """Convert PDF pages to images."""
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(stream=content, filetype="pdf")
        images = []
        
        dpi = options.get('dpi', 150) if options else 150
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))
        
        return images
        
    except ImportError:
        raise HTTPException(status_code=503, detail="PyMuPDF not installed")


def text_to_pdf(content: bytes, options: Dict = None) -> bytes:
    """Convert plain text to PDF."""
    text = content.decode('utf-8')
    
    # Wrap in HTML with monospace font
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: monospace; white-space: pre-wrap; 
               max-width: 800px; margin: 40px auto; padding: 0 20px; }}
    </style>
</head>
<body>{text}</body>
</html>"""
    
    return html_to_pdf(html.encode('utf-8'), options)


# ============== API Endpoints ==============

@app.post("/convert", response_model=TransformResponse)
async def convert_file(request: TransformRequest):
    """
    Convert file from one format to another.
    """
    input_format = request.input_format.lower().lstrip('.')
    output_format = request.output_format.lower().lstrip('.')
    
    # Check if conversion is supported
    conversion_key = (input_format, output_format)
    if conversion_key not in SUPPORTED_CONVERSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Conversion from {input_format} to {output_format} not supported"
        )
    
    try:
        input_data = base64.b64decode(request.input_base64)
        
        # Get conversion function
        func_name = SUPPORTED_CONVERSIONS[conversion_key]
        
        if func_name == "image_convert":
            output_data = image_convert(input_data, output_format, request.options)
        elif func_name == "pdf_to_images":
            # Special case: returns list
            images = pdf_to_images(input_data, request.options)
            # Return first page or combine
            output_data = images[0] if images else b''
        else:
            func = globals()[func_name]
            output_data = func(input_data, request.options)
        
        return TransformResponse(
            output_base64=base64.b64encode(output_data).decode(),
            output_format=output_format,
            original_size=len(input_data),
            transformed_size=len(output_data)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@app.post("/convert/upload")
async def convert_uploaded_file(
    file: UploadFile = File(...),
    output_format: str = Form(...),
    options: Optional[str] = Form(None)
):
    """
    Convert an uploaded file to specified format.
    
    Returns the converted file as a download.
    """
    import json
    
    content = await file.read()
    
    # Detect input format from filename
    input_format = os.path.splitext(file.filename)[1].lstrip('.').lower()
    output_format = output_format.lower().lstrip('.')
    
    conversion_key = (input_format, output_format)
    if conversion_key not in SUPPORTED_CONVERSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Conversion from {input_format} to {output_format} not supported"
        )
    
    try:
        opts = json.loads(options) if options else None
        
        func_name = SUPPORTED_CONVERSIONS[conversion_key]
        
        if func_name == "image_convert":
            output_data = image_convert(content, output_format, opts)
        else:
            func = globals()[func_name]
            output_data = func(content, opts)
        
        # Determine MIME type
        mime_types = {
            'pdf': 'application/pdf',
            'html': 'text/html',
            'md': 'text/markdown',
            'txt': 'text/plain',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'webp': 'image/webp'
        }
        
        mime_type = mime_types.get(output_format, 'application/octet-stream')
        output_filename = f"{os.path.splitext(file.filename)[0]}.{output_format}"
        
        return StreamingResponse(
            BytesIO(output_data),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@app.post("/convert/path")
async def convert_file_by_path(request: PathConvertRequest):
    source_path = request.source_path
    source_ext = os.path.splitext(source_path)[1].lstrip('.').lower()
    
    if request.target_format:
        target_format = request.target_format.lower().lstrip('.')
    elif request.output_path:
        target_format = os.path.splitext(request.output_path)[1].lstrip('.').lower()
    else:
        raise HTTPException(status_code=400, detail="Must specify target_format or output_path with extension")
    
    if request.output_path:
        output_path = request.output_path
    else:
        output_path = os.path.splitext(source_path)[0] + '.' + target_format
    
    conversion_key = (source_ext, target_format)
    if conversion_key not in SUPPORTED_CONVERSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Conversion from {source_ext} to {target_format} not supported"
        )
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        read_response = await client.get(
            f"{WORKSPACE_URL}/file",
            params={"path": source_path}
        )
        
        if read_response.status_code != 200:
            raise HTTPException(
                status_code=404,
                detail=f"Source file not found: {source_path}"
            )
        
        input_data = read_response.content
        
        func_name = SUPPORTED_CONVERSIONS[conversion_key]
        
        if func_name == "image_convert":
            output_data = image_convert(input_data, target_format, request.options)
        elif func_name == "pdf_to_images":
            images = pdf_to_images(input_data, request.options)
            output_data = images[0] if images else b''
        else:
            func = globals()[func_name]
            output_data = func(input_data, request.options)
        
        output_b64 = base64.b64encode(output_data).decode()
        
        content_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'webp': 'image/webp',
            'gif': 'image/gif',
            'pdf': 'application/pdf'
        }
        content_type = content_types.get(target_format, 'application/octet-stream')
        
        save_response = await client.post(
            f"{WORKSPACE_URL}/save-image",
            json={
                "path": output_path,
                "image_base64": output_b64,
                "content_type": content_type
            }
        )
        
        if save_response.status_code not in (200, 201):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save converted file: {save_response.text}"
            )
        
        return {
            "success": True,
            "source_path": source_path,
            "output_path": output_path,
            "source_format": source_ext,
            "target_format": target_format,
            "original_size": len(input_data),
            "converted_size": len(output_data)
        }

# ============== Image Operations ==============

@app.post("/image/resize")
async def resize_image(request: ImageResizeRequest):
    """
    Resize an image.
    """
    from PIL import Image
    
    try:
        img_data = base64.b64decode(request.input_base64)
        img = Image.open(BytesIO(img_data))
        
        original_width, original_height = img.size
        
        if request.width and request.height and not request.maintain_aspect:
            # Resize to exact dimensions
            new_size = (request.width, request.height)
        elif request.width and request.maintain_aspect:
            # Calculate height based on width
            ratio = request.width / original_width
            new_size = (request.width, int(original_height * ratio))
        elif request.height and request.maintain_aspect:
            # Calculate width based on height
            ratio = request.height / original_height
            new_size = (int(original_width * ratio), request.height)
        elif request.width and request.height:
            # Fit within bounds while maintaining aspect
            ratio = min(request.width / original_width, request.height / original_height)
            new_size = (int(original_width * ratio), int(original_height * ratio))
        else:
            raise HTTPException(status_code=400, detail="Must specify width or height")
        
        resized = img.resize(new_size, Image.LANCZOS)
        
        # Determine output format
        output_format = request.output_format or img.format or 'PNG'
        if output_format.lower() in ('jpg', 'jpeg'):
            output_format = 'JPEG'
            if resized.mode == 'RGBA':
                resized = resized.convert('RGB')
        
        output = BytesIO()
        resized.save(output, format=output_format)
        
        return {
            "output_base64": base64.b64encode(output.getvalue()).decode(),
            "original_size": {"width": original_width, "height": original_height},
            "new_size": {"width": new_size[0], "height": new_size[1]},
            "format": output_format.lower()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resize failed: {str(e)}")


# ============== Text Extraction ==============

@app.post("/extract-text", response_model=TextExtractionResult)
async def extract_text(
    file: UploadFile = File(...),
):
    """
    Extract text from various file formats.
    
    Supports: PDF, DOCX, HTML, Markdown, TXT
    """
    content = await file.read()
    filename = file.filename.lower()
    
    try:
        if filename.endswith('.pdf'):
            text = pdf_to_text(content).decode('utf-8')
            return TextExtractionResult(
                text=text,
                format_detected="pdf"
            )
            
        elif filename.endswith('.docx'):
            import docx
            
            doc = docx.Document(BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs]
            text = '\n\n'.join(paragraphs)
            
            return TextExtractionResult(
                text=text,
                format_detected="docx"
            )
            
        elif filename.endswith('.html') or filename.endswith('.htm'):
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(content.decode('utf-8'), 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            
            return TextExtractionResult(
                text=text,
                format_detected="html"
            )
            
        elif filename.endswith('.md'):
            return TextExtractionResult(
                text=content.decode('utf-8'),
                format_detected="markdown"
            )
            
        elif filename.endswith('.txt'):
            return TextExtractionResult(
                text=content.decode('utf-8'),
                format_detected="txt"
            )
            
        else:
            # Try to decode as text
            try:
                text = content.decode('utf-8')
                return TextExtractionResult(
                    text=text,
                    format_detected="unknown_text"
                )
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot extract text from {filename}"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


# ============== Utility Endpoints ==============

@app.get("/supported-formats")
async def get_supported_formats():
    """List supported format conversions."""
    conversions = []
    for (input_fmt, output_fmt) in SUPPORTED_CONVERSIONS.keys():
        conversions.append({
            "from": input_fmt,
            "to": output_fmt
        })
    
    return {
        "conversions": conversions,
        "image_formats": ["png", "jpg", "webp", "bmp", "gif"],
        "document_formats": ["pdf", "md", "html", "txt", "docx"]
    }


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "filetransform-agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8016)
