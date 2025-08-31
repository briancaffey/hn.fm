# Enhanced Celery Task System - Redis-First Architecture

## Overview

This document describes the enhanced Celery task system for hn.fm that implements a Redis-first, single-host architecture with per-service concurrency control, versioned artifacts, and robust orchestration.

## Architecture Components

### 1. Service Lock Manager (`src/hnfm/web/locks.py`)

The `ServiceLockManager` provides Redis-based locking for external services to ensure single concurrency:

```python
from hnfm.web.locks import ServiceLockManager

# Initialize with Redis client
lock_manager = ServiceLockManager(redis_client)

# Use service lock
with lock_manager.service_lock('tts', timeout=300):
    # Only one request can use TTS service at a time
    result = tts_service.generate_audio(script)
```

**Features:**
- Automatic lock timeout and cleanup
- Stale lock detection and recovery
- Force release capability for emergency situations
- Comprehensive logging and monitoring

### 2. Redis Repository (`src/hnfm/web/redis_repo.py`)

The `RedisRepository` provides enhanced Redis operations with versioning and manifest management:

```python
from hnfm.web.redis_repo import RedisRepository

repo = RedisRepository()

# Create or retrieve processing manifest
manifest = repo.get_or_create_manifest(content_id, options)

# Create versioned segment for pipeline step
segment = repo.create_segment(content_id, 'firecrawl_content')

# Complete segment with results
repo.complete_segment(segment.segment_id, {
    'artifacts': {'raw_content': '...'},
    'metadata': {'content_length': 1234}
})
```

**Features:**
- Versioned segment tracking
- Processing manifest management
- Artifact and metadata storage
- Automatic dependency resolution

### 3. Enhanced Tasks (`src/hnfm/web/enhanced_tasks.py`)

Enhanced Celery tasks that integrate with the Redis-first architecture:

```python
from hnfm.web.enhanced_tasks import enhanced_content_pipeline

# Queue enhanced pipeline processing
task = enhanced_content_pipeline.delay(content_id, options)
```

**Available Tasks:**
- `enhanced_content_pipeline`: Full content processing with locking
- `retry_failed_segment`: Retry failed pipeline steps
- `get_enhanced_pipeline_status`: Get detailed pipeline status
- `cleanup_completed_segments`: Clean up old versions

### 4. Enhanced Pipeline Manager (`src/hnfm/pipeline/enhanced_pipeline_manager.py`)

Enhanced pipeline manager with Redis integration and service locking:

```python
from hnfm.pipeline.enhanced_pipeline_manager import EnhancedPipelineManager

pipeline = EnhancedPipelineManager(redis_integration=True)

# Execute step with service locking
result = pipeline.execute_step_with_locking('firecrawl_content', manifest_data)
```

**Features:**
- Service-level locking for pipeline steps
- Redis integration for state management
- Step retry and recovery capabilities
- Comprehensive monitoring and status tracking

## API Endpoints

### Enhanced Pipeline Endpoints

#### Process Content
```http
POST /api/enhanced-pipeline/process
Content-Type: application/json

{
  "url": "https://example.com/article",
  "content_type": "article",
  "options": {
    "priority": "high",
    "voice": "en-US-Standard-A"
  }
}
```

#### Get Pipeline Status
```http
GET /api/enhanced-pipeline/status/{content_id}
```

#### Retry Failed Step
```http
POST /api/enhanced-pipeline/retry/{content_id}/{step_name}
```

#### Cleanup Old Versions
```http
POST /api/enhanced-pipeline/cleanup/{content_id}?keep_versions=2
```

#### Service Lock Status
```http
GET /api/enhanced-pipeline/service-locks
```

#### Force Release Lock
```http
POST /api/enhanced-pipeline/force-release-lock/{service_name}
```

## Redis Key Schema

The enhanced system uses a structured Redis key schema:

```
# Content management
hnfm:content:{content_id}                    # Content item data
hnfm:content_list:all                        # Content listing
hnfm:metadata:{content_id}                   # Content metadata

# Enhanced pipeline tracking
hnfm:manifest:{content_id}                   # Processing manifest
hnfm:segments:{content_id}:{step_name}       # Step segments
hnfm:segment_versions:{content_id}:{step_name} # Version counters

# Service locks
hnfm:lock:{service_name}                     # Service locks

# Processing state
hnfm:queue:processing                        # Processing queue
hnfm:queue:completed                         # Completed queue
hnfm:queue:failed                           # Failed queue

# Artifact tracking
hnfm:artifacts:{content_id}:{step_name}     # Step artifacts
hnfm:artifact_versions:{content_id}:{step_name} # Artifact versions
```

## Pipeline Steps

The enhanced pipeline includes the following steps with service locking:

| Step | Service | Lock Timeout | Dependencies |
|------|---------|--------------|--------------|
| `firecrawl_content` | `firecrawl` | 300s | None |
| `content_processing` | `llm` | 600s | `firecrawl_content` |
| `script_generation` | `llm` | 600s | `content_processing` |
| `tts_generation` | `tts` | 1800s | `script_generation` |
| `image_generation` | `vision` | 1200s | `script_generation` |
| `video_generation` | `video` | 1800s | `tts_generation`, `image_generation` |

## Usage Examples

### Basic Content Processing

```python
from hnfm.web.enhanced_tasks import enhanced_content_pipeline

# Queue content for processing
task = enhanced_content_pipeline.delay(
    content_id="content-123",
    options={
        "priority": "high",
        "voice": "en-US-Standard-A",
        "quality": "high"
    }
)

print(f"Task queued with ID: {task.id}")
```

### Monitoring Pipeline Progress

```python
from hnfm.web.redis_repo import RedisRepository

repo = RedisRepository()

# Get enhanced pipeline status
status = repo.get_enhanced_pipeline_status("content-123")

print(f"Overall status: {status.overall_status}")
print(f"Progress: {status.progress_percentage}%")
print(f"Current step: {status.current_step}")

for step_status in status.step_statuses:
    print(f"{step_status.step_name}: {step_status.status}")
```

### Retrying Failed Steps

```python
from hnfm.web.enhanced_tasks import retry_failed_segment

# Retry a failed segment
task = retry_failed_segment.delay("failed-segment-123")
result = task.get()

print(f"New segment created: {result['new_segment_id']}")
```

## Testing

### Run the Test Suite

```bash
# Run all tests
uv run python test_enhanced_system.py

# Run specific test file
uv run pytest src/hnfm/test/test_enhanced_tasks.py -v
```

### Test Coverage

The test suite covers:
- Service lock acquisition and release
- Segment versioning and persistence
- Manifest management
- Pipeline step execution
- Redis integration
- Celery task registration

## Configuration

### Environment Variables

```bash
# Redis configuration
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

The enhanced system works with the existing Docker Compose setup:

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

### Service Lock Status

Check which services are currently locked:

```bash
curl http://localhost:8000/api/enhanced-pipeline/service-locks
```

### Force Release Locks

In emergency situations, force release a stuck lock:

```bash
curl -X POST http://localhost:8000/api/enhanced-pipeline/force-release-lock/tts
```

### Pipeline Status

Monitor pipeline progress:

```bash
curl http://localhost:8000/api/enhanced-pipeline/status/{content_id}
```

## Migration from Existing System

The enhanced system is designed to work alongside the existing system:

1. **Gradual Rollout**: Use feature flags to enable enhanced processing
2. **Backward Compatibility**: Existing tasks continue to work
3. **Data Migration**: Existing content can be processed through enhanced pipeline
4. **Rollback Plan**: Easy rollback to previous system if needed

### Feature Flags

```python
# Enable enhanced processing
ENHANCED_PIPELINE_ENABLED=true

# Use enhanced pipeline for new content
if os.getenv('ENHANCED_PIPELINE_ENABLED', 'false').lower() == 'true':
    task = enhanced_content_pipeline.delay(content_id, options)
else:
    task = process_content_pipeline.delay(content_id)
```

## Performance Considerations

### Redis Performance

- **Connection Pooling**: Redis connections are pooled and reused
- **Key Expiration**: Locks automatically expire to prevent deadlocks
- **Batch Operations**: Multiple Redis operations are batched where possible

### Lock Timeouts

Service lock timeouts are configured based on expected processing time:

- **Fast Services** (firecrawl, content_processing): 300-600s
- **Medium Services** (tts, image_generation): 1200-1800s
- **Slow Services** (video_generation): 1800s

### Memory Usage

- **Segment Storage**: Old segments are automatically cleaned up
- **Manifest Size**: Manifests are kept minimal with lazy loading
- **Artifact References**: Only file paths are stored, not content

## Troubleshooting

### Common Issues

#### Service Lock Timeouts

```bash
# Check lock status
curl http://localhost:8000/api/enhanced-pipeline/service-locks

# Force release if needed
curl -X POST http://localhost:8000/api/enhanced-pipeline/force-release-lock/{service_name}
```

#### Redis Connection Issues

```bash
# Check Redis health
redis-cli ping

# Check Redis memory usage
redis-cli info memory
```

#### Task Failures

```bash
# Check Celery worker status
celery -A hnfm.web.celery_app inspect active

# Check task results
celery -A hnfm.web.celery_app inspect reserved
```

### Logs

Enable debug logging for troubleshooting:

```bash
export LOG_LEVEL=DEBUG
export CELERY_LOG_LEVEL=DEBUG
```

## Future Enhancements

### Planned Features

1. **Distributed Locking**: Support for multi-host deployments
2. **Advanced Retry Logic**: Exponential backoff and circuit breakers
3. **Metrics and Alerting**: Prometheus integration and alerting
4. **Workflow Engine**: Complex pipeline orchestration
5. **Resource Management**: CPU and memory limits per service

### Contributing

To contribute to the enhanced system:

1. Follow the existing code style and patterns
2. Add comprehensive tests for new functionality
3. Update documentation for new features
4. Ensure backward compatibility
5. Test with the existing pipeline

## Support

For questions or issues with the enhanced system:

1. Check the troubleshooting section above
2. Review the test suite for examples
3. Check Redis and Celery logs
4. Use the monitoring endpoints for debugging
5. Create an issue with detailed error information
