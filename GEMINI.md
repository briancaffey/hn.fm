# Gemini Project Guidelines: hn.fm

This document provides guidelines for the AI assistant to effectively contribute to the `hn.fm` project.

## Project Overview

`hn.fm` is a Python-based service to generate audio/video content, likely from sources like Hacker News. It uses FastAPI for the web server, Celery for background tasks, and is fully containerized with Docker.

## Tech Stack

*   **Language:** Python
*   **Framework:** FastAPI
*   **Package Manager:** `uv`
*   **Testing:** `pytest`
*   **Code Style:** `black`
*   **Containerization:** Docker and Docker Compose
*   **Background Jobs:** Celery with Redis

## Development Workflow

All common development tasks are managed via `make` commands, which wrap `uv` and `docker-compose`.

### Running the Application (Docker)

The preferred method for development is using Docker Compose.

*   **Start development services:**
    ```bash
    make dev-docker
    ```
*   **Stop services:**
    ```bash
    make docker-down
    ```
*   **View logs:**
    ```bash
    make docker-logs-web
    ```

### Testing

The project uses `pytest`. Run the main test suite with:

```bash
make test
```

### Code Style & Linting

The project uses `black` for code formatting.

*   **Check formatting:**
    ```bash
    make black-check
    ```
*   **Apply formatting:**
    ```bash
    make black
    ```

### Dependency Management

Dependencies are managed with `uv`.

*   **Install development dependencies:**
    ```bash
    make install-dev
    ```
