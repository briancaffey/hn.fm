# Image Generation

Generate images for podcast episodes using AI image generation services.

## Quick Start

```bash
# Generate images for a story
uv run python run_image_step.py --story-id "test" --story-title "Test Story"

# Generate images with custom style
uv run python run_image_step.py --story-id "test" --story-title "Test Story" --style "photorealistic"
```

## Configuration

Add to your `.env` file:

```bash
IMAGE_GENERATION_BASE_URL=http://192.168.5.173:8000
LLM_BASE_URL=http://192.168.5.173:1234/v1
```

## How It Works

1. **Read content structure** from `main.yaml`
2. **Generate image prompts** using LLM for each narration group
3. **Create images** using AI image generation service
4. **Update content structure** with generated image paths

## Image Styles

Configure in `config.yaml`:

```yaml
image_generation:
  default_style: "detailed cartoon style"
  available_styles:
    - "detailed cartoon style"
    - "photorealistic cinematic style"
    - "minimalist geometric style"
```

## Output

Images are saved to:
```
outputs/
  Story Name/
    images/
      group_0.png
      group_1.png
      ...
```

## Troubleshooting

- **Service unavailable**: Check image generation service is running
- **LLM errors**: Verify LLM service connectivity
- **Prompt failures**: Check content structure and narration groups
