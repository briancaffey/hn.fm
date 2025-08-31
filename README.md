# hn.fm - AI-Powered Podcast Pipeline

Transform Hacker News into your personalized AI-powered podcast using a sophisticated pipeline that combines content scraping, AI processing, text-to-speech, and audio enhancement.

## 🚀 Features

- **Complete Pipeline Workflow**: From HN scraping to final audio assembly
- **AI-Powered Content Processing**: Intelligent content extraction and script generation
- **High-Quality TTS**: Voice cloning with customizable voices
- **Audio Enhancement**: Studio Voice integration for professional audio quality
- **Smart Caching**: Resume from any step using cached data
- **YAML Configuration**: Easy configuration management
- **Modular Architecture**: Extensible pipeline with pluggable components
- **Local Testing**: Test Firecrawl integration with local HTML files for faster development

## 🏗️ Architecture

The system follows a step-by-step pipeline architecture:

```
1. HN Scraping → 2. Firecrawl Content → 3. Content Processing →
4. Script Generation → 5. TTS Generation → 6. Audio Cleaning → 7. Audio Assembly
```

Each step can be:
- **Executed independently** for testing
- **Cached and reused** to avoid recomputation
- **Resumed from** any point in the workflow

## 📋 Prerequisites

- Python 3.9+
- TTS Service running on `http://192.168.5.96:7860`
- Studio Voice (NVIDIA NIM) service on `192.168.5.96:8001`
- Voice samples in `voices/` directory

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd hn.fm
   ```

2. **Install dependencies**:
   ```bash
   uv add pydub gradio-client grpcio grpcio-tools soundfile scipy numpy pyyaml
   ```

3. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with your API keys and service URLs
   # Required variables:
   # - TTS_BASE_URL: Your TTS service URL
   # - STUDIO_VOICE_TARGET: Your Studio Voice service address
   # - LLM_BASE_URL: Your local LLM service URL
   # - FIRECRAWL_API_KEY: Your Firecrawl API key (if using remote service)
   ```

4. **Configure voices**:
   ```bash
   # Ensure you have voice samples in voices/notebooklm/
   ls voices/notebooklm/
   # Should show: sample.txt, sample.wav
   ```

## ⚙️ Configuration

### YAML Configuration (`config.yaml`)

The system uses a comprehensive YAML configuration file:

```yaml
# Voice Configuration
voice:
  default: "notebooklm"
  available_voices: ["notebooklm", "studio_voice"]

# TTS Service Configuration
tts:
  base_url: "http://192.168.5.96:7860"
  default_voice: "notebooklm"
  batch_size: 2
  max_attempts: 3

# Studio Voice Configuration
studio_voice:
  enabled: true
  target: "192.168.5.96:8001"
  model_type: "48k-hq"  # 48k-hq, 48k-ll, 16k-hq
  sample_rate: 48000

# Pipeline Configuration
pipeline:
  skippable_steps: ["hn_scraping", "firecrawl_content", "content_processing",
                    "script_generation", "tts_generation", "audio_cleaning", "audio_assembly"]
  cache:
    enabled: true
    directory: "cache"
    expiration_hours: 24
```

### Environment Variables

Key environment variables (automatically loaded from `.env`):

```bash
# TTS Service
TTS_BASE_URL=http://192.168.5.96:7860
TTS_DEFAULT_VOICE=notebooklm

# Studio Voice Configuration (NVIDIA NIM)
STUDIO_VOICE_TARGET=192.168.5.96:8001
STUDIO_VOICE_MODEL_TYPE=48k-hq

# Local LLM Configuration
LLM_BASE_URL=http://192.168.5.173:1234/v1
LLM_FALLBACK_URL=http://192.168.5.96:1234
LLM_MODEL=openai/gpt-oss-20b

# API Keys
FIRECRAWL_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Firecrawl Configuration
FIRECRAWL_BASE_URL=http://localhost:3002

# Development Configuration
DEBUG=false
LOG_LEVEL=INFO
```

**Important**: Copy `env.example` to `.env` and fill in your actual values. Never commit the `.env` file to version control.

## 🎯 Usage

### Quick Start

Generate audio from existing TTS lines:

```bash
# Generate audio for a story
uv run python generate_audio.py outputs/tts_lines_How_to_Start_Making_Games_in_J.txt

# Customize batch size and output
uv run python generate_audio.py outputs/tts_lines_*.txt --batch-size 3 --story-name "Custom Story"
```

### Full Pipeline

Run the complete pipeline workflow:

```bash
# Run full pipeline
uv run python run_pipeline.py --story-id "game-dev-js" --story-title "How to Start Making Games in JavaScript"

# Resume from a specific step
uv run python run_pipeline.py --story-id "game-dev-js" --story-title "How to Start Making Games in JavaScript" --start-from "tts_generation"

# Dry run to see what would be executed
uv run python run_pipeline.py --story-id "test" --story-title "Test Story" --dry-run

# List available pipeline steps
uv run python run_pipeline.py --list-steps
```

### Pipeline Steps

1. **`hn_scraping`**: Scrape Hacker News articles
2. **`firecrawl_content`**: Extract content using Firecrawl
3. **`content_processing`**: Process and clean content
4. **`script_generation`**: Generate podcast script with [S1]/[S2] tags
5. **`tts_generation`**: Generate TTS audio in batches
6. **`audio_cleaning`**: Clean audio using Studio Voice
7. **`audio_assembly`**: Combine all audio into final file

## 🎵 Audio Processing

### TTS Generation

- **Batch Processing**: Configurable batch sizes (default: 2 lines)
- **Voice Cloning**: Uses your voice samples for consistency
- **Retry Logic**: Up to 3 attempts with different seeds
- **Progress Tracking**: Detailed logging throughout the process

### Audio Enhancement

- **Sample Rate Conversion**: Automatic conversion to 48kHz
- **Studio Voice Integration**: Professional audio enhancement
- **Quality Options**: High-quality (48k-hq) or low-latency (48k-ll) models
- **Streaming Support**: Both transactional and streaming modes

## 📁 Output Structure

```
outputs/
  Story Name/
    batch_001.wav              # Raw TTS audio
    cleaned_batch_001.wav      # Enhanced audio
    batch_002.wav
    cleaned_batch_002.wav
    ...
    Story Name_final.wav       # Final combined audio
```

## 🔧 Development

### Auto-Reload Development Setup

The project includes auto-reload functionality for Celery workers and beat, making development much more efficient:

```bash
# Start services with auto-reload (recommended for development)
make celery-worker    # Start worker with auto-reload
make celery-beat       # Start beat with auto-reload
make dev-start         # Start all services with auto-reload

# Docker development with auto-reload
make dev-docker        # Start all services in Docker with auto-reload
make docker-up         # Start development services
make docker-down       # Stop all services

# Simple mode (no auto-reload) for debugging
make celery-worker-simple
make celery-beat-simple
```

**Features:**
- **Automatic Restart**: Workers and beat restart when Python code changes
- **File Watching**: Monitors `src/hnfm/` directory tree for changes
- **Docker Support**: Full auto-reload support in Docker containers
- **Graceful Shutdown**: Clean shutdown with Ctrl+C
- **Detailed Logging**: Comprehensive logging of restart events

For detailed information, see [AUTORELOAD_README.md](AUTORELOAD_README.md).

### Project Structure

```
src/hnfm/
  ├── audio/                   # Audio processing services
  │   ├── tts_service.py      # TTS integration
  │   ├── studio_voice_service.py  # Audio enhancement
  │   └── audio_processor.py  # Audio manipulation
  ├── content/                 # Content processing
  │   ├── content_processor.py
  │   ├── script_generator.py
  │   └── llm_service.py
  ├── pipeline/                # Pipeline management
  │   └── pipeline_manager.py
  ├── scraper/                 # Content scraping
  │   ├── hn_scraper.py
  │   └── content_scraper.py
  └── utils/                   # Utilities
      ├── config.py            # Configuration management
      └── logger.py
```

### Adding New Pipeline Steps

1. **Define the step** in `PipelineManager._define_pipeline_steps()`
2. **Implement execution** in `PipelineManager._execute_<step_name>()`
3. **Add to configuration** in `config.yaml`
4. **Update dependencies** as needed

### Code Formatting

This project uses [Black](https://black.readthedocs.io/) for consistent Python code formatting. Black is already configured in your environment and `pyproject.toml`.

#### **Using Makefile (Recommended)**

```bash
# Format all Python code
make black

# Check formatting without making changes
make black-check

# See all available commands
make help
```

#### **Direct Commands**

```bash
# Format all Python files
uv run black . --line-length 88 --exclude .venv

# Format specific directories
uv run black src/ --line-length 88
uv run black *.py --line-length 88

# Check formatting without making changes
uv run black . --line-length 88 --exclude .venv --check
```

**Black Configuration** (already set in `pyproject.toml`):
- Line length: 88 characters
- Target Python version: 3.9+
- Profile: Black-compatible

### Testing

```bash
# Test individual components
uv run python -c "from src.hnfm.audio.tts_service import TTSService; print('✅ TTS Service')"
uv run python -c "from src.hnfm.audio.studio_voice_service import StudioVoiceService; print('✅ Studio Voice Service')"

# Test pipeline
uv run python run_pipeline.py --story-id "test" --story-title "Test" --dry-run
```

## 🚨 Troubleshooting

### Common Issues

1. **TTS Service Unavailable**
   - Check if service is running at configured URL
   - Verify network connectivity

2. **Studio Voice Connection Failed**
   - Ensure gRPC service is running
   - Check target IP and port
   - Verify model type compatibility

3. **Audio Processing Errors**
   - Check pydub installation
   - Verify audio file formats
   - Ensure sufficient disk space

### Debug Mode

Enable detailed logging:

```bash
# Set environment variables
export DEBUG=true
export LOG_LEVEL=DEBUG

# Or use CLI flag
uv run python run_pipeline.py --debug --story-id "test" --story-title "Test" --dry-run
```

## 🔮 Future Enhancements

- [ ] **Multiple Voice Support**: Easy switching between voices
- [ ] **Audio Post-Processing**: Normalization, effects, music integration
- [ ] **Progress Persistence**: Save/restore pipeline state
- [ ] **Parallel Processing**: Execute independent steps concurrently
- [ ] **Quality Metrics**: Audio quality assessment and optimization
- [ ] **Web Interface**: GUI for pipeline management
- [ ] **Cloud Integration**: Deploy pipeline to cloud services

## 📚 Documentation

- [TTS Pipeline Guide](TTS_PIPELINE_README.md) - Detailed TTS usage
- [Configuration Guide](config.yaml) - Configuration options
- [API Reference](src/hnfm/) - Code documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **NVIDIA Studio Voice** for audio enhancement
- **Gradio** for TTS service integration
- **Hacker News** for content inspiration

---

**Ready to create your AI-powered podcast?** Start with the [Quick Start](#quick-start) section and explore the [Pipeline Steps](#pipeline-steps) to understand the complete workflow!
