# WhisperX Audio Processing API

A FastAPI server that provides audio transcription with speaker diarization using OpenAI's Whisper and WhisperX, along with a beautiful web interface for easy interaction.

## Features

- 🎤 **Audio Transcription**: Convert audio to text using various Whisper model sizes
- 🎯 **Word-Level Alignment**: Precise timestamp alignment for each word
- 👥 **Speaker Diarization**: Identify and separate different speakers in the audio
- 🌐 **Web Interface**: Beautiful, responsive web UI for easy file upload and result viewing
- 📱 **Mobile Friendly**: Responsive design that works on all devices
- 📊 **Rich Metadata**: Detailed information about processing results
- 💾 **Export Functionality**: Download results in JSON format
- 🚀 **FastAPI Backend**: High-performance async API with automatic documentation

## Prerequisites

- Python 3.8 or higher
- CUDA-capable GPU (recommended for optimal performance)
- HuggingFace account and access token for speaker diarization

## Installation

1. **Clone or download the files** to your local machine

2. **Set up virtual environment and install dependencies**:

   **Option A: Using uv (recommended)**
   ```bash
   # Install uv if you don't have it
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Create virtual environment and install dependencies
   uv venv
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

   **Option B: Using pip**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set your HuggingFace token as an environment variable**:
   ```bash
   export HF_TOKEN='your_huggingface_token_here'
   ```

   To get a token:
   - Go to [HuggingFace Settings](https://huggingface.co/settings/tokens)
   - Create a new token
   - Accept the terms for pyannote/speaker-diarization model

## Usage

### Starting the Server

1. **Set your HuggingFace token** (if not already set):
   ```bash
   export HF_TOKEN='your_huggingface_token_here'
   ```

2. **Activate your virtual environment** (if not already active):
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Run the FastAPI server**:
   ```bash
   python server.py
   ```

   The server will start on `http://localhost:8042`

2. **Access the web interface**:
   - Open `index.html` in your web browser
   - Or serve it using a simple HTTP server:
     ```bash
     python -m http.server 8001
     ```
     Then visit `http://localhost:8001`

### Using the Web Interface

1. **Upload Audio**: Drag and drop or click to select an audio file
2. **Configure Settings**:
   - Choose Whisper model size (larger = more accurate but slower)
   - Enter your HuggingFace token
   - Optionally set min/max speaker counts
3. **Process**: Click "Process Audio" and wait for completion
4. **View Results**: See transcription with speaker labels and timestamps
5. **Export**: Download results as JSON file

### Using the Python Client

```python
from client import WhisperXClient

# Initialize client
client = WhisperXClient("http://localhost:8042")

# Process audio file
results = client.process_audio(
    audio_file_path="path/to/audio.mp3",
    hf_token="your_huggingface_token",
    model_size="large-v2"
)

# Print results in a readable format
client.print_results(results)
```

### API Endpoints

- `POST /process-audio`: Process audio file with transcription and diarization
- `GET /health`: Check server health and CUDA availability
- `GET /`: API information and available endpoints
- `GET /docs`: Interactive API documentation (Swagger UI)

## Configuration

### Server Configuration

Edit `server.py` to modify:
- Device selection (CUDA/CPU)
- Batch size for processing
- Compute type (float16/int8)
- Model loading preferences

### Web Interface Configuration

Edit `script.js` to modify:
- API base URL
- Progress simulation timing
- Toast notification duration

## Supported Audio Formats

- MP3, WAV, FLAC, M4A, OGG
- Any format supported by WhisperX
- Recommended: 16kHz sample rate for optimal performance

## Model Sizes

- **Tiny**: Fastest, least accurate
- **Base**: Good balance of speed/accuracy
- **Small**: Better accuracy, moderate speed
- **Medium**: High accuracy, slower
- **Large**: Very high accuracy, slow
- **Large V2**: Best accuracy, slowest (recommended)
- **Large V3**: Latest model, highest accuracy

## Performance Tips

1. **GPU Memory**: Use smaller models if you encounter CUDA out of memory errors
2. **Batch Size**: Reduce `BATCH_SIZE` in server.py if needed
3. **Compute Type**: Switch to "int8" for lower memory usage
4. **Audio Length**: Longer files take proportionally longer to process

## Troubleshooting

### Common Issues

1. **CUDA Out of Memory**:
   - Reduce batch size in server.py
   - Use smaller model size
   - Switch to CPU processing

2. **HuggingFace Token Error**:
   - Ensure you have accepted the pyannote/speaker-diarization model terms
   - Check token validity and permissions

3. **Audio Loading Issues**:
   - Verify audio file format is supported
   - Check file isn't corrupted
   - Ensure sufficient disk space for temporary files

4. **Server Connection Issues**:
   - Verify server is running on correct port
   - Check firewall settings
   - Ensure CORS is properly configured

### Debug Mode

Enable debug logging by modifying the server:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## File Structure

```
├── server.py              # FastAPI server implementation
├── client.py              # Python client for API usage
├── index.html             # Web interface HTML
├── styles.css             # Web interface styling
├── script.js              # Web interface functionality
├── requirements.txt       # Python dependencies
└── README_WHISPERX_API.md # This file
```

## API Response Format

```json
{
  "success": true,
  "language": "en",
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello, how are you?",
      "speaker": "SPEAKER_00"
    }
  ],
  "diarization": [...],
  "metadata": {
    "model_size": "large-v2",
    "device": "cuda",
    "audio_duration": 120.5,
    "num_segments": 45,
    "num_speakers": 3
  }
}
```

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the project.

## License

This project uses the same license as WhisperX. Please refer to the original WhisperX repository for license information.

## Acknowledgments

- OpenAI for the Whisper model
- WhisperX team for the enhanced transcription capabilities
- Pyannote team for speaker diarization
- FastAPI team for the excellent web framework
