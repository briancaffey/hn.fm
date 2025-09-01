# Video Generation

Create video podcasts from audio and images.

## Quick Start

```bash
# Generate video for a story
uv run python run_video_step.py --story-id "test" --story-title "Test Story"

# Generate with custom settings
uv run python run_video_step.py --story-id "test" --story-title "Test Story" --fps 30
```

## Configuration

Add to your `.env` file:

```bash
VIDEO_GENERATION_BASE_URL=http://192.168.5.173:8000
```

## How It Works

1. **Read content structure** from `main.yaml`
2. **Load audio and images** from pipeline outputs
3. **Generate video** using AI video generation service
4. **Save final video** to outputs directory

## Video Settings

Configure in `config.yaml`:

```yaml
video_generation:
  default_fps: 24
  default_resolution: "1920x1080"
  default_duration: "auto"
```

## Output

Videos are saved to:
```
outputs/
  Story Name/
    Story Name_video.mp4
```

## Troubleshooting

- **Service unavailable**: Check video generation service is running
- **Missing assets**: Ensure audio and images are generated first
- **Format errors**: Verify audio/image file formats are supported
