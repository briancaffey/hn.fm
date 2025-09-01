# Content Structure

The pipeline generates structured content files for podcast episodes.

## Quick Start

```bash
# Run text-only pipeline
uv run python run_text_only_pipeline.py --story-id "test" --story-title "Test Story"

# Run full pipeline
uv run python run_pipeline.py --story-id "test" --story-title "Test Story"
```

## Content Structure

The pipeline creates `outputs/{story_name}/content/main.yaml`:

```yaml
metadata:
  title: "Story Title"
  created_at: "2024-08-24T13:30:00"
  script_length: 1500

script:
  full_text: "Complete script text..."
  tts_lines:
    - "First TTS line"
    - "Second TTS line"

narration:
  - group_id: 0
    lines: ["First TTS line", "Second TTS line"]
    speaker_tags: ["[S1]", "[S2]"]

images:
  style: "detailed cartoon style"
  pending: []  # Images to generate

audio:
  tts_generated: false
  files: []

video:
  generated: false
  file: null
```

## Pipeline Modes

### Text-Only Mode
- Generates script and content structure
- Skips media generation (TTS, images, video)
- Faster iteration for content review

### Full Mode
- Complete pipeline including media generation
- TTS audio, images, and final video

## Output Structure

```
outputs/
  Story Name/
    content/
      main.yaml          # Content structure
      script.txt         # Full script
      tts_lines.txt      # TTS-ready lines
    batch_001.wav        # Audio batches
    cleaned_batch_001.wav
    Story Name_final.wav # Final audio
```

## Key Features

- **Narration Groups**: TTS lines grouped for coordinated image generation
- **Image Prompts**: LLM-generated prompts for each group
- **Status Tracking**: Progress tracking for all pipeline steps
- **Timestamps**: ASR results for video synchronization
