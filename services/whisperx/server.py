# NumPy 2.0 Compatibility Fix
import numpy as np
import warnings

def fix_numpy_compatibility():
    """Fix common NumPy 2.0 compatibility issues"""

    # Fix np.NaN -> np.nan issue
    if not hasattr(np, 'NaN'):
        # Add backward compatibility for np.NaN
        np.NaN = np.nan

    # Add backward compatibility for common patterns
    if not hasattr(np, 'float'):
        np.float = np.float64

    if not hasattr(np, 'int'):
        np.int = np.int64

    if not hasattr(np, 'bool'):
        np.bool = np.bool_

    # Suppress deprecation warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning, module='numpy')
    warnings.filterwarnings('ignore', category=FutureWarning, module='numpy')

    print("✅ NumPy compatibility fixes applied")

# Apply fixes when imported
fix_numpy_compatibility()

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import whisperx
import gc
import torch
import tempfile
import os
from typing import Optional
import json

app = FastAPI(title="WhisperX Audio Processing API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 16
COMPUTE_TYPE = "float16"

# Debug CUDA setup
print(f"🔍 CUDA Debug Info:")
print(f"   PyTorch version: {torch.__version__}")
print(f"   CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   CUDA version: {torch.version.cuda}")
    print(f"   cuDNN version: {torch.backends.cudnn.version()}")
    print(f"   GPU device: {torch.cuda.get_device_name(0)}")
    print(f"   GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    print(f"   Selected device: {DEVICE}")
else:
    print("   CUDA not available, using CPU")

@app.post("/process-audio")
async def process_audio(
    audio_file: UploadFile = File(...),
    model_size: str = Form("large-v2"),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
    word_timestamps: bool = Form(True)
):
    """
    Process audio file with WhisperX for transcription, alignment, and speaker diarization.

    Args:
        audio_file: Audio file to process
        model_size: Whisper model size (tiny, base, small, medium, large, large-v2, large-v3)
        min_speakers: Minimum number of speakers (optional)
        max_speakers: Maximum number of speakers (optional)
        word_timestamps: Enable word-level timestamps (default: True)

    Returns:
        JSON with transcription segments, speaker diarization, and metadata
    """

    # Get HF token from environment variable
    hf_token = os.getenv('HF_TOKEN')
    if not hf_token:
        raise HTTPException(status_code=500, detail="HF_TOKEN environment variable not set. Please set export HF_TOKEN='your_token_here'")

    try:
        # Create temporary file to save uploaded audio
        print(f"📁 Creating temporary file for audio upload...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_file.filename.split('.')[-1]}") as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        print(f"✅ Temporary file created: {temp_file_path}")

        try:
            # 1. Load and transcribe with Whisper
            print(f"🎯 Step 1: Loading Whisper model: {model_size}")
            print(f"   Device: {DEVICE}, Compute type: {COMPUTE_TYPE}")
            model = whisperx.load_model(model_size, DEVICE, compute_type=COMPUTE_TYPE)
            print(f"✅ Whisper model loaded successfully")

            print(f"🎵 Step 2: Loading audio file...")
            audio = whisperx.load_audio(temp_file_path)
            print(f"✅ Audio loaded, length: {len(audio)} samples")

            print(f"📝 Step 3: Transcribing audio...")
            result = model.transcribe(audio, batch_size=BATCH_SIZE)
            print(f"✅ Transcription complete, language: {result.get('language', 'Unknown')}")

            # Clean up transcription model
            print(f"🧹 Cleaning up transcription model...")
            del model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"✅ Transcription model cleaned up")

            # 2. Align whisper output
            print(f"🔗 Step 4: Loading alignment model...")
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"],
                device=DEVICE
            )
            print(f"✅ Alignment model loaded")

            print(f"⏰ Step 5: Aligning transcription with word-level timestamps...")
            aligned_result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                DEVICE,
                return_char_alignments=word_timestamps
            )
            print(f"✅ Alignment complete")

            # Clean up alignment model
            print(f"🧹 Cleaning up alignment model...")
            del model_a
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"✅ Alignment model cleaned up")

            # 3. Speaker diarization
            print(f"👥 Step 6: Loading diarization model...")
            diarize_model = whisperx.diarize.DiarizationPipeline(
                use_auth_token=hf_token,
                device=DEVICE
            )
            print(f"✅ Diarization model loaded")

            print(f"🎤 Step 7: Performing speaker diarization...")
            if min_speakers and max_speakers:
                diarize_segments = diarize_model(audio, min_speakers=min_speakers, max_speakers=max_speakers)
            else:
                diarize_segments = diarize_model(audio)
            print(f"✅ Diarization complete")

            print(f"🏷️  Step 8: Assigning speaker labels...")
            final_result = whisperx.assign_word_speakers(diarize_segments, aligned_result)
            print(f"✅ Speaker assignment complete")

            # Clean up diarization model
            print(f"🧹 Cleaning up diarization model...")
            del diarize_model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"✅ Diarization model cleaned up")

            # Convert diarize_segments DataFrame to JSON-serializable format
            print(f"Debug: diarize_segments type: {type(diarize_segments)}")

            try:
                if hasattr(diarize_segments, 'to_dict'):
                    # If it's a pandas DataFrame, convert to records format
                    diarization_data = diarize_segments.to_dict('records')
                    print(f"Debug: Converted DataFrame to {len(diarization_data)} records")

                    # Convert any non-serializable objects in the records
                    def convert_to_serializable(obj):
                        if hasattr(obj, '__dict__'):
                            # Convert objects to dictionaries
                            return {k: convert_to_serializable(v) for k, v in obj.__dict__.items()}
                        elif hasattr(obj, 'start') and hasattr(obj, 'end'):
                            # Handle Segment-like objects with start/end times
                            return {
                                'start': float(obj.start) if hasattr(obj.start, '__float__') else str(obj.start),
                                'end': float(obj.end) if hasattr(obj.end, '__float__') else str(obj.end)
                            }
                        elif hasattr(obj, 'to_dict'):
                            # Handle objects with to_dict method
                            return obj.to_dict()
                        elif isinstance(obj, (list, tuple)):
                            # Handle lists and tuples
                            return [convert_to_serializable(item) for item in obj]
                        elif isinstance(obj, dict):
                            # Handle dictionaries
                            return {k: convert_to_serializable(v) for k, v in obj.items()}
                        elif hasattr(obj, '__str__'):
                            # Fallback: convert to string
                            return str(obj)
                        else:
                            return obj

                    # Convert all records to serializable format
                    diarization_data = [convert_to_serializable(record) for record in diarization_data]
                    print("Debug: Converted records to serializable format")

                elif hasattr(diarize_segments, 'to_json'):
                    # Alternative conversion method
                    diarization_data = diarize_segments.to_json(orient='records')
                    print("Debug: Converted using to_json method")
                else:
                    # If it's already a list/dict, use as is
                    diarization_data = diarize_segments
                    print("Debug: Using diarize_segments as-is")
            except Exception as e:
                print(f"Debug: Error converting diarize_segments: {e}")
                # Fallback: convert to string representation
                diarization_data = str(diarize_segments)

            # Prepare response
            response_data = {
                "success": True,
                "language": result["language"],
                "segments": final_result["segments"],
                "diarization": diarization_data,
                "metadata": {
                    "model_size": model_size,
                    "device": DEVICE,
                    "batch_size": BATCH_SIZE,
                    "compute_type": COMPUTE_TYPE,
                    "word_timestamps": word_timestamps,
                    "audio_duration": len(audio) / 16000,  # Assuming 16kHz sample rate
                    "num_segments": len(final_result["segments"]),
                    "num_speakers": len(set(seg.get("speaker", "UNKNOWN") for seg in final_result["segments"]))
                }
            }

            return JSONResponse(content=response_data)

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except Exception as e:
        print(f"❌ Error processing audio: {str(e)}")
        print(f"🔍 Error type: {type(e).__name__}")
        import traceback
        print("📋 Full traceback:")
        traceback.print_exc()

        # Additional CUDA-specific debugging
        if torch.cuda.is_available():
            print(f"🔍 CUDA Memory Status:")
            print(f"   Allocated: {torch.cuda.memory_allocated() / 1024**2:.1f} MB")
            print(f"   Cached: {torch.cuda.memory_reserved() / 1024**2:.1f} MB")
            print(f"   Max allocated: {torch.cuda.max_memory_allocated() / 1024**2:.1f} MB")

        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    hf_token = os.getenv('HF_TOKEN')
    return {
        "status": "healthy",
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available(),
        "force_cpu": False, # Force_CPU is removed, so this will always be False
        "cuda_working": DEVICE == "cuda",
        "hf_token_set": hf_token is not None,
        "hf_token_length": len(hf_token) if hf_token else 0,
        "hf_token_prefix": hf_token[:8] + "..." if hf_token and len(hf_token) > 8 else "None"
    }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "WhisperX Audio Processing API",
        "version": "1.0.0",
        "endpoints": {
            "POST /process-audio": "Process audio file with transcription and diarization",
            "GET /health": "Health check",
            "GET /": "API information"
        }
    }

if __name__ == "__main__":
    import uvicorn
    import os
    import socket

    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8042))

    # Get local IP address for network access
    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "localhost"

    print(f"🚀 Starting WhisperX server on port {port}")
    print(f"🌐 Server accessible at:")
    print(f"   Local: http://localhost:{port}")
    print(f"   Network: http://{local_ip}:{port}")
    print(f"   Any interface: http://0.0.0.0:{port}")
    print("Press Ctrl+C to stop the server")

    # Server info for integrated browser
    print(f"\n🌐 To open in Cursor's integrated browser:")
    print(f"   1. Install 'Live Server' extension")
    print(f"   2. Right-click on 'index.html'")
    print(f"   3. Select 'Open with Live Server'")
    print(f"   4. Or manually navigate to: http://localhost:{port}")
    print(f"\n📱 For external browser or network access:")
    print(f"   Local: xdg-open http://localhost:{port}")
    print(f"   Network: xdg-open http://{local_ip}:{port}")
    print(f"\n🔗 Other devices on your network can access:")
    print(f"   http://{local_ip}:{port}")

    try:
        uvicorn.run(app, host="0.0.0.0", port=port)
    except OSError as e:
        if "address already in use" in str(e):
            print(f"\n❌ Port {port} is already in use!")
            print(f"Try using a different port:")
            print(f"  PORT=8002 python server.py")
            print(f"  Or kill the process using port {port}:")
            print(f"  sudo lsof -ti:{port} | xargs kill -9")
        else:
            print(f"\n❌ Error starting server: {e}")
