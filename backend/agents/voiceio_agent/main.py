import os
import sys
import tempfile
import base64
from typing import Optional
from io import BytesIO

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(
    title="Voice IO Agent",
    description="Speech-to-text and text-to-speech conversion",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")


_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(
                WHISPER_MODEL,
                device="cuda",
                compute_type="float16"
            )
        except Exception:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(
                WHISPER_MODEL,
                device="cpu",
                compute_type="int8"
            )
    return _whisper_model


def unload_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        del _whisper_model
        _whisper_model = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


def get_tts_model():
    return None


def unload_tts_model():
    pass


class TranscriptionResult(BaseModel):
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    segments: Optional[list] = None


class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    speed: float = 1.0


class TTSResponse(BaseModel):
    audio_base64: str
    format: str = "wav"
    duration_ms: Optional[int] = None


@app.post("/stt", response_model=TranscriptionResult)
async def speech_to_text(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = Query(None, description="Language code (auto-detect if not provided)")
):
    try:
        content = await audio.read()
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            model = get_whisper_model()
            
            segments, info = model.transcribe(
                tmp_path,
                language=language,
                beam_size=5,
                vad_filter=True
            )
            
            segment_list = []
            full_text_parts = []
            
            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                full_text_parts.append(segment.text.strip())
            
            full_text = " ".join(full_text_parts)
            
            return TranscriptionResult(
                text=full_text,
                language=info.language,
                confidence=info.language_probability,
                segments=segment_list
            )
            
        finally:
            os.unlink(tmp_path)
            unload_whisper_model()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.post("/stt/base64", response_model=TranscriptionResult)
async def speech_to_text_base64(
    audio_base64: str,
    language: Optional[str] = None
):
    try:
        audio_data = base64.b64decode(audio_base64)
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        
        try:
            model = get_whisper_model()
            
            segments, info = model.transcribe(
                tmp_path,
                language=language,
                beam_size=5,
                vad_filter=True
            )
            
            segment_list = []
            full_text_parts = []
            
            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                full_text_parts.append(segment.text.strip())
            
            full_text = " ".join(full_text_parts)
            
            return TranscriptionResult(
                text=full_text,
                language=info.language,
                confidence=info.language_probability,
                segments=segment_list
            )
            
        finally:
            os.unlink(tmp_path)
            unload_whisper_model()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(request: TTSRequest):
    try:
        tts = get_tts_model()
        
        if tts is None:
            return await tts_fallback(request)
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            tts.tts_to_file(
                text=request.text,
                file_path=tmp_path,
                speed=request.speed
            )
            
            with open(tmp_path, "rb") as f:
                audio_data = f.read()
            
            audio_base64 = base64.b64encode(audio_data).decode()
            
            duration_ms = len(audio_data) // 32
            
            return TTSResponse(
                audio_base64=audio_base64,
                format="wav",
                duration_ms=duration_ms
            )
            
        finally:
            os.unlink(tmp_path)
            unload_tts_model()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


async def tts_fallback(request: TTSRequest) -> TTSResponse:
    try:
        import pyttsx3
        
        engine = pyttsx3.init()
        engine.setProperty('rate', int(150 * request.speed))
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            engine.save_to_file(request.text, tmp_path)
            engine.runAndWait()
            
            with open(tmp_path, "rb") as f:
                audio_data = f.read()
            
            audio_base64 = base64.b64encode(audio_data).decode()
            
            return TTSResponse(
                audio_base64=audio_base64,
                format="wav"
            )
        finally:
            os.unlink(tmp_path)
            engine.stop()
            
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="TTS not available. Install TTS or pyttsx3."
        )


@app.post("/tts/stream")
async def text_to_speech_stream(request: TTSRequest):
    try:
        tts = get_tts_model()
        
        if tts is None:
            raise HTTPException(status_code=503, detail="TTS streaming requires Coqui TTS")
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            tts.tts_to_file(
                text=request.text,
                file_path=tmp_path,
                speed=request.speed
            )
            
            def iterfile():
                with open(tmp_path, "rb") as f:
                    while chunk := f.read(8192):
                        yield chunk
            
            return StreamingResponse(
                iterfile(),
                media_type="audio/wav",
                headers={"Content-Disposition": "attachment; filename=speech.wav"}
            )
            
        finally:
            pass
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@app.get("/models")
async def list_available_models():
    whisper_models = ["tiny", "base", "small", "medium", "large"]
    
    tts_models = []
    try:
        from TTS.api import TTS
        tts_models = TTS().list_models()
    except ImportError:
        tts_models = ["pyttsx3 (fallback)"]
    
    return {
        "stt_models": whisper_models,
        "stt_current": WHISPER_MODEL,
        "tts_models": tts_models[:20] if len(tts_models) > 20 else tts_models,
        "tts_current": TTS_MODEL
    }


@app.post("/unload-models")
async def unload_models():
    unload_whisper_model()
    unload_tts_model()
    return {"status": "models_unloaded"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "voiceio-agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8015)
