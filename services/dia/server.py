import io
import os
import tempfile
import time
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from dia.model import Dia


# --- Logging Setup ---
LOG_LEVEL = os.environ.get("LOG_LEVEL") or ("DEBUG" if os.environ.get("DIA_DEBUG") else "INFO")
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("dia.server")


app = FastAPI(
    title="Dia FastAPI Server",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Force Hugging Face cache location to avoid re-downloading models
HF_HOME_DEFAULT = "/mnt/e/a3data/huggingface"
try:
    current_hf_home = os.environ.get("HF_HOME")
    if current_hf_home != HF_HOME_DEFAULT:
        os.environ["HF_HOME"] = HF_HOME_DEFAULT
        logger.info(f"Set HF_HOME to {HF_HOME_DEFAULT}")
    else:
        logger.info(f"HF_HOME already set to {HF_HOME_DEFAULT}")
except Exception as e:
    logger.warning(f"Failed to set HF_HOME: {e}")


# --- Model lifecycle management ---
model: Optional[Dia] = None
device: Optional[torch.device] = None


def _select_device() -> torch.device:
    if not torch.cuda.is_available():
        logger.error(
            "CUDA is not available. GPU is required for inference. Install CUDA-enabled PyTorch wheels and ensure NVIDIA drivers are installed."
        )
        raise HTTPException(status_code=503, detail="CUDA not available; GPU is required for inference.")
    logger.debug("CUDA is available; selecting cuda device")
    return torch.device("cuda")


def _load_model() -> None:
    global model, device
    if model is not None:
        logger.debug("Model already loaded; skipping load")
        return
    device = _select_device()
    logger.info(f"Selected device: {device}")
    try:
        cuda_info = {
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": getattr(torch.version, "cuda", None),
            "cudnn_version": getattr(torch.backends.cudnn, "version", lambda: None)(),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }
        logger.info(f"CUDA info: {cuda_info}")
    except Exception as e:
        logger.warning(f"Failed to query CUDA info: {e}")
    dtype_map = {"cpu": "float32", "mps": "float32", "cuda": "float16"}
    dtype = dtype_map.get(device.type, "float16")
    logger.info(f"Loading Dia model with dtype={dtype} on device={device}...")
    t0 = time.time()
    model = Dia.from_pretrained("nari-labs/Dia-1.6B-0626", compute_dtype=dtype, device=device)
    logger.info(f"Model loaded in {time.time() - t0:.2f}s")


def _unload_model() -> None:
    global model
    if model is not None:
        try:
            # Best-effort cleanup
            del model
        finally:
            model = None
    if torch.cuda.is_available():
        try:
            before_alloc = torch.cuda.memory_allocated()
            before_reserved = torch.cuda.memory_reserved()
        except Exception:
            before_alloc = before_reserved = None
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
        try:
            after_alloc = torch.cuda.memory_allocated()
            after_reserved = torch.cuda.memory_reserved()
        except Exception:
            after_alloc = after_reserved = None
        logger.info(
            f"CUDA memory cleanup: allocated {before_alloc} -> {after_alloc}, reserved {before_reserved} -> {after_reserved}"
        )


@app.get("/health")
def health() -> JSONResponse:
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        try:
            mem_info = {
                "allocated": torch.cuda.memory_allocated(),
                "reserved": torch.cuda.memory_reserved(),
            }
        except Exception:
            mem_info = None
    else:
        mem_info = None
    status = {
        "status": "ok",
        "device": str(device) if device else None,
        "model_loaded": model is not None,
        "cuda_available": cuda_available,
        "cuda_mem": mem_info,
    }
    return JSONResponse(status)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)


 


def _save_temp_wav_from_upload(upload: Optional[UploadFile]) -> Optional[str]:
    if upload is None:
        return None

    # Read bytes and decode with soundfile
    data = upload.file.read()
    if not data:
        return None

    with io.BytesIO(data) as bio:
        try:
            audio_data, sr = sf.read(bio, dtype="float32", always_2d=False)
        except Exception as e:  # fallback: some containers need write to disk first
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(upload.filename or "prompt").suffix or ".wav")
            tmp.write(data)
            tmp.flush()
            tmp.close()
            try:
                audio_data, sr = sf.read(tmp.name, dtype="float32", always_2d=False)
            finally:
                Path(tmp.name).unlink(missing_ok=True)

    # ensure mono
    if audio_data.ndim > 1:
        if audio_data.shape[0] == 2:
            audio_data = np.mean(audio_data, axis=0)
        elif audio_data.shape[1] == 2:
            audio_data = np.mean(audio_data, axis=1)
        else:
            audio_data = audio_data[..., 0]
        audio_data = np.ascontiguousarray(audio_data)

    # write to true temp wav on disk for model.generate
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".wav", delete=False) as f_audio:
        sf.write(f_audio.name, audio_data, sr, subtype="FLOAT")
        return f_audio.name


def _apply_speed(audio: np.ndarray, speed_factor: float) -> np.ndarray:
    speed_factor = max(0.1, min(speed_factor, 5.0))
    original_len = len(audio)
    target_len = int(original_len / speed_factor)
    if target_len > 0 and target_len != original_len:
        x_original = np.arange(original_len)
        x_resampled = np.linspace(0, original_len - 1, target_len)
        return np.interp(x_resampled, x_original, audio).astype(np.float32)
    return audio.astype(np.float32)


# --- Lifecycle Hooks ---
@app.on_event("startup")
def on_startup() -> None:
    logger.info("App startup: loading model...")
    _load_model()
    logger.info("App startup: model loaded successfully")


@app.on_event("shutdown")
def on_shutdown() -> None:
    logger.info("App shutdown: unloading model and cleaning up CUDA memory...")
    _unload_model()
    logger.info("App shutdown: cleanup completed")


@app.post("/generate")
def generate(
    text: str = Form(..., description="Generation script. Must start with [S1] and alternate [S1]/[S2]."),
    audio_prompt_text: Optional[str] = Form(None, description="Transcript of the uploaded audio prompt."),
    audio_prompt: Optional[UploadFile] = File(None, description="Audio file for voice prompting."),
    max_new_tokens: int = Form(3072),
    cfg_scale: float = Form(3.0),
    temperature: float = Form(1.8),
    top_p: float = Form(0.95),
    cfg_filter_top_k: int = Form(45),
    speed_factor: float = Form(1.0),
    seed: int = Form(-1),
):
    logger.info(
        {
            "event": "generate_request",
            "has_audio_prompt": audio_prompt is not None,
            "text_len": len(text) if text else 0,
            "params": {
                "max_new_tokens": max_new_tokens,
                "cfg_scale": cfg_scale,
                "temperature": temperature,
                "top_p": top_p,
                "cfg_filter_top_k": cfg_filter_top_k,
                "speed_factor": speed_factor,
                "seed": seed,
            },
        }
    )
    try:
        _load_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {e}")

    # basic validations similar to Gradio app
    if audio_prompt is not None:
        if not audio_prompt_text or audio_prompt_text.isspace():
            raise HTTPException(status_code=400, detail="audio_prompt_text is required when audio_prompt is provided")

    if not text or text.isspace():
        raise HTTPException(status_code=400, detail="text cannot be empty")

    # If audio prompt text provided, prepend it to text as in Gradio app
    if audio_prompt is not None and audio_prompt_text:
        text = (audio_prompt_text + "\n" + text).strip()

    prompt_path: Optional[str] = None
    sr = 44100
    try:
        if audio_prompt is not None:
            prompt_path = _save_temp_wav_from_upload(audio_prompt)
            logger.debug(f"Saved audio prompt to temp path: {prompt_path}")

        if seed is None or seed < 0:
            seed = int(torch.randint(0, 2**31 - 1, (1,)).item())
        logger.debug(f"Using seed: {seed}")
        # set seeds
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)

        start = time.time()
        if torch.cuda.is_available():
            try:
                logger.debug(
                    f"CUDA mem before generate: alloc={torch.cuda.memory_allocated()} reserved={torch.cuda.memory_reserved()}"
                )
            except Exception:
                pass
        with torch.inference_mode():
            audio_np = model.generate(
                text,
                max_tokens=max_new_tokens,
                cfg_scale=cfg_scale,
                temperature=temperature,
                top_p=top_p,
                cfg_filter_top_k=cfg_filter_top_k,
                use_torch_compile=False,
                audio_prompt=prompt_path,
                verbose=True,
            )
        if torch.cuda.is_available():
            try:
                logger.debug(
                    f"CUDA mem after generate: alloc={torch.cuda.memory_allocated()} reserved={torch.cuda.memory_reserved()}"
                )
            except Exception:
                pass
        # speed adjustment and return WAV bytes
        audio_np = _apply_speed(audio_np, speed_factor)
        duration = len(audio_np) / float(sr)
        logger.info(f"Generated audio: shape={audio_np.shape}, sr={sr}, duration={duration:.3f}s, time={time.time()-start:.2f}s")

        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, audio_np, sr, subtype="PCM_16", format="WAV")
        wav_buffer.seek(0)

        headers = {
            "x-seed": str(seed),
            "x-sample-rate": str(sr),
            "x-duration-seconds": f"{duration:.3f}",
        }
        return StreamingResponse(wav_buffer, media_type="audio/wav", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")
    finally:
        if prompt_path and Path(prompt_path).exists():
            Path(prompt_path).unlink(missing_ok=True)


@app.post("/cleanup")
def cleanup() -> JSONResponse:
    _unload_model()
    return JSONResponse({"status": "ok", "message": "Freed VRAM and unloaded model"})


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8491))
    uvicorn.run("server:app", host=host, port=port, reload=False, log_level=LOG_LEVEL.lower(), access_log=True)


