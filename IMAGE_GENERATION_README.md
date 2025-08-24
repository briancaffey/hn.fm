# Image Generation Service

The Image Generation Service integrates with an external AI image generation API to create images for video content based on script segments.

## Features

- **API Integration**: Connects to image generation service at `http://192.168.5.173:8000`
- **Batch Processing**: Generate multiple images for script segments
- **Flexible Configuration**: Configurable image dimensions, quality, and generation parameters
- **Automatic Prompt Creation**: Converts script text into image generation prompts
- **Error Handling**: Graceful fallback when image generation fails

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
IMAGE_GENERATION_BASE_URL=http://192.168.5.173:8000
```

### Configuration File

The service is configured in `config.yaml`:

```yaml
image_generation:
  base_url: "${IMAGE_GENERATION_BASE_URL}"
  default_height: 1024
  default_width: 1024
  default_cfg_scale: 5
  default_mode: "base"
  default_steps: 50
  default_samples: 1
  output_directory: "images"
```

## Usage

### Basic Image Generation

```python
from hnfm.video import ImageGenerationService

# Initialize service
service = ImageGenerationService()

# Generate a single image
image_path = service.generate_and_save_image(
    prompt="a cozy coffee shop interior",
    output_dir="outputs/my_story/images",
    filename="coffee_shop.png"
)
```

### Batch Generation for Script Segments

```python
# Script segments with text content
script_segments = [
    {"text": "The story begins in a bustling tech office..."},
    {"text": "Later that day, the protagonist walks through the city..."},
    {"text": "Finally, they arrive at their destination..."}
]

# Generate images for each segment
image_paths = service.generate_images_for_script(
    script_segments=script_segments,
    output_dir="outputs/my_story/images"
)
```

### Custom Generation Parameters

```python
# Override default parameters
image_path = service.generate_and_save_image(
    prompt="a futuristic cityscape",
    output_dir="outputs/my_story/images",
    height=2048,
    width=1024,
    cfg_scale=7,
    steps=75,
    seed=42
)
```

## API Endpoints

The service communicates with the image generation API:

- **Health Check**: `GET /v1/health/ready`
- **Image Generation**: `POST /v1/infer`

### Request Format

```json
{
  "prompt": "a simple coffee shop interior",
  "height": 1024,
  "width": 1024,
  "cfg_scale": 5,
  "mode": "base",
  "image": null,
  "samples": 1,
  "seed": 0,
  "steps": 50
}
```

### Response Format

```json
{
  "artifacts": [
    {
      "base64": "/9j/4AAQSkZ...b+AVZ/9k=",
      "finishReason": "SUCCESS",
      "seed": 0
    }
  ]
}
```

## Integration with Pipeline

The image generation service is designed to integrate with the main pipeline:

1. **Script Processing**: After script generation, extract text segments
2. **Image Generation**: Generate images for each segment
3. **Video Creation**: Use generated images in video generation
4. **Output Organization**: Images are saved to `outputs/{story_name}/images/`

## Testing

Run the test suite to verify the service:

```bash
uv run python test_image_generation.py
```

This will test:
- Configuration loading
- Health check
- Single image generation
- Multiple image generation

## Dependencies

- `requests`: HTTP client for API communication
- `Pillow`: Image processing and saving
- `pathlib`: File path handling

## Error Handling

The service includes comprehensive error handling:

- **API Failures**: Logs errors and raises exceptions
- **Network Issues**: Timeout handling and connection error recovery
- **File System**: Automatic directory creation and permission handling
- **Partial Failures**: Continues processing other segments if one fails

## Future Enhancements

- **LLM Integration**: Use AI to create better image prompts from script text
- **Style Consistency**: Maintain visual consistency across generated images
- **Caching**: Cache generated images to avoid regeneration
- **Quality Control**: Automatic image quality assessment and regeneration
- **Batch Optimization**: Parallel image generation for faster processing
