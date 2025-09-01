# Simple Pipeline System for hn.fm

## Overview

This document describes the simplified pipeline system for hn.fm that provides straightforward content processing without complex locking mechanisms. Perfect for hackathon projects and personal use.

## Architecture Components

### 1. Pipeline Manager (`src/hnfm/pipeline/enhanced_pipeline_manager.py`)

The `PipelineManager` provides simple, direct pipeline execution:

```python
from hnfm.pipeline.enhanced_pipeline_manager import PipelineManager

# Initialize pipeline manager
pipeline = PipelineManager(text_only=True)

# Execute a pipeline step
result = pipeline.execute_step('firecrawl_content', manifest_data)
```

**Features:**
- Simple step execution without locking
- Text-only mode for faster processing
- Direct file-based artifact storage
- Easy to understand and debug

### 2. Content Pipeline Tasks (`src/hnfm/web/enhanced_tasks.py`)

Simple Celery tasks for content processing:

```python
from hnfm.web.enhanced_tasks import content_pipeline

# Queue content processing
task = content_pipeline.delay(content_id, options)
```

**Available Tasks:**
- `content_pipeline`: Basic content processing (text-only)
- `full_pipeline`: Full processing including TTS, images, and video
- `process_content_pipeline`: Legacy pipeline processing

## Pipeline Steps

The simplified pipeline includes the following steps:

| Step | Description | Dependencies |
|------|-------------|-------------|
| `firecrawl_content` | Extract content using Firecrawl | None |
| `content_processing` | Process and clean content | `firecrawl_content` |
| `script_generation` | Generate podcast script with [S1]/[S2] tags | `content_processing` |
| `tts_generation` | Generate TTS audio in batches | `script_generation` |
| `audio_cleaning` | Clean audio using Studio Voice | `tts_generation` |
| `audio_assembly` | Combine all audio into final file | `audio_cleaning` |
| `image_generation` | Generate images for video | `script_generation` |
| `video_generation` | Create final video with audio and images | `audio_assembly`, `image_generation` |

## Usage Examples

### Basic Content Processing

```python
from hnfm.web.enhanced_tasks import content_pipeline

# Queue content for processing
task = content_pipeline.delay(
    content_id="content-123",
    options={
        "priority": "high",
        "voice": "en-US-Standard-A",
        "quality": "high"
    }
)

print(f"Task queued with ID: {task.id}")
```

### Full Pipeline Processing

```python
from hnfm.web.enhanced_tasks import full_pipeline

# Queue full pipeline processing
task = full_pipeline.delay(
    content_id="content-123",
    url="https://example.com/article",
    content_type="article"
)

print(f"Full pipeline task queued with ID: {task.id}")
```

### Direct Pipeline Execution

```python
from hnfm.pipeline.enhanced_pipeline_manager import PipelineManager

# Initialize pipeline manager
pipeline = PipelineManager(text_only=True)

# Execute a specific step
result = pipeline.execute_step(
    "firecrawl_content",
    {
        "selected_article": {
            "url": "https://example.com/article",
            "title": "Example Article",
            "id": "content-123"
        }
    }
)

print(f"Step completed: {result}")
```

## API Endpoints

### Pipeline Endpoints

#### Get Pipeline Status
```http
GET /api/pipeline/status
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "message": "Pipeline system is running without locking"
}
```

## Testing

### Run the Test Suite

```bash
# Run all tests
uv run python src/hnfm/test/test_enhanced_system.py

# Run specific test file
uv run python src/hnfm/test/test_enhanced_tasks.py
```

### Test Coverage

The test suite covers:
- Pipeline manager initialization
- Step execution
- Task registration
- API endpoint functionality

## Configuration

### Environment Variables

```bash
# Redis configuration (for Celery)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Celery configuration
CELERY_ALWAYS_EAGER=false
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Docker Compose

The simplified system works with the existing Docker Compose setup:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  celery-worker:
    build: .
    command: ["celery", "-A", "hnfm.web.celery_app", "worker", "--loglevel=info"]
    volumes:
      - ./src:/app/src
    depends_on:
      - redis
```

## Monitoring and Debugging

### Pipeline Status

Check pipeline system status:

```bash
curl http://localhost:8000/api/pipeline/status
```

### Task Monitoring

Monitor Celery task progress:

```bash
# Check Celery worker status
celery -A hnfm.web.celery_app inspect active

# Check task results
celery -A hnfm.web.celery_app inspect reserved
```

## Migration from Enhanced System

The simplified system is designed to replace the complex enhanced system:

1. **Removed Complexity**: No more service locking or versioning
2. **Direct Execution**: Pipeline steps execute directly without Redis coordination
3. **File-based Storage**: Artifacts are stored directly in the cache directory
4. **Simplified API**: Fewer endpoints and simpler responses

### Key Changes

- Removed `ServiceLockManager` and all locking logic
- Simplified `PipelineManager` without Redis integration
- Streamlined Celery tasks without complex manifest management
- Direct file-based artifact storage instead of Redis

## Performance Considerations

### Simplified Architecture

- **No Lock Overhead**: Direct execution without locking mechanisms
- **File-based Storage**: Simple file system storage for artifacts
- **Reduced Complexity**: Fewer moving parts means fewer failure points

### Resource Usage

- **Memory**: Lower memory usage without Redis caching
- **CPU**: Direct execution without coordination overhead
- **Storage**: Simple file-based storage in cache directory

## Troubleshooting

### Common Issues

#### Task Failures

```bash
# Check Celery worker status
celery -A hnfm.web.celery_app inspect active

# Check task results
celery -A hnfm.web.celery_app inspect reserved
```

#### File Permissions

```bash
# Ensure cache directory is writable
chmod 755 cache/
```

#### Redis Connection Issues

```bash
# Check Redis health
redis-cli ping

# Check Redis memory usage
redis-cli info memory
```

### Logs

Enable debug logging for troubleshooting:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run with verbose logging
uv run python run_web_server.py --log-level debug
```

## Conclusion

The simplified pipeline system provides a clean, straightforward approach to content processing that's perfect for hackathon projects and personal use. By removing the complexity of service locking and Redis-based coordination, the system is easier to understand, debug, and maintain while still providing all the essential functionality for content processing.
