# Docker Setup for hn.fm

This document describes how to use Docker to run the hn.fm backend application with all its services.

## Overview

The Docker setup includes:
- **FastAPI Web Server** - Main application server
- **Celery Worker** - Background task processing
- **Celery Beat** - Scheduled task scheduler
- **Redis** - Message broker and result backend
- **Flower** - Celery monitoring interface

## Quick Start

### 1. Environment Setup

Copy the example environment file and configure your settings:

```bash
cp env.example .env
# Edit .env with your API keys and service URLs
```

### 2. Start Development Environment

```bash
# Build and start all services with hot reloading
make dev-docker

# Or manually:
make docker-build
make docker-up-dev
```

### 3. Access Services

- **Web Server**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Flower Monitoring**: http://localhost:5555

## Docker Commands

### Development Commands

```bash
# Start development environment with hot reloading
make dev-docker

# Start production environment
make prod-docker

# Build Docker images
make docker-build

# Build without cache
make docker-build-no-cache
```

### Service Management

```bash
# Start all services
make docker-up

# Stop all services
make docker-down

# Restart all services
make docker-restart

# View service status
make docker-status

# View logs
make docker-logs          # All services
make docker-logs-web      # Web server only
make docker-logs-celery   # Celery worker only
make docker-logs-beat     # Celery Beat only
```

### Container Access

```bash
# Open shell in web container
make docker-shell

# Open shell in Celery worker container
make docker-shell-celery
```

### Cleanup

```bash
# Stop services and remove volumes
make docker-down-volumes

# Clean up Docker resources
make docker-clean
```

## Configuration

### Environment Variables

The Docker setup uses environment variables from your `.env` file. Key variables include:

- **API Keys**: `FIRECRAWL_API_KEY`, `OPENAI_API_KEY`
- **Service URLs**: TTS, ASR, LLM, Image Generation services
- **Redis Configuration**: Host, port, database settings
- **Celery Configuration**: Worker concurrency, timeouts, etc.

### Service Configuration

#### Development (`docker-compose.dev.yml`)
- Hot reloading enabled for FastAPI
- Debug mode enabled
- Source code mounted for live updates
- Development-friendly logging

#### Production (`docker-compose.prod.yml`)
- Optimized resource limits
- Production logging levels
- Enhanced restart policies
- Resource constraints for stability

## Architecture

### Service Dependencies

```
web (FastAPI) → redis
celery-worker → redis
celery-beat → redis
flower → redis
```

### Volume Mounts

- `./src:/app/src` - Source code for development
- `./outputs:/app/outputs` - Generated content
- `./cache:/app/cache` - Pipeline cache
- `redis_data:/data` - Redis persistence

### Networks

All services run on a custom bridge network (`hnfm-network`) for secure inter-service communication.

## Development Workflow

### 1. Code Changes

With the development setup, code changes are automatically detected:
- FastAPI will reload when Python files change
- Celery services will restart when needed

### 2. Adding Dependencies

When adding new dependencies to `pyproject.toml`:

```bash
# Rebuild the image
make docker-build

# Restart services
make docker-restart
```

### 3. Debugging

```bash
# View real-time logs
make docker-logs-web

# Access container shell
make docker-shell

# Check service health
make docker-status
```

## Production Deployment

### 1. Environment Configuration

Ensure your `.env` file has production-appropriate values:
- Set `DEBUG=false`
- Configure production service URLs
- Set appropriate resource limits

### 2. Start Production Services

```bash
make prod-docker
```

### 3. Monitoring

- Use Flower for Celery task monitoring
- Check container health with `make docker-status`
- Monitor logs with `make docker-logs`

## Troubleshooting

### Common Issues

#### Services Won't Start
```bash
# Check service status
make docker-status

# View logs for specific service
make docker-logs-web
```

#### Redis Connection Issues
```bash
# Check Redis health
docker-compose exec redis redis-cli ping

# Restart Redis
docker-compose restart redis
```

#### Celery Worker Issues
```bash
# Check Celery worker status
docker-compose exec celery-worker celery -A src.hnfm.web.celery_app inspect active

# Restart worker
docker-compose restart celery-worker
```

### Performance Issues

#### Memory Usage
```bash
# Check container resource usage
docker stats

# Adjust resource limits in docker-compose.prod.yml
```

#### Slow Response Times
- Check Redis performance
- Monitor Celery worker concurrency
- Review service health checks

## Best Practices

### 1. Development
- Use `make dev-docker` for development
- Mount source code for hot reloading
- Enable debug logging

### 2. Production
- Use `make prod-docker` for production
- Set appropriate resource limits
- Monitor service health
- Regular log rotation

### 3. Security
- Never commit `.env` files
- Use secrets management in production
- Regular security updates
- Network isolation

## File Structure

```
.
├── Dockerfile                 # Main application image
├── docker-compose.yml         # Base service configuration
├── docker-compose.dev.yml     # Development overrides
├── docker-compose.prod.yml    # Production overrides
├── .dockerignore             # Docker build exclusions
├── env.example               # Environment template
└── Makefile                  # Docker commands
```

## Support

For issues with the Docker setup:
1. Check service logs: `make docker-logs`
2. Verify environment configuration
3. Check service dependencies
4. Review Docker documentation
