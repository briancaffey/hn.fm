# Development Guide

This guide covers everything you need to develop and run hn.fm locally.

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd hn.fm

# Install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Start development environment
make dev-docker
```

## Development Commands

### Code Quality
```bash
make black          # Format code
make black-check    # Check formatting
make test           # Run tests
```

### Services
```bash
# Start all services with auto-reload
make dev-docker

# Individual services
make docker-up      # Start services
make docker-down    # Stop services
make docker-logs    # View logs
```

### Celery (Background Tasks)
```bash
make celery-worker    # Start worker with auto-reload
make celery-beat       # Start scheduler with auto-reload
make flower            # Start monitoring interface
```

## Auto-Reload Development

The development environment automatically restarts services when you make code changes:

- **Celery Workers**: Restart when Python files change
- **Celery Beat**: Restart when Python files change
- **Web Server**: Restart when Python files change
- **File Watching**: Monitors `src/hnfm/` directory tree

## Docker Services

- **Web Server**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Flower Monitoring**: http://localhost:5555
- **Redis**: Message broker and cache

## Environment Setup

Copy and configure environment variables:

```bash
cp env.example .env
# Edit .env with your API keys and service URLs
```

Required services:
- TTS Service (for text-to-speech)
- Studio Voice (for audio enhancement)
- Local LLM (for content processing)
- Firecrawl (for web scraping)

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

## Testing

```bash
# Run all tests
make test

# Specific test suites
make test-pipeline
make test-api
make test-integration
```

## Code Formatting

This project uses Black for consistent Python formatting:

```bash
make black          # Format all code
make black-check    # Check without changes
```

## Troubleshooting

### Common Issues

1. **Services won't start**: Check Docker is running and ports are available
2. **Auto-reload not working**: Ensure source code is mounted as volumes in Docker
3. **Tests failing**: Verify all required services are running

### Debug Mode

Enable detailed logging:

```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

## Next Steps

- See [API Documentation](OPENAPI_DOCUMENTATION.md) for endpoint details
- Check [Content Structure](CONTENT_STRUCTURE_README.md) for pipeline details
- Review [TTS Pipeline](TTS_PIPELINE_README.md) for audio generation
