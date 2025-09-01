# Firecrawl Testing

Test web scraping functionality with local HTML files.

## Quick Start

```bash
# Test with local HTML file
uv run python test_firecrawl_local.py test.html

# Test with multiple files
uv run python test_firecrawl_local.py *.html
```

## Local Testing

Create test HTML files to avoid external API calls:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Test Article</title>
</head>
<body>
    <article>
        <h1>Test Article Title</h1>
        <p>This is test content for Firecrawl testing.</p>
    </article>
</body>
</html>
```

## Configuration

Set environment variables:

```bash
FIRECRAWL_BASE_URL=http://localhost:3002
FIRECRAWL_API_KEY=local-dev-key
```

## Testing Commands

```bash
# Test single file
uv run python test_firecrawl_local.py test.html

# Test with custom output
uv run python test_firecrawl_local.py test.html --output-dir custom_outputs

# Test with verbose logging
uv run python test_firecrawl_local.py test.html --verbose
```

## Output

Test results are saved to:
```
outputs/
  test_article/
    content.txt
    metadata.json
```

## Troubleshooting

- **Service unavailable**: Check Firecrawl service is running
- **File not found**: Ensure HTML file exists and is readable
- **Parse errors**: Check HTML structure and content
