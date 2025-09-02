# Test Coverage Guide for hn.fm

This guide explains how to use pytest-cov to measure and improve test coverage in the hn.fm project.

## Quick Start

### Basic Coverage Commands

```bash
# Run tests with terminal coverage report
make test-cov

# Run tests with HTML coverage report (recommended)
make test-cov-html

# Show coverage report only (requires previous run)
make coverage-report
```

### Viewing Coverage Results

After running `make test-cov-html`, open `htmlcov/index.html` in your browser to see:
- Overall coverage percentage
- File-by-file coverage breakdown
- Line-by-line coverage details
- Missing lines highlighted

## Current Coverage Status

**Overall Coverage: 23%** (as of latest run)

### Well-Tested Areas (High Coverage)
- **Test files**: 100% coverage (as expected)
- **TTS Service**: 58% coverage
- **Integration tests**: 81% coverage
- **API tests**: 68% coverage

### Areas Needing More Tests (Low Coverage)
- **Scripts**: 0% coverage (command-line scripts)
- **Web API**: 0% coverage (FastAPI endpoints)
- **Audio services**: 11-25% coverage
- **Content processing**: 12-32% coverage
- **Video generation**: 9-40% coverage

## Coverage Configuration

### What's Included
- Source code in `src/hnfm/`
- All Python modules and packages

### What's Excluded
- Test files (`*/test/*`)
- Cache directories (`*/__pycache__/*`, `*/.venv/*`)
- Migration files
- Site packages

### Coverage Thresholds
Currently no minimum coverage threshold is set. Consider adding one as coverage improves.

## Improving Coverage

### Priority Areas for Testing

1. **Web API Endpoints** (0% coverage)
   - FastAPI routes in `src/hnfm/web/api.py`
   - Database operations
   - Redis operations

2. **Core Services** (Low coverage)
   - Audio processing services
   - Content processing pipeline
   - Video generation

3. **Scripts** (0% coverage)
   - Command-line entry points
   - Celery worker scripts

### Testing Strategy

1. **Start with Critical Paths**
   - Focus on main user workflows
   - Test error handling and edge cases

2. **Mock External Dependencies**
   - API calls (image generation, TTS)
   - File system operations
   - Database connections

3. **Integration vs Unit Tests**
   - Unit tests: Mock external dependencies
   - Integration tests: Test real interactions

## Advanced Usage

### Coverage with Specific Tests

```bash
# Test specific module with coverage
docker-compose run --rm web pytest src/hnfm/test/test_api.py --cov=src/hnfm.web --cov-report=html

# Test specific file with coverage
docker-compose run --rm web pytest src/hnfm/test/test_image_generator.py --cov=src/hnfm.video.image_generator --cov-report=term-missing
```

### Docker Integration

Coverage reports are automatically mounted to the host system via Docker volumes:
- HTML reports are generated in `htmlcov/` directory
- Reports persist between container runs
- No need for manual file copying

### Coverage Configuration

The coverage configuration is in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src/hnfm"]
omit = [
    "*/test/*",
    "*/__pycache__/*",
    "*/migrations/*",
    "*/venv/*",
    "*/.venv/*",
    "*/env/*",
    "*/site-packages/*"
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
]
show_missing = true
precision = 2
```

## Best Practices

### Writing Testable Code
- Keep functions small and focused
- Use dependency injection
- Separate business logic from I/O operations

### Coverage Goals
- **Minimum**: 70% overall coverage
- **Target**: 85% overall coverage
- **Critical paths**: 95% coverage

### Excluding Code from Coverage
Use `# pragma: no cover` for code that shouldn't be tested:
```python
def __repr__(self):  # pragma: no cover
    return f"<{self.__class__.__name__}>"
```

## Troubleshooting

### Common Issues

1. **Low coverage on imports**
   - Normal for `__init__.py` files
   - Consider if imports need testing

2. **Scripts showing 0% coverage**
   - Scripts are typically not imported by tests
   - Test the functions they call, not the script itself

3. **External service calls**
   - Always mock external API calls
   - Test the logic around the calls, not the calls themselves

### Coverage Report Issues

If coverage reports seem incorrect:
1. Check the `source` configuration in `pyproject.toml`
2. Verify `omit` patterns are correct
3. Ensure tests are actually importing the code being tested

## Future Enhancements

### Suggested Improvements

1. **Coverage Thresholds**
   ```toml
   [tool.coverage.report]
   fail_under = 70
   ```

2. **Coverage Badges**
   - Add coverage badge to README
   - Integrate with CI/CD pipeline

3. **Coverage Trends**
   - Track coverage over time
   - Set up coverage reporting in CI

4. **Branch Coverage**
   - Enable branch coverage for better analysis
   - Focus on conditional logic testing

5. **Coverage Reports in CI**
   - Generate coverage reports in GitHub Actions
   - Comment coverage changes on PRs

## Resources

- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://docs.python.org/3/library/unittest.html)
