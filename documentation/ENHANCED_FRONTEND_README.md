# Enhanced Frontend for HN.fm Pipeline

This document describes the enhanced frontend components and features that provide comprehensive visibility into the content processing pipeline.

## 🚀 New Features

### 1. Enhanced Content Detail View (`/items/[id]/enhanced`)

A comprehensive view that shows:
- **Real-time Pipeline Progress**: Live updates of processing steps with progress bars
- **Step-by-Step Status**: Detailed status for each pipeline step (firecrawl, content processing, script generation, TTS, image generation, video generation)
- **Generated Artifacts**: Organized display of all generated media files
- **Service Lock Status**: Shows which external services are currently locked
- **Retry Functionality**: Ability to retry failed steps
- **Auto-refresh**: Automatically updates every 3 seconds during processing

### 2. Pipeline Dashboard

A centralized dashboard showing:
- **Processing Statistics**: Total, processing, completed, and failed items
- **Service Status**: Real-time status of all external services (TTS, ASR, Vision, etc.)
- **Quick Actions**: Easy access to common operations
- **Auto-refresh**: Updates every 30 seconds

### 3. Enhanced Media Display

Organized tabs for different artifact types:
- **Audio Files**: Playable audio players with download links
- **Images**: Grid view with hover actions for viewing/downloading
- **Videos**: Embedded video players with download options
- **Scripts**: Downloadable script files

## 🏗️ Architecture

### Frontend Components

#### Core Components
- `PipelineDashboard.vue` - Main dashboard component
- `enhanced.vue` - Enhanced content detail page
- `progress.vue` - Progress bar component
- `tabs.vue` - Tab navigation system

#### UI Components
- `tabs-list.vue` - Tab list container
- `tabs-trigger.vue` - Individual tab buttons
- `tabs-content.vue` - Tab content containers

### Backend API Endpoints

#### New Endpoints
- `GET /api/content/{content_id}/artifacts` - Get all artifacts for a content item
- `GET /api/content/{content_id}/media/{media_type}/{filename}` - Serve media files
- `GET /api/content/{content_id}/enhanced-status` - Get enhanced pipeline status
- `GET /api/pipeline/status` - Get pipeline status
- `POST /api/enhanced-pipeline/retry/{content_id}/{step_name}` - Retry failed step

## 🎯 Usage

### Accessing Enhanced Views

1. **From Content List**: Click the workflow icon (⚙️) next to any item
2. **From Item Detail**: Click the "Enhanced View" button
3. **Direct URL**: Navigate to `/items/{id}/enhanced`

### Pipeline Monitoring

1. **Dashboard**: Visit the main page to see the pipeline dashboard
2. **Real-time Updates**: The dashboard auto-refreshes every 30 seconds
3. **Service Status**: Monitor which external services are currently locked

### Media Management

1. **View Artifacts**: Use the tabs to switch between different media types
2. **Play Media**: Click play buttons to preview audio/video content
3. **Download Files**: Use download buttons to save media files locally
4. **View Images**: Hover over images to see view/download options

## 🔧 Configuration

### API Base URL

The frontend uses the `apiBase` from the runtime config:

```typescript
// nuxt.config.ts
runtimeConfig: {
  public: {
    apiBase: 'http://localhost:8000',
  }
}
```

### Auto-refresh Intervals

- **Enhanced View**: 3 seconds during processing
- **Dashboard**: 30 seconds continuously
- **Service Status**: 30 seconds continuously

## 🎨 UI/UX Features

### Visual Indicators

- **Status Badges**: Color-coded status indicators
- **Progress Bars**: Visual progress tracking
- **Icons**: Contextual icons for different states
- **Loading States**: Spinner animations during operations

### Responsive Design

- **Mobile-friendly**: Responsive grid layouts
- **Touch-friendly**: Large touch targets for mobile
- **Adaptive**: Adjusts to different screen sizes

### Accessibility

- **Keyboard Navigation**: Full keyboard support
- **Screen Reader**: Proper ARIA labels
- **Color Contrast**: High contrast for readability
- **Focus Management**: Clear focus indicators

## 🚦 Status Indicators

### Pipeline Step Status
- **Pending** (⏰): Step waiting to be executed
- **Processing** (🔄): Step currently running
- **Completed** (✅): Step finished successfully
- **Failed** (❌): Step encountered an error

### Service Lock Status
- **Available** (🔓): Service is free to use
- **Locked** (🔒): Service is currently in use

### Overall Status
- **Pending**: Content waiting to be processed
- **Processing**: Content currently being processed
- **Completed**: All steps completed successfully
- **Failed**: Processing failed at some step

## 🔄 Real-time Updates

### WebSocket Integration (Future)
- Real-time pipeline status updates
- Live service lock notifications
- Instant artifact availability

### Current Polling
- Enhanced view: 3-second intervals during processing
- Dashboard: 30-second intervals
- Manual refresh buttons available

## 🛠️ Development

### Adding New Artifact Types

1. **Backend**: Add new artifact type to `get_content_artifacts` endpoint
2. **Frontend**: Add new tab to the enhanced view
3. **UI**: Create appropriate display component

### Customizing Status Indicators

Modify the status mapping functions:
```typescript
const getStatusVariant = (status: string) => {
  // Add new status variants here
}
```

### Adding New Pipeline Steps

1. **Backend**: Update pipeline step definitions
2. **Frontend**: Add step to the status display
3. **UI**: Add appropriate icons and colors

## 🧪 Testing

### Manual Testing

1. **Start Services**:
   ```bash
   # Backend
   uv run python run_web_server.py

   # Frontend
   cd frontend && yarn dev
   ```

2. **Test Enhanced View**:
   - Navigate to `/items/{id}/enhanced`
   - Start processing and watch real-time updates
   - Test retry functionality for failed steps

3. **Test Dashboard**:
   - Visit main page to see dashboard
   - Verify auto-refresh functionality
   - Check service status updates

### Automated Testing

Run the test script:
```bash
uv run python test_enhanced_frontend.py
```

## 🐛 Troubleshooting

### Common Issues

1. **Enhanced Status Not Available**:
   - Content may not be using enhanced pipeline
   - Check if Redis is running
   - Verify enhanced tasks are registered

2. **Media Files Not Loading**:
   - Check file paths in outputs directory
   - Verify media serving endpoint
   - Check file permissions

3. **Auto-refresh Not Working**:
   - Check browser console for errors
   - Verify API endpoints are accessible
   - Check network connectivity

### Debug Mode

Enable debug logging in the browser console:
```javascript
localStorage.setItem('debug', 'hnfm:*')
```

## 🔮 Future Enhancements

### Planned Features
- **WebSocket Integration**: Real-time updates without polling
- **Bulk Operations**: Process multiple items simultaneously
- **Advanced Filtering**: Filter by processing status, date, etc.
- **Export Functionality**: Export processing reports
- **Notification System**: Alerts for completed/failed processing

### Performance Optimizations
- **Lazy Loading**: Load media files on demand
- **Caching**: Cache frequently accessed data
- **Compression**: Optimize media file serving
- **CDN Integration**: Serve media from CDN

## 📚 Related Documentation

- [Enhanced System README](./ENHANCED_SYSTEM_README.md) - Backend architecture
- [API Documentation](./documentation/OPENAPI_DOCUMENTATION.md) - API reference
- [Development Guide](./documentation/DEVELOPMENT.md) - Development setup

## 🤝 Contributing

When adding new features:

1. **Follow Patterns**: Use existing component patterns
2. **API First**: Design backend endpoints first
3. **Test Thoroughly**: Test both success and error cases
4. **Document Changes**: Update this README
5. **Consider UX**: Think about user experience

## 📄 License

This enhanced frontend is part of the HN.fm project and follows the same license terms.
