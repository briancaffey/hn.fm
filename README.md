# hn.fm

Transform Hacker News into AI-powered podcasts using content scraping, AI processing, text-to-speech, and audio enhancement.

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd hn.fm

# Install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Configure environment
cp env.example .env
# Edit .env with your API keys and service URLs

# Start development environment
make dev-docker
```

## What It Does

1. **Scrapes Hacker News** articles for content
2. **Processes content** using AI to extract key points
3. **Generates scripts** with conversational dialogue between two hosts
4. **Creates audio** using text-to-speech with voice cloning
5. **Enhances audio** using Studio Voice for professional quality
6. **Generates images** for visual content
7. **Creates videos** combining audio and images

## Basic Usage

### Generate a Podcast Episode

```bash
# Run full pipeline
uv run python run_pipeline.py --story-id "test" --story-title "Test Story"

# Run text-only (faster iteration)
uv run python run_text_only_pipeline.py --story-id "test" --story-title "Test Story"

# Resume from specific step
uv run python run_pipeline.py --story-id "test" --story-title "Test Story" --start-from "tts_generation"
```

### Generate Audio from Script

```bash
# Generate audio for existing script
uv run python generate_audio.py outputs/tts_lines_*.txt

# Customize batch size
uv run python generate_audio.py outputs/tts_lines_*.txt --batch-size 3
```

## Development

```bash
# Start development environment
make dev-docker

# Code formatting
make black

# Run tests
make test

# View available commands
make help
```

## Services

- **Web Server**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Flower Monitoring**: http://localhost:5555

## Configuration

Required services:
- TTS Service (for text-to-speech)
- Studio Voice (for audio enhancement)
- Local LLM (for content processing)
- Firecrawl (for web scraping)

## Documentation

See the [documentation folder](documentation/) for detailed guides on:
- Setup and development
- Pipeline usage and content structure
- Audio, image, and video generation
- AI prompt customization
- Web API usage
- Testing and troubleshooting

## Project Structure

```
src/hnfm/
├── audio/          # Audio processing services
├── content/        # Content processing
├── pipeline/       # Pipeline management
├── scraper/        # Content scraping
├── web/           # Web API and Celery
└── utils/         # Utilities and config
```

## License

MIT License - see [LICENSE](LICENSE) for details.
