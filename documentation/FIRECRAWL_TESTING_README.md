# 🔥 Firecrawl Testing Guide

This guide explains how to test Firecrawl integration with hn.fm using local HTML files for faster, more reliable testing.

## 🎯 Why Test with Local HTML?

Testing with local HTML files provides several advantages:

- **Faster Testing**: No need to wait for external websites to load
- **Reliable Content**: Consistent test data that won't change
- **Offline Development**: Work without internet connectivity
- **Content Control**: Test with specific HTML structures and content
- **Rate Limit Avoidance**: No API limits when testing locally
- **Debugging**: Easier to isolate issues in controlled environment

## 🏗️ Test Setup

### 1. Test HTML File

Your test HTML is located at:
```
src/hnfm/web/static/test_html/test_content.html
```

This file contains Wikipedia content about Large Language Models, which is perfect for testing because:
- It's familiar content you can verify
- It has rich HTML structure (headings, paragraphs, lists)
- It represents real-world content you might encounter
- It's substantial enough to test content processing

### 2. Web Server Configuration

The test HTML is served by your FastAPI backend at:
```
http://localhost:8000/static/test_html/test_content.html
```

This allows Firecrawl to scrape it as if it were a real website.

## 🧪 Running Tests

### Quick Test (Recommended for Development)

```bash
# Start the web server first
uv run python -m src.hnfm.web.server

# In another terminal, run the quick test
uv run python -m src.hnfm.test.test_firecrawl_quick
```

This runs a simple test that:
1. ✅ Verifies web server is running
2. ✅ Tests HTML file accessibility
3. ✅ Tests Firecrawl scraping
4. ✅ Tests content processing
5. ✅ Tests script generation

### Comprehensive Test Suite

```bash
# Run the full pytest suite
uv run pytest src/hnfm/test/test_firecrawl_integration.py -v

# Run specific test methods
uv run pytest src/hnfm/test/test_firecrawl_integration.py::TestFirecrawlIntegration::test_firecrawl_local_html_scraping -v
```

## 📋 Test Coverage

### Core Functionality Tests

| Test | Description | What It Validates |
|------|-------------|-------------------|
| `test_server_availability` | Web server and static file serving | Server is running and serving test HTML |
| `test_firecrawl_local_html_scraping` | Firecrawl scraping of local HTML | Content extraction and parsing |
| `test_content_processing` | Content cleaning and processing | Text cleaning and paragraph extraction |
| `test_script_generation` | Script generation from content | LLM integration and script creation |
| `test_end_to_end_pipeline` | Complete workflow | Full pipeline integration |

### Advanced Tests

| Test | Description | What It Validates |
|------|-------------|-------------------|
| `test_firecrawl_parameters` | Different scraping configurations | Parameter handling and flexibility |
| `test_error_handling` | Error scenarios | Robustness and error reporting |
| `test_performance_benchmarks` | Performance metrics | Pipeline efficiency and timing |

## 🔧 Test Configuration

### Environment Variables

Ensure these are set in your `.env` file:

```bash
# Firecrawl Configuration
FIRECRAWL_API_KEY=local-dev-key  # Any value for local development
FIRECRAWL_BASE_URL=http://localhost:3002

# Web Server Configuration
WEB_HOST=0.0.0.0
WEB_PORT=8000
```

### Test Parameters

The tests use these default parameters:

```python
# Content processing
max_paragraphs=10

# Script generation
max_length=15  # minutes

# Performance thresholds
avg_time_threshold=30  # seconds
min_time_threshold=20  # seconds
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Web Server Not Running
```
❌ Web server not accessible: Connection refused
```
**Solution**: Start the web server:
```bash
uv run python -m src.hnfm.web.server
```

#### 2. Test HTML Not Found
```
❌ Test HTML file not accessible: 404
```
**Solution**: Check that the file exists:
```bash
ls -la src/hnfm/web/static/test_html/test_content.html
```

#### 3. Firecrawl Service Unavailable
```
❌ Scraping failed: Connection refused
```
**Solution**: Start local Firecrawl service:
```bash
cd ~/git/firecrawl
docker compose up -d
```

#### 4. Content Processing Errors
```
❌ Content processing error: [Error details]
```
**Solution**: Check LLM service configuration and ensure services are running.

### Debug Mode

Enable debug logging by setting in your `.env`:
```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

## 📊 Expected Results

### Successful Test Run

```
🚀 Starting Firecrawl Quick Test Suite...

🧪 Testing web server availability...
✅ Web server is running
✅ Test HTML file is accessible
✅ Test HTML contains expected content

🧪 Testing Firecrawl scraping of: http://localhost:8000/static/test_html/test_content.html
✅ Successfully scraped content
   Title: Large language model - Wikipedia
   Content length: 15420 characters
   URL: http://localhost:8000/static/test_html/test_content.html
   Content preview: A large language model (LLM) is a computational model...

🧪 Testing content processing...
✅ Content processing successful
   Cleaned content length: 12345 characters
   Meaningful paragraphs: 15

🧪 Testing script generation...
✅ Script generation successful
   Script length: 2345 characters
   Summary length: 234 characters
   Script preview: [S1] Welcome to today's episode where we explore...
   Summary: An overview of large language models, their capabilities...

✅ All tests completed successfully in 12.34 seconds!

📊 Test Summary:
   - Web server: ✅ Running
   - HTML access: ✅ Accessible
   - Firecrawl scraping: ✅ Success
   - Content processing: ✅ Success
   - Script generation: ✅ Success
   - Total time: 12.34s

🎉 All tests passed! Your Firecrawl integration is working correctly.
```

## 🔄 Updating Test Content

To test with different HTML content:

1. **Replace the test HTML file**:
   ```bash
   # Copy new HTML content
   cp your_new_content.html src/hnfm/web/static/test_html/test_content.html
   ```

2. **Update test assertions** if needed:
   - Modify expected content checks in test files
   - Update content length expectations
   - Adjust keyword searches

3. **Restart the web server** if needed:
   ```bash
   # Stop and restart
   pkill -f "python -m src.hnfm.web.server"
   uv run python -m src.hnfm.web.server
   ```

## 🎯 Next Steps

After successful testing:

1. **Integrate with your pipeline**: Use the tested configuration in production
2. **Add more test cases**: Create tests for different content types
3. **Performance optimization**: Use benchmark results to optimize your pipeline
4. **Error handling**: Implement robust error handling based on test findings

## 📚 Related Documentation

- [DEVELOPMENT.md](DEVELOPMENT.md) - Development setup and Firecrawl configuration
- [README.md](README.md) - Project overview and architecture
- [src/hnfm/test/README.md](src/hnfm/test/README.md) - Complete test suite documentation
