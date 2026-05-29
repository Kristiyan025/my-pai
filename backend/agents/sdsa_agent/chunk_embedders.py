"""
Chunk Embedders for SDSA Agent.
Processes chunks and generates embeddings with metadata.
"""

from typing import Dict, Any, List, Generator, Optional
from dataclasses import dataclass

from chunkers import DocumentChunk, ChunkType
import text_embedder
import image_embedder
import image_text_extractor
import image_captioner
import text_summarizer


@dataclass
class EmbeddingResult:
    """Result of embedding a chunk."""
    embedding: List[float]
    document: str  # Content for text, "user::filepath" for images
    metadata: Dict[str, Any]
    chunk_id: str


class TextChunkEmbedder:
    """
    Embeds text chunks using TextEmbedder.
    Adds summary to metadata via TextSummarizer.
    """
    
    async def embed(
        self, 
        chunk: DocumentChunk, 
        user_id: int,
        source_type: str,
        source_id: str
    ) -> EmbeddingResult:
        """
        Embed a text chunk.
        
        Args:
            chunk: Text chunk to embed
            user_id: User ID
            source_type: "file" or "message"
            source_id: Filepath or message identifier
            
        Returns:
            EmbeddingResult with embedding and metadata
        """
        content = chunk.content
        
        # Generate embedding
        embedding = text_embedder.embed_text(content)
        
        # Generate summary (async)
        try:
            summary = await text_summarizer.summarize_text(content, max_length=50)
        except Exception:
            summary = content[:200] + "..." if len(content) > 200 else content
        
        # Build chunk ID
        chunk_id = f"{user_id}:{source_type}:{source_id}:text:{chunk.chunk_index}"
        
        # Build metadata
        metadata = {
            **chunk.metadata,
            "user_id": user_id,
            "source_type": source_type,
            "source_id": source_id,
            "chunk_type": "text",
            "chunk_index": chunk.chunk_index,
            "summary": summary,
            "embedding_type": "text"
        }
        
        return EmbeddingResult(
            embedding=embedding,
            document=content,
            metadata=metadata,
            chunk_id=chunk_id
        )


class ImageChunkEmbedder:
    """
    Embeds image chunks.
    Produces TWO embeddings per image:
    1. Vision embedding (using ImageEmbedder)
    2. Text embedding of extracted text (using TextEmbedder)
    
    Both include:
    - Extracted text from image (via OCR)
    - Image caption (via ImageCaptioner)
    """
    
    async def embed(
        self, 
        chunk: DocumentChunk,
        user_id: int,
        source_type: str,
        source_id: str,
        filepath: Optional[str] = None
    ) -> List[EmbeddingResult]:
        """
        Embed an image chunk.
        
        Args:
            chunk: Image chunk to embed
            user_id: User ID
            source_type: "file" or "message"
            source_id: Filepath or message identifier
            filepath: Full filepath for document field
            
        Returns:
            List of EmbeddingResult (vision and text embeddings)
        """
        image_data = chunk.content
        results = []
        
        # Extract text from image (reuse across both embeddings)
        try:
            extracted_text = image_text_extractor.extract_text(image_data)
        except Exception:
            extracted_text = ""
        
        # Generate caption (only once!)
        try:
            caption = await image_captioner.caption_image(image_data)
        except Exception:
            caption = ""
        
        # Document field for images: "user::filepath"
        doc_field = f"{user_id}::{filepath or source_id}"
        
        base_metadata = {
            **chunk.metadata,
            "user_id": user_id,
            "source_type": source_type,
            "source_id": source_id,
            "chunk_type": "image",
            "chunk_index": chunk.chunk_index,
            "extracted_text": extracted_text,
            "caption": caption
        }
        
        # 1. Vision embedding
        try:
            vision_embedding = image_embedder.embed_image(image_data)
            vision_chunk_id = f"{user_id}:{source_type}:{source_id}:image:{chunk.chunk_index}:vision"
            
            results.append(EmbeddingResult(
                embedding=vision_embedding,
                document=doc_field,
                metadata={**base_metadata, "embedding_type": "vision"},
                chunk_id=vision_chunk_id
            ))
        except Exception as e:
            print(f"Vision embedding failed: {e}")
        
        # 2. Text embedding of extracted text (if there is any)
        if extracted_text.strip():
            try:
                # Combine extracted text and caption for richer embedding
                text_for_embedding = f"{extracted_text}\n\n{caption}" if caption else extracted_text
                text_embedding = text_embedder.embed_text(text_for_embedding)
                
                text_chunk_id = f"{user_id}:{source_type}:{source_id}:image:{chunk.chunk_index}:text"
                
                results.append(EmbeddingResult(
                    embedding=text_embedding,
                    document=doc_field,
                    metadata={**base_metadata, "embedding_type": "text_from_image"},
                    chunk_id=text_chunk_id
                ))
            except Exception as e:
                print(f"Text embedding from image failed: {e}")
        
        return results


class ChunkEmbedder:
    """
    Factory class that routes chunks to appropriate embedder.
    """
    
    def __init__(self):
        self.text_embedder = TextChunkEmbedder()
        self.image_embedder = ImageChunkEmbedder()
    
    async def embed(
        self,
        chunk: DocumentChunk,
        user_id: int,
        source_type: str,
        source_id: str,
        filepath: Optional[str] = None
    ) -> List[EmbeddingResult]:
        """
        Embed a chunk based on its type.
        
        Returns a list because image chunks produce multiple embeddings.
        """
        if chunk.chunk_type == ChunkType.TEXT:
            result = await self.text_embedder.embed(chunk, user_id, source_type, source_id)
            return [result]
        elif chunk.chunk_type == ChunkType.IMAGE:
            return await self.image_embedder.embed(chunk, user_id, source_type, source_id, filepath)
        else:
            raise ValueError(f"Unknown chunk type: {chunk.chunk_type}")


async def process_document(
    content: Any,
    file_type: str,
    user_id: int,
    filepath: str,
    chunk_embedder: ChunkEmbedder = None
) -> Generator[EmbeddingResult, None, None]:
    """
    Process a document: chunk it and generate embeddings.
    
    Args:
        content: Document content (bytes or string)
        file_type: File extension
        user_id: User ID
        filepath: Full filepath
        chunk_embedder: Optional ChunkEmbedder instance
        
    Yields:
        EmbeddingResult objects
    """
    from chunkers import DocumentChunker
    
    if chunk_embedder is None:
        chunk_embedder = ChunkEmbedder()
    
    document_chunker = DocumentChunker()
    
    metadata = {
        "user_id": user_id,
        "filepath": filepath,
        "file_type": file_type
    }
    
    # Chunk the document
    for chunk in document_chunker.chunk(content, file_type, metadata):
        # Embed the chunk
        embedding_results = await chunk_embedder.embed(
            chunk,
            user_id=user_id,
            source_type="file",
            source_id=filepath,
            filepath=filepath
        )
        
        for result in embedding_results:
            yield result


async def process_chat_message(
    message_text: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    context_messages: List[str] = None,
    chunk_embedder: ChunkEmbedder = None
) -> Generator[EmbeddingResult, None, None]:
    """
    Process a chat message for embedding.
    
    Args:
        message_text: Message content
        user_id: User ID
        chat_id: Chat ID
        message_id: Message ID
        context_messages: Previous messages for context
        chunk_embedder: Optional ChunkEmbedder instance
        
    Yields:
        EmbeddingResult objects
    """
    from chunkers import DocumentChunker
    
    if chunk_embedder is None:
        chunk_embedder = ChunkEmbedder()
    
    document_chunker = DocumentChunker()
    
    # Combine message with context
    full_text = message_text
    if context_messages:
        context_text = "\n---\n".join(context_messages)
        full_text = f"Context:\n{context_text}\n---\nCurrent message:\n{message_text}"
    
    source_id = f"chat:{chat_id}:msg:{message_id}"
    
    metadata = {
        "user_id": user_id,
        "chat_id": chat_id,
        "message_id": message_id
    }
    
    # Chunk as plain text
    for chunk in document_chunker.chunk(full_text, "txt", metadata):
        embedding_results = await chunk_embedder.embed(
            chunk,
            user_id=user_id,
            source_type="message",
            source_id=source_id
        )
        
        for result in embedding_results:
            yield result
