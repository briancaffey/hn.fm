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
