# TTS Pipeline

Generate audio from text using voice cloning technology.

## Quick Start

```bash
# Generate audio from TTS lines
uv run python generate_audio.py outputs/tts_lines_*.txt

# Customize batch size
uv run python generate_audio.py outputs/tts_lines_*.txt --batch-size 3
```

## Configuration

Add to your `.env` file:

```bash
TTS_BASE_URL=http://192.168.5.96:7860
TTS_DEFAULT_VOICE=notebooklm
```

## Voice Setup

Each voice needs:
```
voices/
  notebooklm/
    sample.txt    # Text content
    sample.wav    # Audio sample
```

## How It Works

1. **Read TTS lines** from file
2. **Process in batches** (default: 2 lines)
3. **Generate audio** using voice cloning
4. **Combine batches** into final audio file

## Output

```
outputs/
  Story Name/
    batch_001.wav
    batch_002.wav
    Story Name_final.wav
```

## Troubleshooting

- **Service unavailable**: Check TTS service is running
- **Missing voices**: Ensure voice samples exist in `voices/` directory
- **Audio errors**: Verify pydub installation and file formats

## API Parameters

- **text_input**: Text to convert
- **audio_prompt_text_input**: Voice sample text
- **audio_prompt_input**: Voice sample audio
- **max_new_tokens**: 3072
- **cfg_scale**: 3
- **temperature**: 1.8
- **speed_factor**: 1
