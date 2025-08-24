"""Video generation service for hn.fm."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
import tempfile
import subprocess
import shutil

logger = logging.getLogger(__name__)


class VideoGenerator:
    """Generates videos with spoken words displayed on a black background."""

    def __init__(self):
        """Initialize the video generator."""
        self.width = 1024
        self.height = 1024
        self.fps = 30
        self.speaker_colors = {
            "SPEAKER_00": "white",
            "SPEAKER_01": "orange"
        }

    def generate_video(
        self,
        asr_file_path: str,
        audio_file_path: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Generate a video with spoken words displayed on a black background.

        Args:
            asr_file_path: Path to the ASR JSON file
            audio_file_path: Path to the audio file
            output_path: Path where the output video should be saved

        Returns:
            Dictionary containing video generation results
        """
        try:
            logger.info(f"🎬 Starting video generation...")
            logger.info(f"📁 ASR file: {asr_file_path}")
            logger.info(f"🎵 Audio file: {audio_file_path}")
            logger.info(f"🎥 Output: {output_path}")

            # Load ASR data
            asr_data = self._load_asr_data(asr_file_path)
            if not asr_data:
                raise RuntimeError("Failed to load ASR data")

            # Get audio duration
            audio_duration = self._get_audio_duration(audio_file_path)
            if not audio_duration:
                raise RuntimeError("Failed to get audio duration")

            logger.info(f"⏱️ Audio duration: {audio_duration:.2f} seconds")

            # Create subtitle file
            subtitle_file = self._create_subtitle_file(asr_data, audio_duration)

            # Generate video
            video_path = self._create_video_with_ffmpeg(
                audio_file_path,
                subtitle_file,
                output_path,
                audio_duration
            )

            # Clean up temporary files
            if subtitle_file and Path(subtitle_file).exists():
                Path(subtitle_file).unlink()

            logger.info(f"✅ Video generation completed successfully")
            logger.info(f"🎥 Video saved to: {video_path}")

            return {
                "success": True,
                "video_path": video_path,
                "duration": audio_duration,
                "resolution": f"{self.width}x{self.height}",
                "fps": self.fps
            }

        except Exception as e:
            logger.error(f"❌ Video generation failed: {e}")
            raise RuntimeError(f"Video generation failed: {e}")

    def _load_asr_data(self, asr_file_path: str) -> Dict[str, Any]:
        """Load ASR data from JSON file."""
        try:
            with open(asr_file_path, 'r') as f:
                data = json.load(f)

            if not data.get("success"):
                raise RuntimeError("ASR data indicates failure")

            return data
        except Exception as e:
            logger.error(f"Failed to load ASR data: {e}")
            return None

    def _get_audio_duration(self, audio_file_path: str) -> float:
        """Get audio duration using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_file_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
            return duration

        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid duration value: {e}")
            return None

    def _create_subtitle_file(self, asr_data: Dict[str, Any], audio_duration: float) -> str:
        """Create an ASS subtitle file from ASR data with speaker-specific styling."""
        try:
            # Create temporary ASS subtitle file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as f:
                subtitle_file = f.name

            segments = asr_data.get("segments", [])

            with open(subtitle_file, 'w', encoding='utf-8') as f:
                # Write ASS header
                f.write("[Script Info]\n")
                f.write("Title: Generated Subtitles\n")
                f.write("ScriptType: v4.00+\n")
                f.write("WrapStyle: 1\n")
                f.write("ScaledBorderAndShadow: yes\n")
                f.write("YCbCr Matrix: TV.601\n\n")

                # Write styles section
                f.write("[V4+ Styles]\n")
                f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
                # Speaker00: White text with orange border
                f.write("Style: Speaker00,DejaVu Sans,48,&H00FFFFFF,&H000000FF,&H00008CFF,&H80000000,1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n")
                # Speaker01: Orange text with white border
                f.write("Style: Speaker01,DejaVu Sans,48,&H00008CFF,&H000000FF,&H00FFFFFF,&H80000000,1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n\n")

                # Write events section
                f.write("[Events]\n")
                f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

                for segment in segments:
                    words = segment.get("words", [])

                    for word_data in words:
                        word = word_data.get("word", "").strip()
                        start_time = word_data.get("start", 0)
                        end_time = word_data.get("end", 0)
                        speaker = word_data.get("speaker", "SPEAKER_00")

                        if not word or start_time >= end_time:
                            continue

                        # Convert times to ASS format (H:MM:SS.cc)
                        start_ass = self._seconds_to_ass(start_time)
                        end_ass = self._seconds_to_ass(end_time)

                        # Determine style based on speaker
                        style = "Speaker01" if speaker == "SPEAKER_01" else "Speaker00"

                        # Write subtitle entry
                        f.write(f"Dialogue: 0,{start_ass},{end_ass},{style},,0,0,0,,{word}\n")

            logger.info(f"📝 Created ASS subtitle file with word-level styling")
            return subtitle_file

        except Exception as e:
            logger.error(f"Failed to create subtitle file: {e}")
            return None

    def _seconds_to_ass(self, seconds: float) -> str:
        """Convert seconds to ASS time format (H:MM:SS.cc)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centiseconds = int((seconds % 1) * 100)

        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    def _get_speaker_color_hex(self, speaker: str) -> str:
        """Get hex color code for a speaker."""
        color_map = {
            "SPEAKER_00": "FFFFFF",  # White
            "SPEAKER_01": "FF8C00",  # Orange
        }
        return color_map.get(speaker, "FFFFFF")  # Default to white

    def _seconds_to_srt(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def _create_video_with_ffmpeg(
        self,
        audio_file: str,
        subtitle_file: str,
        output_path: str,
        audio_duration: float
    ) -> str:
        """Create video using ffmpeg with black background and subtitles."""
        try:
            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)

            # Build ffmpeg command
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-f", "lavfi",
                "-i", f"color=black:size={self.width}x{self.height}:duration={audio_duration}",
                "-i", audio_file,
                "-vf", f"ass={subtitle_file}",
                "-c:a", "aac",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-shortest",
                output_path
            ]

            logger.info(f"🎬 Running ffmpeg command...")
            logger.debug(f"ffmpeg command: {' '.join(cmd)}")

            # Run ffmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            if not Path(output_path).exists():
                raise RuntimeError("ffmpeg completed but output file not found")

            logger.info(f"✅ ffmpeg completed successfully")
            return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed: {e}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise RuntimeError(f"ffmpeg failed: {e}")
        except Exception as e:
            logger.error(f"Video creation failed: {e}")
            raise RuntimeError(f"Video creation failed: {e}")

    def process_and_save(
        self,
        asr_file_path: str,
        audio_file_path: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Process ASR data and audio to generate video, then save to output path.

        This is a convenience method that combines generate_video and saves the result.

        Args:
            asr_file_path: Path to the ASR JSON file
            audio_file_path: Path to the audio file
            output_path: Path where the output video should be saved

        Returns:
            Dictionary containing video generation results
        """
        return self.generate_video(asr_file_path, audio_file_path, output_path)
