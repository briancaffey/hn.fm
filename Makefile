.PHONY: help black black-check clean clean-cache clean-pycache test install-dev

# Default target
help:
	@echo "hn.fm Development Commands"
	@echo "========================"
	@echo ""
	@echo "Code Formatting:"
	@echo "  black        - Format all Python code with Black"
	@echo "  black-check  - Check code formatting without making changes"
	@echo ""
	@echo "Cleaning:"
	@echo "  clean        - Remove all generated files and caches"
	@echo "  clean-cache  - Remove pipeline cache files"
	@echo "  clean-pycache - Remove Python cache directories"
	@echo ""
	@echo "Development:"
	@echo "  install-dev  - Install development dependencies"
	@echo "  test         - Run tests"
	@echo ""
	@echo "Use 'make <command>' to run a specific command"

# Code formatting with Black
black:
	@echo "🎨 Formatting code with Black..."
	uv run black . --line-length 88 --exclude .venv
	@echo "✅ Code formatting complete!"

# Check code formatting without making changes
black-check:
	@echo "🔍 Checking code formatting with Black..."
	uv run black . --line-length 88 --exclude .venv --check
	@echo "✅ Code formatting check complete!"

# Clean all generated files and caches
clean: clean-cache clean-pycache
	@echo "🧹 Cleaning generated files..."
	rm -rf outputs/
	rm -f *.wav
	rm -f *.mp3
	@echo "✅ Clean complete!"

# Clean pipeline cache files
clean-cache:
	@echo "🗑️  Cleaning pipeline cache..."
	rm -rf cache/
	@echo "✅ Cache cleaned!"

# Clean Python cache directories
clean-pycache:
	@echo "🐍 Cleaning Python cache directories..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	@echo "✅ Python cache cleaned!"

# Install development dependencies
install-dev:
	@echo "📦 Installing development dependencies..."
	uv add --dev black isort flake8 pytest pytest-cov pre-commit
	@echo "✅ Development dependencies installed!"

# Run tests
test:
	@echo "🧪 Running tests..."
	uv run pytest tests/ -v
	@echo "✅ Tests complete!"

# Celery commands
celery-worker:
	@echo "Starting Celery worker..."
	uv run python start_celery_worker.py

celery-beat:
	@echo "Starting Celery Beat..."
	uv run python start_celery_beat.py

flower:
	@echo "Starting Flower monitoring..."
	uv run python start_flower.py

# Test commands
test-celery:
	@echo "Testing Celery setup..."
	uv run python -m src.hnfm.test.test_celery

test-all:
	@echo "Running all tests..."
	@echo "Testing web server..."
	uv run python -m src.hnfm.test.test_web_server
	@echo ""
	@echo "Testing Celery..."
	uv run python -m src.hnfm.test.test_celery
	@echo ""
	@echo "Testing scraper..."
	uv run python -m src.hnfm.test.test_scraper

# Development setup
dev-setup: install-deps
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then cp env.example .env; echo "Created .env file"; fi
	@echo "Starting Redis..."
	docker-compose up redis -d
	@echo "Waiting for Redis to be ready..."
	@sleep 3
	@echo "Testing setup..."
	uv run python -m src.hnfm.test.test_web_server
	@echo "Development environment ready!"
	@echo "Start services with: make dev-start"

dev-start:
	@echo "Starting development services..."
	@echo "Web server: http://localhost:8000"
	@echo "Flower monitoring: http://localhost:5555"
	@echo "Press Ctrl+C to stop all services"
	@trap 'kill 0' SIGINT; \
	uv run python run_web_server.py & \
	uv run python start_celery_worker.py & \
	uv run python start_flower.py & \
	wait

dev-start-background:
	@echo "Starting development services in background..."
	@echo "Starting Redis..."
	docker-compose up redis -d
	@echo "Starting Celery worker..."
	uv run python start_celery_worker.py &
	@echo "Starting web server..."
	uv run python run_web_server.py &
	@echo "Services started in background!"
	@echo "Web server: http://localhost:8000"
	@echo "API docs: http://localhost:8000/docs"
	@echo "Celery Flower: http://localhost:5555"
