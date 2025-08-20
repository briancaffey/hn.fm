# hn.fm Development Roadmap

## Bug Fixes & Improvements

### LLM Service Robustness
[x] Fix NoneType error in LLM service when local LLM returns malformed responses
[x] Add proper response validation to prevent crashes on invalid LLM responses
[x] Simplify fallback script to single line: "[S1] This is a fallback, error generating script"
[x] Add comprehensive error handling for LLM service failures
[x] Fix local LLM endpoint issue - was using wrong API path (missing /v1 prefix)
[x] Add retry mechanism for transient LLM failures
[ ] Add fallback to OpenAI when local LLM is consistently failing
[ ] Investigate why local LLM (openai/gpt-oss-20b) consistently returns invalid response structures

### Content Processing Stability
[ ] Fix content processing failures when articles have unusual formatting
[ ] Add better error handling for malformed HTML content
[ ] Add content validation before script generation
[ ] Add fallback content processing when primary method fails

### URL Filtering & Quality Control
[x] Add URL filtering to avoid problematic domains (Japanese websites, YouTube, paywalls)
[x] Filter out websites that consistently cause Firecrawl errors
[x] Improve story selection to prioritize reliable content sources
[ ] Add dynamic URL blacklisting based on failure patterns
[ ] Add content quality scoring before processing

## Content Scraping & Flexibility

### Article Source Flexibility
[x] Add ability to scrape from /newest Hacker News articles (not just front page)
[ ] Add ability to scrape from /show HN and /ask HN sections
[ ] Add ability to scrape from specific HN post IDs
[ ] Add ability to provide custom URLs for scraping (not just HN links)
[ ] Add support for scraping from other tech news sources (Reddit r/programming, Lobsters, etc.)
[ ] Add date-based filtering (e.g., "articles from last 7 days")
[ ] Maintain a list of links that we do not want to scrape (e.g., youtube.com, paywall sites, etc.)

### Enhanced Content Processing
[ ] Incorporate HN comments into scraped content
[ ] Add comment filtering and ranking (by score, relevance, length)
[ ] Generate comment summaries for podcast scripts
[ ] Add support for handling different content types (articles, discussions, tutorials)
[ ] Improve content cleaning and formatting for better TTS quality
[ ] Add content length estimation before processing

## Pipeline & Testing Improvements

### Testing Flexibility
[ ] Add command-line flags for different HN sections (/newest, /show, /ask)
[ ] Add dry-run mode that shows what would be scraped without executing
[ ] Add interactive mode for selecting articles from a list
[ ] Add batch processing for multiple articles
[ ] Add regression testing for pipeline steps

### Pipeline Enhancements
[ ] Add pipeline step for comment processing
[ ] Add content quality scoring before script generation
[x] Add system health check step to verify all required services are running before pipeline execution
[ ] Add pipeline step for content summarization
[ ] Add pipeline step for content validation
[ ] Add pipeline step for audio quality assessment

## Audio & TTS Improvements

### Voice & Quality
[ ] Add support for multiple voices in single episode
[ ] Add voice switching based on content type (e.g., different voice for comments)
[ ] Improve audio post-processing and noise reduction
[ ] Add audio normalization and compression
[ ] Add support for background music/sound effects
[ ] Add audio chapter markers for different sections

### TTS Service
[ ] Add fallback TTS services if primary fails
[ ] Add TTS service health monitoring
[ ] Add TTS quality metrics and feedback
[ ] Add support for different TTS models/voices
[ ] Add TTS caching to avoid regenerating same content

## Content Generation & Scripts

### Script Enhancement
[ ] Add dynamic script generation based on content length
[ ] Add script templates for different content types
[ ] Add script versioning and A/B testing
[ ] Add script quality scoring and feedback
[ ] Add script editing interface for manual adjustments
[ ] Add support for different podcast formats (news, discussion, tutorial)

### Content Analysis
[ ] Add content sentiment analysis
[ ] Add content topic classification
[ ] Add content difficulty assessment
[ ] Add content controversy detection
[ ] Add content freshness scoring

## Infrastructure & Performance

### Caching & Storage
[ ] Improve caching strategy for HN data
[ ] Add database backend for better data persistence
[ ] Add content deduplication
[ ] Add cache invalidation strategies
[ ] Add backup and restore functionality

### Performance
[ ] Add parallel processing for multiple articles
[ ] Add async/await for I/O operations
[ ] Add progress bars and better logging
[ ] Add performance monitoring and metrics
[ ] Add resource usage optimization

## User Experience & Interface

### CLI Improvements
[ ] Add interactive article selection
[ ] Add better error messages and suggestions
[ ] Add progress indicators for long operations
[ ] Add configuration validation
[ ] Add help text for all commands
[ ] Add command aliases and shortcuts

### Configuration
[ ] Add configuration validation
[ ] Add configuration templates
[ ] Add environment-specific configs
[ ] Add configuration migration tools
[ ] Add configuration documentation

## Monitoring & Analytics

### Pipeline Monitoring
[ ] Add pipeline execution metrics
[ ] Add success/failure rate tracking
[ ] Add execution time monitoring
[ ] Add resource usage tracking
[ ] Add error rate monitoring
[ ] Add pipeline health dashboard

### Content Analytics
[ ] Add content popularity tracking
[ ] Add user engagement metrics
[ ] Add content quality metrics
[ ] Add TTS quality metrics
[ ] Add audio quality metrics

## Integration & APIs

### External Services
[ ] Add support for more content sources
[ ] Add support for more TTS services
[ ] Add support for more audio processing tools
[ ] Add webhook support for notifications
[ ] Add API endpoints for external access

### Deployment
[ ] Add Docker support
[ ] Add CI/CD pipeline
[ ] Add automated testing
[ ] Add deployment scripts
[ ] Add monitoring and alerting

## Documentation & Maintenance

### Code Quality
[ ] Add comprehensive test coverage
[ ] Add code documentation
[ ] Add API documentation
[ ] Add user guides
[ ] Add developer setup guide
[ ] Add troubleshooting guide

### Maintenance
[ ] Add dependency updates
[ ] Add security audits
[ ] Add performance reviews
[ ] Add code reviews
[ ] Add changelog management

## Future Enhancements

### Advanced Features
[ ] Add machine learning for content selection
[ ] Add personalized content recommendations
[ ] Add multi-language support
[ ] Add podcast episode scheduling
[ ] Add social media integration
[ ] Add community features

### Monetization
[ ] Add premium content features
[ ] Add sponsorship integration
[ ] Add analytics dashboard
[ ] Add user accounts and preferences
[ ] Add subscription management
