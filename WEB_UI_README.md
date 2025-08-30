# hn.fm Web Interface

A beautiful web UI for managing your Hacker News content pipeline. This interface provides an easy way to monitor, create, and manage content without using CLI commands.

## Features

- **Dashboard**: Overview of pipeline status and recent content
- **Content Management**: View, create, and manage content items
- **Real-time Updates**: Auto-refresh and live status indicators
- **Responsive Design**: Works on desktop and mobile devices
- **Redis Storage**: Fast, persistent storage for all content data

## Quick Start

### 1. Install Dependencies

The web interface requires additional dependencies. Install them with:

```bash
uv add fastapi uvicorn[standard] redis jinja2
```

### 2. Start Redis

You can use Docker Compose to start Redis:

```bash
# Start just Redis
docker-compose up redis

# Or start both Redis and web server
docker-compose up
```

Alternatively, install Redis locally:

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server
```

### 3. Configure Environment

Copy the environment file and update Redis settings:

```bash
cp env.example .env
```

Update the Redis configuration in `.env`:

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_URL=redis://localhost:6379/0

WEB_HOST=0.0.0.0
WEB_PORT=8000
WEB_RELOAD=true
```

### 4. Test the Setup

Run the test script to verify everything works:

```bash
python test_web_server.py
```

### 5. Start the Web Server

```bash
python run_web_server.py
```

Or use uvicorn directly:

```bash
uvicorn src.hnfm.web.server:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Open in Browser

Navigate to: http://localhost:8000

## Usage

### Dashboard

The main dashboard shows:
- **Quick Actions**: Create new content, refresh data
- **Statistics**: Total content, completed today, active jobs, last completion
- **Recent Content**: Table of latest content items with status

### Creating Content

1. Click "New Content" button
2. Enter the URL (Hacker News post or article)
3. Select content type (article, podcast, video)
4. Click "Add Content"

The system will:
- Store the content in Redis
- Set status to "processing"
- Trigger the pipeline (when integrated)

### Content Management

- **View**: Click "View" link to see content details
- **Edit**: Update title, status, or metadata
- **Delete**: Remove content items
- **Filter**: Filter by content type or status

## API Endpoints

The web interface provides a RESTful API:

- `GET /api/health` - Health check
- `GET /api/content` - List content items
- `GET /api/content/{id}` - Get specific content
- `POST /api/content` - Create new content
- `PUT /api/content/{id}` - Update content
- `DELETE /api/content/{id}` - Delete content
- `GET /api/pipeline/status` - Pipeline status
- `POST /api/pipeline/process` - Trigger processing

## Architecture

### Components

- **FastAPI Server**: Modern, fast web framework
- **Redis Database**: In-memory data store for content
- **Jinja2 Templates**: Server-side HTML rendering
- **Tailwind CSS**: Utility-first CSS framework
- **Vanilla JavaScript**: Lightweight frontend

### Data Flow

1. **Content Creation**: User submits URL → Stored in Redis → Pipeline triggered
2. **Content Processing**: Pipeline updates status → Redis updated → UI reflects changes
3. **Content Display**: UI fetches from Redis → Renders in templates → User sees updates

### File Structure

```
src/hnfm/web/
├── __init__.py          # Package initialization
├── models.py            # Pydantic data models
├── database.py          # Redis database interface
├── api.py              # FastAPI routes
├── server.py           # Main server entry point
├── templates/          # HTML templates
│   ├── base.html      # Base template
│   └── index.html     # Dashboard template
└── static/            # Static assets
    ├── css/           # Stylesheets
    └── js/            # JavaScript files
```

## Development

### Adding New Features

1. **Models**: Add new fields to `models.py`
2. **Database**: Implement storage logic in `database.py`
3. **API**: Add endpoints in `api.py`
4. **Templates**: Create HTML templates
5. **Frontend**: Add JavaScript functionality

### Testing

```bash
# Test database and models
python test_web_server.py

# Test API endpoints
curl http://localhost:8000/api/health
```

### Debugging

- Check Redis connection: `redis-cli ping`
- View logs: Check console output
- API docs: http://localhost:8000/docs (FastAPI auto-generated)

## Production Deployment

### Environment Variables

```bash
WEB_HOST=0.0.0.0
WEB_PORT=8000
WEB_RELOAD=false
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password
```

### Using Docker

```bash
# Build and run
docker-compose up --build

# Or just the web service
docker-compose up web
```

### Using a Process Manager

```bash
# With systemd
sudo systemctl enable hnfm-web
sudo systemctl start hnfm-web

# With supervisor
[program:hnfm-web]
command=python run_web_server.py
directory=/path/to/hn.fm
autostart=true
autorestart=true
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check if Redis is running: `redis-cli ping`
   - Verify host/port in `.env`
   - Check firewall settings

2. **Port Already in Use**
   - Change `WEB_PORT` in `.env`
   - Kill existing process: `lsof -ti:8000 | xargs kill`

3. **Template Errors**
   - Check template syntax
   - Verify template directory path
   - Check Jinja2 installation

4. **Static Files Not Loading**
   - Verify static directory path
   - Check file permissions
   - Clear browser cache

### Logs

Check the console output for error messages. Common log levels:
- `INFO`: Normal operation
- `WARNING`: Non-critical issues
- `ERROR`: Problems that need attention

## Future Enhancements

- [ ] User authentication and authorization
- [ ] Content search and filtering
- [ ] File upload and management
- [ ] Real-time notifications
- [ ] Content analytics and metrics
- [ ] Pipeline job queue management
- [ ] Content scheduling
- [ ] Export functionality
- [ ] Dark mode theme
- [ ] Mobile app

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
