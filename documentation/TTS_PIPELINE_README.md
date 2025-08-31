# TTS Pipeline for hn.fm

This document describes how to use the Text-to-Speech (TTS) pipeline to generate audio from script lines.

## Overview

The TTS pipeline converts text lines into audio using voice cloning technology. It processes TTS lines in batches, generates audio for each batch, and combines them into a final audio file.

## Prerequisites

1. **TTS Service**: A running TTS service at `http://192.168.5.96:7860` (configurable via environment variables)
2. **Voice Samples**: Voice samples in the `voices/` directory
3. **Python Dependencies**: Installed via `uv add pydub gradio-client`

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# TTS Service Configuration
TTS_BASE_URL=http://192.168.5.96:7860
TTS_DEFAULT_VOICE=notebooklm
```

### Voice Samples

Each voice needs a directory with:
- `sample.txt` - Text content for voice cloning
- `sample.wav` - Audio sample for voice cloning

Example structure:
```
voices/
  notebooklm/
    sample.txt
    sample.wav
  other_voice/
    sample.txt
    sample.wav
```

## Usage

### Command Line Interface

The simplest way to generate audio:

```bash
# Generate audio from TTS lines file
uv run python generate_audio.py outputs/tts_lines_How_to_Start_Making_Games_in_J.txt

# Customize batch size and output directory
uv run python generate_audio.py outputs/tts_lines_*.txt --batch-size 3 --output-dir custom_outputs

# Use custom story name
uv run python generate_audio.py outputs/tts_lines_*.txt --story-name "My Custom Story"
```

### Programmatic Usage

```python
from hnfm.content.script_generator import ScriptGenerator

# Initialize script generator
script_generator = ScriptGenerator()

# Process TTS lines and generate audio
final_audio_path = script_generator.process_tts_lines(
    tts_lines_file="outputs/tts_lines_*.txt",
    story_name="Story Name",
    batch_size=2
)

print(f"Audio generated: {final_audio_path}")
```

## How It Works

1. **Read TTS Lines**: Reads lines from the TTS lines file
2. **Batch Processing**: Groups lines into batches (default: 2 lines per batch)
3. **Voice Cloning**: For each batch:
   - Sends text + voice sample to TTS API
   - Receives generated audio
   - Saves individual batch audio
4. **Audio Combination**: Combines all batch audio into final file
5. **Organization**: Creates story-specific output directory

## Output Structure

```
outputs/
  Story Name/
    batch_001.wav          # First batch audio
    batch_002.wav          # Second batch audio
    ...
    Story Name_final.wav   # Combined final audio
```

## TTS Service API

The pipeline uses a Gradio client to connect to the TTS service with these parameters:

- **text_input**: The text to convert to speech
- **audio_prompt_text_input**: Voice sample text
- **audio_prompt_input**: Voice sample audio file
- **max_new_tokens**: 3072
- **cfg_scale**: 3
- **temperature**: 1.8
- **top_p**: 0.95
- **cfg_filter_top_k**: 45
- **speed_factor**: 1
- **seed**: Random seed for each attempt

## Error Handling

- **Retry Logic**: Up to 3 attempts per batch with different seeds
- **Graceful Degradation**: Continues processing if individual batches fail
- **Detailed Logging**: Comprehensive logging for debugging

## Testing

Test the pipeline components:

```bash
# Test TTS service connection
uv run python test_tts_simple.py

# Test TTS API calls
uv run python test_tts_api.py

# Test full pipeline
uv run python test_tts_pipeline.py
```

## Troubleshooting

### Common Issues

1. **TTS Service Unavailable**
   - Check if service is running at configured URL
   - Verify network connectivity

2. **Voice Samples Missing**
   - Ensure voice sample files exist
   - Check file permissions

3. **Audio Processing Errors**
   - Verify pydub installation
   - Check audio file formats

### Debug Mode

Enable detailed logging by setting environment variables:

```bash
export LOG_LEVEL=DEBUG
export DEBUG=true
```

## Future Enhancements

- [ ] Support for multiple voice types
- [ ] Audio post-processing (normalization, effects)
- [ ] Batch size optimization
- [ ] Progress tracking and resumption
- [ ] Audio quality metrics
