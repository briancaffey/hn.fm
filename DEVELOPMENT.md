# 🚀 Development Setup Guide

This guide will help you set up the development environment for hn.fm using modern Python tooling.

## 📋 Prerequisites

- **Python 3.9+** installed on your system
- **Git** for version control
- **Docker** for containerized services (required for Firecrawl)

## 🛠️ Development Environment Setup

### 1. Install uv (Python Package Manager)

`uv` is a fast Python package installer and resolver, written in Rust. It's significantly faster than pip and provides better dependency resolution.

#### macOS/Linux
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Windows
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Verify Installation
```bash
uv --version
```

### 2. Project Setup

```bash
# Clone the repository (if not already done)
git clone https://github.com/briancaffey/hn.fm.git
cd hn.fm

# Create a new virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

### 3. Development Dependencies

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Or install specific dev tools
uv pip install pytest pytest-cov black isort flake8 mypy pre-commit
```

### 4. Pre-commit Hooks Setup

```bash
# Install pre-commit hooks
pre-commit install

# Run pre-commit on all files
pre-commit run --all-files
```

## 🔥 Local Firecrawl Setup

For hn.fm development, you'll need to run Firecrawl locally to scrape content from URLs. This section provides complete instructions for self-hosting Firecrawl.

### Why Self-host Firecrawl?

- **Enhanced Security**: Keep all data within your controlled environment
- **Customizable Services**: Tailor scraping services to your specific needs
- **Learning**: Gain deeper understanding of the scraping infrastructure
- **Cost Control**: No API rate limits or usage costs

### Prerequisites for Firecrawl

- **Docker** installed and running
- **Git** for cloning the Firecrawl repository
- **Port 3002** available on your local machine

### Step 1: Clone Firecrawl Repository

```bash
# Clone Firecrawl to a separate directory (not in this repo)
cd ~/git  # or wherever you keep your projects
git clone https://github.com/mendableai/firecrawl.git
cd firecrawl
```

### Step 2: Configure Environment Variables

Create a `.env` file in the Firecrawl root directory:

```bash
# Copy the example environment file
cp apps/api/.env.example .env

# Edit with your configuration
nano .env
```

**Required Environment Variables:**
```bash
# ===== Required ENVS ======
NUM_WORKERS_PER_QUEUE=8
PORT=3002
HOST=0.0.0.0

# Redis configuration for Docker
REDIS_URL=redis://redis:6379
REDIS_RATE_LIMIT_URL=redis://redis:6379
PLAYWRIGHT_MICROSERVICE_URL=http://playwright-service:3000/html

# Disable authentication for local development
USE_DB_AUTHENTICATION=false

# ===== Optional ENVS ======
# Basic logging level
LOGGING_LEVEL=INFO

# Proxy settings (if needed)
# PROXY_SERVER=
# PROXY_USERNAME=
# PROXY_PASSWORD=

# Block media requests to save bandwidth
BLOCK_MEDIA=false
```

### Step 3: Build and Run Firecrawl

```bash
# Build the Docker containers
docker compose build

# Start the services
docker compose up -d

# Check if services are running
docker compose ps
```

### Step 4: Verify Firecrawl is Running

- **API Endpoint**: http://localhost:3002
- **Queue Manager**: http://localhost:3002/admin/@/queues
- **Health Check**: http://localhost:3002/health

### Step 5: Test Firecrawl API

```bash
# Test the scrape endpoint
curl -X POST http://localhost:3002/v0/scrape \
    -H 'Content-Type: application/json' \
    -d '{
      "url": "https://docs.firecrawl.dev",
      "pageOptions": {
        "onlyMainContent": true,
        "includeHtml": false,
        "includeMarkdown": true
      }
    }'
```

### Step 6: Configure hn.fm for Local Firecrawl

Update your `env.example` file or create a `.env` file in the hn.fm project:

```bash
# Firecrawl Configuration
FIRECRAWL_API_KEY=local-dev-key  # Any value for local development
FIRECRAWL_BASE_URL=http://localhost:3002

# Other configuration
HN_USER_AGENT=hn.fm/0.1.0 (briancaffey)
DEBUG=true
LOG_LEVEL=INFO
```

## 🏗️ Project Structure

```
hn.fm/
├── src/
│   └── hnfm/
│       ├── __init__.py
│       ├── scraper/
│       ├── content/
│       ├── audio/
│       ├── video/
│       └── utils/
├── tests/
├── pyproject.toml
├── README.md
├── DEVELOPMENT.md
└── env.example
```

## 🔧 Development Commands

### Code Quality
```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/
mypy src/

# Run tests
pytest
pytest --cov=src/ --cov-report=html
```

### Package Management
```bash
# Add new dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Update dependencies
uv lock --upgrade
```

## 🌍 Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example environment file
cp env.example .env

# Edit with your configuration
nano .env
```

Required environment variables:
- `FIRECRAWL_API_KEY`: Your Firecrawl API key (or any value for local dev)
- `FIRECRAWL_BASE_URL`: http://localhost:3002 for local Firecrawl
- `OPENAI_API_KEY`: OpenAI API key (if using cloud models)
- `HN_USER_AGENT`: User agent for HN scraping

## 🐳 Docker Development (Optional)

```bash
# Build development container
docker build -f Dockerfile.dev -t hnfm-dev .

# Run development container
docker run -it --rm -v $(pwd):/app hnfm-dev

# Or use docker-compose for full stack
docker-compose -f docker-compose.dev.yml up
```

## 📝 Development Workflow

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/url-scraping
   ```

2. **Make Changes**
   - Write code in `src/hnfm/`
   - Add tests in `tests/`
   - Update documentation

3. **Quality Checks**
   ```bash
   pre-commit run --all-files
   pytest
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: implement URL scraping with Firecrawl"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/url-scraping
   # Create PR on GitHub
   ```

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/ --cov-report=html

# Run specific test file
pytest tests/test_scraper.py

# Run tests in parallel
pytest -n auto
```

### Test Structure
- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows

## 📚 Documentation

### Code Documentation
- Use Google-style docstrings
- Include type hints for all functions
- Document complex algorithms and business logic

### API Documentation
- Use FastAPI for web endpoints (if applicable)
- Generate OpenAPI specs automatically
- Include usage examples

## 🔍 Debugging

### VS Code Configuration
Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}"
        }
    ]
}
```

### Logging
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

## 🚨 Common Issues

### uv Installation Issues
- Ensure you have the latest version of Python
- On macOS, you might need to install Xcode command line tools
- On Windows, ensure PowerShell execution policy allows scripts

### Virtual Environment Issues
- Always activate the virtual environment: `source .venv/bin/activate`
- If dependencies are missing, run `uv pip install -e .`
- Check Python version: `python --version`

### Import Issues
- Ensure you're in the project root directory
- Check that `src/` is in your Python path
- Verify `pyproject.toml` configuration

### Firecrawl Issues

#### Docker containers fail to start
```bash
# Check container logs
docker logs firecrawl-api-1
docker logs firecrawl-redis-1

# Ensure all required environment variables are set
# Verify Docker services are running
docker compose ps
```

#### Connection issues with Redis
- Ensure Redis service is running: `docker compose ps redis`
- Verify REDIS_URL in .env points to `redis://redis:6379`
- Check network settings and firewall rules

#### API endpoint does not respond
- Verify Firecrawl is running: `docker compose ps`
- Check PORT and HOST settings in .env
- Ensure port 3002 is not used by other services

#### Supabase client errors
- These are expected in self-hosted instances
- Set `USE_DB_AUTHENTICATION=false` in .env
- Authentication bypass warnings are normal for local development

## 📞 Getting Help

- **GitHub Issues**: Create an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check this file and README.md first
- **Firecrawl Discord**: [Join the community](https://discord.gg/gSmWdAkdwd)

---

**Happy coding! 🎉**
