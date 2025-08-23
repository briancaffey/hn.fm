# Video Generation Pipeline Step

This document describes the new video generation step that has been added to the hn.fm pipeline.

## Overview

The video generation step creates videos with spoken words displayed on a black background. Each word is displayed between its start and stop timestamps, with different colors for different speakers.

## Features

- **Black Background**: 1024x1024 resolution with 30 FPS
- **Word-Level Timing**: Each spoken word appears at its exact timestamp
- **Speaker Colors**:
  - SPEAKER_00: White
  - SPEAKER_01: Orange
- **Professional Subtitles**: Uses ASS format with native styling support
- **Audio Sync**: Video duration matches audio duration exactly
- **High Quality**: Uses H.264 encoding with AAC audio

## Implementation

### Video Generator Service

Located at `src/hnfm/video/video_generator.py`, this service:

1. **Loads ASR Data**: Parses the ASR JSON file to extract word-level timing and speaker information
2. **Creates Subtitles**: Generates an SRT subtitle file with speaker-specific styling
3. **Generates Video**: Uses ffmpeg to create a video with:
   - Black background (`color=black:size=1024x1024`)
   - Subtitles with speaker colors
   - Synchronized audio
   - H.264 video codec and AAC audio codec

### Pipeline Integration

The video generation step is fully integrated into the pipeline:

- **Step Name**: `video_generation`
- **Dependencies**: `asr_processing` (requires ASR results and final audio)
- **Output**: `content/video.mp4`
- **Cache Key**: `video_results`

### Pipeline Flow

```
ASR Processing → Video Generation → [Future steps...]
     ↓                ↓
content/asr.json  content/video.mp4
```

## Usage

### Standalone Testing

Use the `run_video_step.py` script to test video generation against any output folder:

```bash
# Basic usage
uv run python run_video_step.py outputs/story_name

# Specify custom audio file
uv run python run_video_step.py outputs/story_name --audio-file path/to/audio.wav

# Specify custom output path
uv run python run_video_step.py outputs/story_name --output-video path/to/output.mp4

# Enable verbose logging
uv run python run_video_step.py outputs/story_name --verbose
```

### Pipeline Integration

The video generation step runs automatically as part of the full pipeline after ASR processing is complete.

## Requirements

- **ffmpeg**: Must be installed and available in PATH
- **ffprobe**: For audio duration detection
- **Python Dependencies**: Standard hn.fm dependencies

## Output

The generated video will be saved as `content/video.mp4` in the story's output directory.

## Technical Details

### Subtitle Format

Uses ASS (Advanced SubStation Alpha) format which natively supports styling:
- **Speaker00 Style**: White text (`&H00FFFFFF`), 48pt font, bold, centered
- **Speaker01 Style**: Orange text (`&H00008CFF`), 48pt font, bold, centered
- **Positioning**: Center-aligned with proper margins
- **Format**: Professional subtitle format with full styling support

### FFmpeg Command

```bash
ffmpeg -y -f lavfi -i "color=black:size=1024x1024:duration={duration}" \
       -i {audio_file} \
       -vf "ass={subtitle_file}" \
       -c:a aac -c:v libx264 -preset medium -crf 23 -shortest \
       {output_path}
```

The `ass` filter is used instead of `subtitles` since we generate ASS format files with native styling support.

## Future Enhancements

- **Custom Colors**: Allow configuration of speaker colors
- **Font Options**: Configurable font family and size
- **Background Options**: Custom background images or colors
- **Animation**: Smooth transitions between words
- **Layout Options**: Different text positioning and alignment
