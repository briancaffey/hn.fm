# Simple Test Suite for hn.fm

This is a simplified test suite with just 3 core test files for easy debugging and maintenance.

## 🧪 Test Structure

### Core Test Files

1. **`test_pipeline.py`** - Core pipeline functionality
   - HN scraping
   - Content scraping with Firecrawl
   - Content processing and cleaning
   - Script generation
   - Full pipeline integration

2. **`test_api.py`** - API endpoints and web server
   - Database connection and operations
   - Content storage and retrieval
   - Celery task configuration
   - Pydantic models
   - Task execution

3. **`test_integration.py`** - End-to-end workflows
   - Configuration loading
   - System health checks
   - Content lifecycle management
   - Error handling
   - Performance metrics
   - Frontend integration points

## 🚀 How to Run Tests

### Prerequisites
```bash
# Start Redis (if needed for database tests)
docker-compose up redis -d
```

### Running Tests

#### Using Docker Compose (Recommended)
```bash
# Run all tests
make test

# Run specific test files
make test-pipeline
make test-api
make test-integration

# Or use docker-compose directly
docker-compose run --rm web pytest src/hnfm/test/ -v
docker-compose run --rm web pytest src/hnfm/test/test_pipeline.py -v
```

#### Using pytest directly (if running locally)
```bash
# Run all tests
pytest src/hnfm/test/ -v

# Run specific test file
pytest src/hnfm/test/test_pipeline.py -v
pytest src/hnfm/test/test_api.py -v
pytest src/hnfm/test/test_integration.py -v

# Run specific test class
pytest src/hnfm/test/test_pipeline.py::TestPipeline -v

# Run specific test method
pytest src/hnfm/test/test_pipeline.py::TestPipeline::test_hn_utils -v
```

## 📊 Test Results

Tests provide clear output with:
- ✅ Success indicators
- ❌ Failure indicators
- 📊 Summary statistics
- 🎉 Overall pass/fail status

## 🔧 Debugging

### Common Issues

1. **Import Errors**
   ```bash
   # Make sure you're in the project root
   cd /path/to/hn.fm
   ```

2. **Redis Connection**
   ```bash
   # Start Redis
   docker-compose up redis -d
   ```

3. **Missing Dependencies**
   ```bash
   # Install dev dependencies
   uv sync --group dev
   ```

### Debugging Individual Tests

```bash
# Run with more verbose output
uv run pytest src/hnfm/test/test_pipeline.py -v -s

# Run with coverage
uv run pytest src/hnfm/test/test_pipeline.py --cov=hnfm.pipeline

# Run with debugger
uv run python -m pdb src/hnfm/test/test_pipeline.py
```

## 🎯 Test Philosophy

- **Simple**: Easy to understand and debug
- **Fast**: Quick feedback loop
- **Reliable**: Consistent results
- **Comprehensive**: Covers all major functionality
- **Maintainable**: Easy to modify and extend

## 📝 Adding New Tests

When adding new tests:

1. **Choose the right file**:
   - Pipeline functionality → `test_pipeline.py`
   - API/web server → `test_api.py`
   - End-to-end workflows → `test_integration.py`

2. **Follow the pattern**:
   ```python
   def test_your_functionality(self):
       """Test description"""
       print("🧪 Testing Your Functionality...")

       try:
           # Your test logic here
           assert condition, "Assertion message"
           print("✅ Test passed")
           return True
       except Exception as e:
           print(f"❌ Test failed: {e}")
           return False
   ```

3. **Add to the test runner**:
   - Add your test method to the appropriate test class
   - Update the `run_*_tests()` function to include your test

## 🚀 Quick Start

```bash
# Quick test run
make test

# Or run specific tests
make test-pipeline
make test-api
make test-integration
```

That's it! Simple, fast, and easy to debug. 🎉
