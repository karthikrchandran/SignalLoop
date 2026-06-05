"""Local STT microservice wrapping faster-whisper.

Usage:
    uv run --with-requirements tooling/stt_service/requirements.txt \
        uvicorn tooling.stt_service.main:app --host 0.0.0.0 --port 9000
"""
from __future__ import annotations

import logging
import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

logger.info(
    "Loading faster-whisper model=%s device=%s compute=%s",
    MODEL_SIZE,
    DEVICE,
    COMPUTE_TYPE,
)
_model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
logger.info("Model loaded.")

app = FastAPI(title="Local STT Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": MODEL_SIZE}


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    model: str = Form(default=""),
) -> dict[str, str | float]:
    """Transcribe uploaded audio and return text, language, and duration."""
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        segments, info = _model.transcribe(tmp_path, beam_size=5)
        text = " ".join(segment.text.strip() for segment in segments)
        return {
            "text": text,
            "language": info.language,
            "duration": round(info.duration, 2),
        }
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        os.unlink(tmp_path)
