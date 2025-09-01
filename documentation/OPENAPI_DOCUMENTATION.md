# API Documentation

Web API endpoints for hn.fm pipeline management.

## Quick Start

Start the web server:

```bash
make docker-dev
```

Access the API:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Main Endpoints

### Health Check
```http
GET /health
```

### Pipeline Management
```http
POST /pipeline/run
{
  "story_id": "test-story",
  "story_title": "Test Story",
  "start_from": "content_processing"
}
```

### Content Operations
```http
GET /content/{story_id}
POST /content/{story_id}/process
GET /content/{story_id}/script
```

### Audio Operations
```http
POST /audio/{story_id}/generate
GET /audio/{story_id}/status
```

## Models

### PipelineRequest
```json
{
  "story_id": "string",
  "story_title": "string",
  "start_from": "string",
  "dry_run": false
}
```

### ContentResponse
```json
{
  "story_id": "string",
  "title": "string",
  "script": "string",
  "tts_lines": ["string"],
  "status": "string"
}
```

## Authentication

Currently no authentication required for local development.

## Error Handling

Standard HTTP status codes:
- `200` - Success
- `400` - Bad Request
- `404` - Not Found
- `500` - Internal Server Error

## Testing

Test the API:

```bash
# Run API tests
make test-api

# Test specific endpoint
curl http://localhost:8000/health
```
