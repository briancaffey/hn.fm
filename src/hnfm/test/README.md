# hn.fm Test Suite

This directory contains all the test files for the hn.fm project. The tests are organized by functionality and can be run individually or as a suite.

## 🧪 Test Overview

### Web Interface Tests
- **`test_web_server.py`** - Tests the FastAPI web server, Redis database, and Pydantic models
- **`test_celery.py`** - Tests Celery task queue setup, task execution, and monitoring

### Pipeline Tests
- **`test_full_pipeline.py`** - Tests the complete content processing pipeline
- **`test_text_only_pipeline.py`** - Tests text-only content processing
- **`test_pipeline_with_images.py`** - Tests pipeline with image generation
- **`test_scraper.py`** - Tests content scraping functionality
- **`test_firecrawl_integration.py`** - Comprehensive Firecrawl integration tests
- **`test_firecrawl_quick.py`** - Quick Firecrawl functionality tests

### Service Tests
- **`test_config.py`** - Tests configuration management and loading
- **`test_asr_with_audio.py`** - Tests ASR (Automatic Speech Recognition) with audio files
- **`test_asr_error_details.py`** - Tests ASR error handling and detailed error reporting
- **`test_asr_timeout.py`** - Tests ASR timeout handling
- **`test_tts_timeout.py`** - Tests TTS (Text-to-Speech) timeout handling
- **`test_image_generation.py`** - Tests image generation service
- **`test_video_generation.py`** - Tests video generation functionality

## 🚀 How to Run Tests

### Prerequisites
1. **Redis running**: `docker-compose up redis -d`
2. **Dependencies installed**: `uv sync`
3. **Environment configured**: Copy `env.example` to `.env` and update as needed
4. **Web server running**: For Firecrawl tests, start the web server with `uv run python -m src.hnfm.web.server`
5. **Test HTML available**: Ensure `src/hnfm/web/static/test_html/test_content.html` contains test content

### Running Individual Tests

#### Web Server Tests
```bash
# Test web server setup
uv run python -m src.hnfm.test.test_web_server

# Test Celery setup
uv run python -m src.hnfm.test.test_celery
```

#### Pipeline Tests
```bash
# Test full pipeline
uv run python -m src.hnfm.test.test_full_pipeline

# Test text-only pipeline
uv run python -m src.hnfm.test.test_text_only_pipeline

# Test pipeline with images
uv run python -m src.hnfm.test.test_pipeline_with_images
```

#### Service Tests
```bash
# Test configuration
uv run python -m src.hnfm.test.test_config

# Test ASR services
uv run python -m src.hnfm.test.test_asr_with_audio
uv run python -m src.hnfm.test.test_asr_error_details
uv run python -m src.hnfm.test.test_asr_timeout

# Test TTS services
uv run python -m src.hnfm.test.test_tts_timeout

# Test image generation
uv run python -m src.hnfm.test.test_image_generation

# Test video generation
uv run python -m src.hnfm.test.test_video_generation

# Test scraper
uv run python -m src.hnfm.test.test_scraper

# Test Firecrawl integration
uv run python -m src.hnfm.test.test_firecrawl_quick
uv run pytest src/hnfm/test/test_firecrawl_integration.py -v
```

### Running All Tests
```bash
# Run all tests (if you have pytest installed)
uv run pytest src/hnfm/test/ -v

# Or run them individually to see detailed output
for test_file in src/hnfm/test/test_*.py; do
    echo "Running $test_file..."
    uv run python -m src.hnfm.test.$(basename $test_file .py)
    echo "---"
done
```

## 📋 Test Categories

### 🔧 **Infrastructure Tests**
These tests verify the basic setup and infrastructure:

- **`test_web_server.py`** - Web server, database, and API functionality
- **`test_celery.py`** - Task queue system and worker management
- **`test_config.py`** - Configuration loading and management

### 🚀 **Pipeline Tests**
These tests verify the content processing pipeline:

- **`test_full_pipeline.py`** - End-to-end content processing
- **`test_text_only_pipeline.py`** - Text processing without media
- **`test_pipeline_with_images.py`** - Pipeline with image generation
- **`test_scraper.py`** - Content scraping and extraction
- **`test_firecrawl_integration.py`** - Firecrawl scraping, content processing, and script generation
- **`test_firecrawl_quick.py`** - Quick Firecrawl functionality validation

### 🎵 **Audio/Video Tests**
These tests verify media processing capabilities:

- **`test_asr_*.py`** - Speech recognition functionality
- **`test_tts_timeout.py`** - Text-to-speech with timeout handling
- **`test_video_generation.py`** - Video creation and processing

### 🔥 **Firecrawl Integration Tests**
These tests verify Firecrawl scraping and content processing:

- **`test_firecrawl_integration.py`** - Comprehensive integration testing with pytest
  - Tests local HTML file scraping
  - Validates content processing pipeline
  - Tests script generation
  - Performance benchmarking
  - Error handling validation
- **`test_firecrawl_quick.py`** - Quick functionality validation
  - Simple test runner for development
  - Step-by-step pipeline validation
  - Useful for debugging and development
- **`test_image_generation.py`** - Image generation and manipulation

## 🐛 Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```bash
   # Start Redis
   docker-compose up redis -d

   # Check Redis status
   redis-cli ping
   ```

2. **Import Errors**
   ```bash
   # Make sure you're in the project root
   cd /path/to/hn.fm

   # Run tests with proper module path
   uv run python -m src.hnfm.test.test_web_server
   ```

3. **Missing Dependencies**
   ```bash
   # Install dependencies
   uv sync

   # Or install specific packages
   uv add pytest pytest-cov
   ```

4. **Environment Variables**
   ```bash
   # Copy and configure environment
   cp env.example .env
   # Edit .env with your configuration
   ```

### Test-Specific Issues

- **ASR Tests**: Require audio files in the test directory
- **Image Tests**: Require image generation service running
- **Video Tests**: Require video processing dependencies
- **Pipeline Tests**: May require external services (OpenAI, etc.)

## 📊 Test Results

### Expected Output
Successful tests should show:
```
✅ Test name passed
🎉 All tests completed successfully
```

Failed tests will show:
```
❌ Test name failed: error details
⚠️ Some tests failed. Check the setup.
```

### Performance Notes
- **Web server tests**: ~2-5 seconds
- **Celery tests**: ~10-30 seconds (depends on worker availability)
- **Pipeline tests**: ~30 seconds to several minutes
- **Service tests**: ~5-15 seconds each

## 🔄 Continuous Integration

For CI/CD pipelines, you can run tests with:
```bash
# Install dependencies
uv sync

# Start Redis
docker-compose up redis -d

# Run tests
uv run python -m src.hnfm.test.test_web_server
uv run python -m src.hnfm.test.test_celery
```

## 📝 Adding New Tests

When adding new tests:

1. **Follow naming convention**: `test_<functionality>.py`
2. **Include docstrings**: Describe what the test verifies
3. **Handle dependencies**: Check for required services
4. **Provide clear output**: Use ✅/❌ indicators
5. **Update this README**: Add new test to the appropriate category

## 🎯 Test Philosophy

- **Fast feedback**: Tests should run quickly and provide clear results
- **Isolated**: Tests should not depend on each other
- **Informative**: Clear error messages and success indicators
- **Comprehensive**: Cover all major functionality
- **Maintainable**: Easy to understand and modify

---

For more information about the project, see the main [README.md](../../../README.md) and [documentation/DEVELOPMENT.md](../../../documentation/DEVELOPMENT.md).
