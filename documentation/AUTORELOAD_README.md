# Auto-Reload Development Setup

This document describes the auto-reload functionality for Celery workers and beat in the hn.fm development environment.

## Overview

The auto-reload system automatically restarts Celery workers and beat processes when Python code changes are detected, making development much more efficient by eliminating the need to manually restart services.

## Auto-Reload Scripts

### `start_celery_worker_autoreload.py`
- **Purpose**: Starts a Celery worker with automatic reloading on code changes
- **Features**:
  - Watches for changes in Python files in the `src/hnfm` directory tree
  - Automatically kills and restarts the worker process when changes are detected
  - Provides detailed logging of restart events
  - Graceful shutdown with Ctrl+C

### `start_celery_beat_autoreload.py`
- **Purpose**: Starts Celery Beat with automatic reloading on code changes
- **Features**:
  - Watches for changes in Python files in the `src/hnfm` directory tree
  - Automatically kills and restarts the beat process when changes are detected
  - Manages PID files for proper process tracking
  - Provides detailed logging of restart events
  - Graceful shutdown with Ctrl+C

## Usage

### Local Development

```bash
# Start worker with auto-reload
make celery-worker

# Start beat with auto-reload
make celery-beat

# Start all services with auto-reload
make dev-start

# Start services in background with auto-reload
make dev-start-background
```

### Docker Development

```bash
# Start all services in Docker with auto-reload
make dev-docker

# Or use the individual Docker commands
make docker-up      # Start development services
make docker-down    # Stop all services
make docker-logs    # View logs
make docker-status  # Check service status
```

### Simple Mode (No Auto-Reload)

If you need to run without auto-reload for debugging:

```bash
# Start worker without auto-reload
make celery-worker-simple

# Start beat without auto-reload
make celery-beat-simple
```

## How It Works

### File Watching
The auto-reload scripts monitor the following directories for changes:
- `src/hnfm/`
- `src/hnfm/web/`
- `src/hnfm/content/`
- `src/hnfm/audio/`
- `src/hnfm/video/`
- `src/hnfm/scraper/`

### Process Management
1. **Initial Start**: The script starts the Celery process normally
2. **File Monitoring**: A background thread continuously checks file modification times
3. **Change Detection**: When a Python file is modified, the script detects the change
4. **Process Restart**: The script kills the existing process and starts a new one
5. **Logging**: All restart events are logged with timestamps and file information

### Docker Integration
In Docker mode, the auto-reload scripts run inside containers with:
- Source code mounted as volumes for live editing
- Environment variables configured for development
- Health checks to ensure services are running properly

## Configuration

### Environment Variables
The auto-reload scripts use the same environment variables as the regular Celery processes:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Development Settings
DEBUG=true
LOG_LEVEL=DEBUG
CELERY_WORKER_CONCURRENCY=2
```

### PID Files
- Worker PID file: `/tmp/celery_worker.pid`
- Beat PID file: `/tmp/celerybeat.pid` (configurable via `PIDFILE` env var)

## Troubleshooting

### Common Issues

1. **Process not restarting**
   - Check if the process is being killed properly
   - Verify file permissions on the auto-reload scripts
   - Check logs for error messages

2. **Too frequent restarts**
   - The scripts check for changes every second
   - If you're making many rapid changes, consider batching them

3. **Docker container issues**
   - Ensure source code is properly mounted as volumes
   - Check container logs: `make docker-logs-celery`
   - Verify network connectivity between services

### Debug Mode
To see more detailed logging, set the `DEBUG` environment variable:

```bash
DEBUG=true make celery-worker
```

### Manual Restart
If auto-reload isn't working, you can manually restart:

```bash
# Kill all Celery processes
pkill -f celery

# Start manually
make celery-worker-simple
```

## Performance Considerations

- **File Watching**: The scripts check file modification times every second
- **Process Restart**: Each restart takes a few seconds
- **Memory Usage**: Auto-reload adds minimal overhead
- **CPU Usage**: File watching uses negligible CPU

## Best Practices

1. **Save Files**: Make sure to save your files completely before expecting a restart
2. **Batch Changes**: Group related changes to minimize restart frequency
3. **Monitor Logs**: Keep an eye on the logs to ensure restarts are working
4. **Test Changes**: Always test your changes after a restart to ensure they work

## Migration from Old Setup

The old setup used separate scripts without auto-reload. The new setup:

- **Replaces**: `start_celery_worker.py` and `start_celery_beat.py` for development
- **Keeps**: The old scripts as `celery-worker-simple` and `celery-beat-simple`
- **Updates**: All Makefile commands to use auto-reload by default
- **Simplifies**: Docker setup to focus on development with hot reloading

## Future Enhancements

Potential improvements to consider:
- Configurable file watching intervals
- Selective file watching (ignore certain files/directories)
- Integration with IDE file watchers
- Performance optimizations for large codebases
- Better error handling and recovery
