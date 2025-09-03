# hn.fm Test Suite

This directory contains tests for the core inference services of the hn.fm project. The test suite has been simplified to focus on the essential services.

## 🧪 Test Overview

### Core Service Tests
- **`test_pipeline.py`** - Tests individual pipeline components (HN scraper, content scraper, content processor, script generator)
- **`test_tts_service.py`** - Tests TTS (Text-to-Speech) service functionality
- **`test_image_generator.py`** - Tests image generation service
- **`test_script_generator.py`** - Tests script generation functionality
- **`test_datetime_serialization.py`** - Tests datetime serialization utilities

### Removed Tests
The following tests were removed as part of the codebase simplification:
- Complex pipeline integration tests
- Web API tests (for deleted web components)
- Database integration tests (for deleted database components)

## 🚀 How to Run Tests

### Prerequisites
1. **Dependencies installed**: `uv sync`
2. **Environment configured**: Copy `env.example` to `.env` and update as needed

### Running Individual Tests

#### Core Service Tests
```bash
# Test individual pipeline components
uv run python -m src.hnfm.test.test_pipeline

# Test TTS service
uv run python -m src.hnfm.test.test_tts_service

# Test image generation
uv run python -m src.hnfm.test.test_image_generator

# Test script generation
uv run python -m src.hnfm.test.test_script_generator

# Test datetime utilities
uv run python -m src.hnfm.test.test_datetime_serialization
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
