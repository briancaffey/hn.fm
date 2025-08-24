# Content Structure and Text-Only Pipeline Mode

This document describes the new content structure system and text-only pipeline mode for hn.fm.

## Overview

The pipeline now supports a **text-only mode** that generates script content and creates a structured `main.yaml` file without running TTS, image generation, or video creation. This allows for faster iteration and content review before committing to media generation.

## Content Structure (main.yaml)

The pipeline generates a structured YAML file at `outputs/{story_name}/content/main.yaml` that contains:

### File Structure

```yaml
metadata:
  title: "Story Title"
  created_at: "2024-08-24T13:30:00"
  script_length: 1500
  tts_lines_count: 8
  image_style: "detailed cartoon style"

script:
  full_text: "Complete script text..."
  tts_lines:
    - "First TTS line"
    - "Second TTS line"
    - "..."

narration:
  - group_id: 0
    lines:
      - "First TTS line"
      - "Second TTS line"
    speaker_tags: ["[S1]", "[S2]"]
    start_time: null  # Filled by ASR later
    end_time: null    # Filled by ASR later
    duration: null    # Filled by ASR later

images:
  style: "detailed cartoon style"
  generated: []       # Images that have been created
  pending:            # Images waiting to be generated
    - group_id: 0
      lines:
        - "First TTS line"
        - "Second TTS line"
      status: "pending"
      image_prompt: null
      image_file: null

audio:
  tts_generated: false
  files: []
  duration: null

video:
  generated: false
  file: null
  duration: null
```

### Key Features

- **Narration Groups**: TTS lines are grouped in pairs (S1/S2) for coordinated image generation
- **Image Prompts**: LLM-generated prompts for each narration group
- **Status Tracking**: Tracks progress of image generation, TTS, and video creation
- **Timestamps**: ASR results update timing information for video synchronization

## Text-Only Pipeline Mode

### Usage

```python
from hnfm.pipeline import PipelineManager

# Initialize in text-only mode
pipeline = PipelineManager(text_only=True)

# Run pipeline (only text generation steps)
result = pipeline.run_pipeline()
```

### What Gets Generated

✅ **Text-Only Mode Includes:**
- System health check
- Hacker News scraping
- Content extraction and processing
- Script generation
- Main content structure (main.yaml)

❌ **Text-Only Mode Skips:**
- Image generation
- TTS audio generation
- Audio cleaning and assembly
- ASR processing
- Video generation

### Benefits

1. **Fast Iteration**: Generate and review content quickly
2. **Content Review**: Review scripts before committing to media generation
3. **Debugging**: Easier to debug content issues without media generation
4. **Development**: Test content pipeline changes independently

## LLM-Powered Image Prompts

### How It Works

1. **Script Analysis**: LLM analyzes the full script for context
2. **Group Processing**: Each narration group (2 TTS lines) gets processed
3. **Prompt Generation**: LLM creates detailed, visual image prompts
4. **Style Consistency**: Prompts maintain the configured visual style

### System Prompt

The LLM uses a specialized system prompt with:
- **Reasoning: high** (for gpt-oss model)
- Expert image prompt engineering instructions
- Style guidelines and visual coherence requirements
- Focus on visual elements, mood, and composition

### Example Prompts

**Input TTS Lines:**
```
[S1] The story begins in a bustling tech office
[S2] Developers work feverishly on their latest project
```

**Generated Prompt:**
```
A modern tech office interior with multiple developers working at their desks,
computers and monitors scattered around, intense focus on faces, warm lighting
from overhead fixtures, detailed cartoon style with vibrant colors
```

## Configuration

### Image Style

Set the default image style in `config.yaml`:

```yaml
image_generation:
  default_style: "detailed cartoon style"
  # ... other settings
```

### Environment Variables

```bash
# Image generation service
IMAGE_GENERATION_BASE_URL=http://192.168.5.173:8000

# LLM service (for prompt generation)
LLM_BASE_URL=http://192.168.5.173:1234/v1
```

## Usage Examples

### 1. Generate Content Only

```bash
# Run text-only pipeline
uv run python run_text_only_pipeline.py
```

### 2. Review Generated Content

```bash
# Check the main.yaml file
cat outputs/{story_name}/content/main.yaml
```

### 3. Run Full Pipeline Later

```python
# Standard pipeline (includes all steps)
pipeline = PipelineManager(text_only=False)
result = pipeline.run_pipeline()
```

### 4. Custom Image Style

```python
from hnfm.content import ImagePromptGenerator

generator = ImagePromptGenerator()
prompts = generator.generate_image_prompts_for_narration(
    narration_groups,
    full_script,
    style="photorealistic cinematic style"
)
```

## File Organization

```
outputs/
└── {story_name}/
    ├── content/
    │   ├── main.yaml          # Main content structure
    │   ├── script.md          # Full script
    │   ├── tts_lines.txt      # TTS lines
    │   └── script_meta.json   # Script metadata
    ├── images/                # Generated images (when not text-only)
    ├── content/               # Video and ASR results (when not text-only)
    └── ...
```

## Testing

### Test Text-Only Mode

```bash
uv run python test_text_only_pipeline.py
```

### Test Content Structure

```bash
uv run python test_pipeline_with_images.py
```

### Test Image Generation

```bash
uv run python test_image_generation.py
```

## Troubleshooting

### Common Issues

1. **Main.yaml Not Created**: Check if content manager import is working
2. **LLM Prompt Generation Fails**: Verify LLM service is accessible
3. **Image Generation Fails**: Check image service connectivity
4. **Pipeline Steps Missing**: Verify text_only flag is set correctly

### Logging

The system provides comprehensive logging:
- Content structure creation/updates
- LLM prompt generation progress
- Image generation status
- Pipeline step execution

Check logs for detailed error information and debugging.

## Future Enhancements

- **Prompt Templates**: Configurable prompt templates for different content types
- **Style Presets**: Predefined visual style combinations
- **Content Validation**: Automatic content quality assessment
- **Batch Processing**: Parallel processing for faster generation
- **Content Versioning**: Track changes and iterations
