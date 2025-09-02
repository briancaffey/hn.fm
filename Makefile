.PHONY: help black black-check lint-frontend lint-frontend-fix clean clean-cache clean-pycache test test-cov test-cov-html docker-up docker-down docker-logs docker-shell

# Default target
help:
	@echo "hn.fm Development Commands"
	@echo "========================"
	@echo ""
	@echo "Code Formatting:"
	@echo "  black        - Format all Python code with Black"
	@echo "  black-check  - Check code formatting without making changes"
	@echo "  lint-frontend - Lint frontend code with ESLint"
	@echo "  lint-frontend-fix - Fix frontend linting issues automatically"
	@echo ""
	@echo "Cleaning:"
	@echo "  clean        - Remove all generated files and caches"
	@echo "  clean-cache  - Remove pipeline cache files"
	@echo "  clean-pycache - Remove Python cache directories"
	@echo ""
	@echo "Testing:"
	@echo "  test         - Run all tests"
	@echo "  test-cov     - Run tests with coverage report"
	@echo "  test-cov-html - Run tests and generate HTML coverage report"
	@echo ""
	@echo "Docker Services:"
	@echo "  docker-up    - Start all services with hot reloading"
	@echo "  docker-down  - Stop all services"
	@echo "  docker-logs  - View logs for all services"
	@echo "  docker-shell - Open shell in web container"
	@echo ""
	@echo "Use 'make <command>' to run a specific command"

# Code formatting with Black
black:
	@echo "🎨 Formatting code with Black..."
	docker compose run --rm web black . --line-length 88 --exclude .venv
	@echo "✅ Code formatting complete!"

# Check code formatting without making changes
black-check:
	@echo "🔍 Checking code formatting with Black..."
	docker compose run --rm web black . --line-length 88 --exclude .venv --check
	@echo "✅ Code formatting check complete!"

# Lint frontend code
lint-frontend:
	@echo "🔍 Linting frontend code with ESLint..."
	cd frontend && yarn lint
	@echo "✅ Frontend linting complete!"

# Fix frontend linting issues
lint-frontend-fix:
	@echo "🔧 Fixing frontend linting issues..."
	cd frontend && yarn lint:fix
	@echo "✅ Frontend linting fixes complete!"

# Clean all generated files and caches
clean: clean-cache
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

# Run all tests
test:
	@echo "🧪 Running all tests..."
	docker compose run --rm web pytest src/hnfm/test/ -v
	@echo "✅ Tests complete!"

# Test coverage commands
test-cov:
	@echo "🧪 Running tests with coverage report..."
	docker compose run --rm web pytest src/hnfm/test/ --cov=src/hnfm --cov-report=term-missing -v
	@echo "✅ Coverage test complete!"

test-cov-html:
	@echo "🧪 Running tests with HTML coverage report..."
	docker compose run --rm web pytest src/hnfm/test/ --cov=src/hnfm --cov-report=html --cov-report=term-missing -v
	@echo "✅ HTML coverage report generated in htmlcov/"
	@echo "📊 Open htmlcov/index.html in your browser to view the report"



# Docker commands
docker-up:
	@echo "🐳 Starting services with hot reloading..."
	docker compose up -d
	@echo "✅ Services started!"
	@echo "Web server: http://localhost:8000"
	@echo "API docs: http://localhost:8000/docs"
	@echo "Flower monitoring: http://localhost:5555"

docker-down:
	@echo "🐳 Stopping all services..."
	docker compose down
	@echo "✅ Services stopped!"

docker-logs:
	@echo "🐳 Showing logs for all services..."
	docker compose logs -f

docker-shell:
	@echo "🐳 Opening shell in web container..."
	docker compose exec web bash
