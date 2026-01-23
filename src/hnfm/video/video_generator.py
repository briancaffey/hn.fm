"""Video generation service for hn.fm."""

import json
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Tuple
import tempfile
import subprocess
import shutil

logger = logging.getLogger(__name__)


class VideoGenerator:
    """Generates videos with generated images and spoken words."""

    def __init__(self):
        """Initialize the video generator."""
        self.width = 1024
        self.height = 1024
        self.fps = 30
        self.speaker_colors = {"SPEAKER_00": "white", "SPEAKER_01": "orange"}

    def generate_video(
        self,
        asr_file_path: str,
        audio_file_path: str,
        main_yaml_path: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """Generate a video with generated images and spoken words.

        Args:
            asr_file_path: Path to the ASR JSON file
            audio_file_path: Path to the audio file
            main_yaml_path: Path to the main.yaml content structure file
            output_path: Path where the output video should be saved

        Returns:
            Dictionary containing video generation results
        """
        try:
            logger.info(f"🎬 Starting video generation with images...")
            logger.info(f"📁 ASR file: {asr_file_path}")
            logger.info(f"🎵 Audio file: {audio_file_path}")
            logger.info(f"📋 Content file: {main_yaml_path}")
            logger.info(f"🎥 Output: {output_path}")

            # Load ASR data
            asr_data = self._load_asr_data(asr_file_path)
            if not asr_data:
                raise RuntimeError("Failed to load ASR data")

            # Load main content structure
            content_data = self._load_main_content(main_yaml_path)
            if not content_data:
                raise RuntimeError("Failed to load main content structure")

            # Get audio duration
            audio_duration = self._get_audio_duration(audio_file_path)
            if not audio_duration:
                raise RuntimeError("Failed to get audio duration")

            logger.info(f"⏱️ Audio duration: {audio_duration:.2f} seconds")

            # Create subtitle file
            subtitle_file = self._create_subtitle_file(asr_data, audio_duration)

            # Create video with images
            video_path = self._create_video_with_images(
                audio_file_path,
                subtitle_file,
                content_data,
                output_path,
                audio_duration,
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
                "fps": self.fps,
            }

        except Exception as e:
            logger.error(f"❌ Video generation failed: {e}")
            raise RuntimeError(f"Video generation failed: {e}")

    def _load_asr_data(self, asr_file_path: str) -> Dict[str, Any]:
        """Load ASR data from JSON file."""
        try:
            with open(asr_file_path, "r") as f:
                data = json.load(f)

            if not data.get("success"):
                raise RuntimeError("ASR data indicates failure")

            return data
        except Exception as e:
            logger.error(f"Failed to load ASR data: {e}")
            return None

    def _load_main_content(self, main_yaml_path: str) -> Dict[str, Any]:
        """Load main content structure from YAML file."""
        try:
            with open(main_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            logger.info(
                f"📋 Loaded content structure with {len(data.get('narration', []))} narration groups"
            )
            return data
        except Exception as e:
            logger.error(f"Failed to load main content: {e}")
            return None

    def _get_audio_duration(self, audio_file_path: str) -> float:
        """Get audio duration using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_file_path,
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

    def _create_subtitle_file(
        self, asr_data: Dict[str, Any], audio_duration: float
    ) -> str:
        """Create an ASS subtitle file from ASR data with speaker-specific styling."""
        try:
            # Create temporary ASS subtitle file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".ass", delete=False
            ) as f:
                subtitle_file = f.name

            segments = asr_data.get("segments", [])

            with open(subtitle_file, "w", encoding="utf-8") as f:
                # Write ASS header
                f.write("[Script Info]\n")
                f.write("Title: Generated Subtitles\n")
                f.write("ScriptType: v4.00+\n")
                f.write("WrapStyle: 1\n")
                f.write("ScaledBorderAndShadow: yes\n")
                f.write("YCbCr Matrix: TV.601\n\n")

                # Write styles section
                f.write("[V4+ Styles]\n")
                f.write(
                    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                )
                # Speaker00: White text with orange border
                f.write(
                    "Style: Speaker00,DejaVu Sans,36,&H00FFFFFF,&H000000FF,&H00008CFF,&H80000000,1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n"
                )
                # Speaker01: Orange text with white border
                f.write(
                    "Style: Speaker01,DejaVu Sans,36,&H00008CFF,&H000000FF,&H00FFFFFF,&H80000000,1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n\n"
                )

                # Write events section
                f.write("[Events]\n")
                f.write(
                    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
                )

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
                        f.write(
                            f"Dialogue: 0,{start_ass},{end_ass},{style},,0,0,0,,{word}\n"
                        )

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

    def _create_video_with_images(
        self,
        audio_file: str,
        subtitle_file: str,
        content_data: Dict[str, Any],
        output_path: str,
        audio_duration: float,
    ) -> str:
        """Create video using ffmpeg with generated images and subtitles."""
        try:
            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)

            # Get narration groups with images
            # The structure is: images.generated[].status and images.generated[].image_file
            images_section = content_data.get("images", {})
            if isinstance(images_section, dict) and "generated" in images_section:
                image_groups = images_section["generated"]
                logger.debug(
                    f"🔍 Found images.generated section with {len(image_groups)} groups"
                )
            else:
                # Fallback: try to find images in other locations
                logger.warning(
                    f"🔍 No images.generated section found, trying fallback locations"
                )
                image_groups = []

                # Try narration.generated if it exists
                narration_section = content_data.get("narration", {})
                if (
                    isinstance(narration_section, dict)
                    and "generated" in narration_section
                ):
                    image_groups = narration_section["generated"]
                    logger.debug(
                        f"🔍 Found narration.generated section with {len(image_groups)} groups"
                    )
                elif isinstance(narration_section, list):
                    # Try to find groups with status and image_file directly
                    image_groups = [
                        group
                        for group in narration_section
                        if group.get("image_file")
                        and group.get("status") == "generated"
                    ]
                    logger.debug(
                        f"🔍 Found {len(image_groups)} groups with images in narration list"
                    )

            logger.info(
                f"🎨 Found {len(image_groups)} image groups for video generation"
            )
            logger.debug(
                f"🔍 Content structure: images section type={type(images_section)}"
            )
            if isinstance(images_section, dict):
                logger.debug(f"🔍 Images section keys: {list(images_section.keys())}")
                if "generated" in images_section:
                    logger.debug(
                        f"🔍 Generated images count: {len(images_section['generated'])}"
                    )
                    # Log first few groups for debugging
                    for i, group in enumerate(images_section["generated"][:3]):
                        logger.debug(
                            f"🔍 Image Group {i}: status={group.get('status')}, image_file={group.get('image_file')}"
                        )

            if not image_groups:
                logger.warning("⚠️ No images found, falling back to black background")
                return self._create_video_with_ffmpeg_fallback(
                    audio_file, subtitle_file, output_path, audio_duration
                )

            # Create a simple approach: show each image for equal duration
            # In the future, this could be enhanced to use actual ASR timestamps
            num_images = len(image_groups)
            image_duration = audio_duration / num_images

            logger.info(f"⏱️ Each image will display for {image_duration:.2f} seconds")
            logger.debug(f"🎬 Processing {num_images} images for video generation:")

            # Create a temporary directory for intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)

                # Create individual video segments for each image
                video_segments = []
                for i, group in enumerate(image_groups):
                    image_path = group.get("image_file")
                    if not image_path or not Path(image_path).exists():
                        logger.warning(f"⚠️ Image file not found: {image_path}")
                        continue

                    # Log which image we're processing
                    image_name = Path(image_path).name
                    logger.debug(
                        f"   🖼️  Processing image {i+1}/{num_images}: {image_name}"
                    )

                    # Create a video segment for this image
                    segment_path = temp_dir_path / f"segment_{i:03d}.mp4"
                    self._create_image_segment(image_path, segment_path, image_duration)
                    video_segments.append(segment_path)

                    logger.debug(
                        f"   ✅ Created video segment {i+1}/{num_images}: {segment_path.name}"
                    )

                if not video_segments:
                    raise RuntimeError("No valid video segments created")

                logger.debug(
                    f"🎬 Successfully created {len(video_segments)} video segments"
                )

                # Create a file list for ffmpeg concat
                concat_list_path = temp_dir_path / "concat_list.txt"
                with open(concat_list_path, "w") as f:
                    for segment in video_segments:
                        f.write(f"file '{segment}'\n")

                # Concatenate all segments and add audio + subtitles
                cmd = [
                    "ffmpeg",
                    "-y",  # Overwrite output file
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_list_path),
                    "-i",
                    audio_file,
                    "-vf",
                    f"ass={subtitle_file}",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-preset",
                    "medium",
                    "-crf",
                    "23",
                    "-shortest",
                    output_path,
                ]

                logger.info(
                    f"🎬 Running ffmpeg concat command with {len(video_segments)} image segments..."
                )
                logger.debug(f"ffmpeg command: {' '.join(cmd)}")

                # Run ffmpeg
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)

                if not Path(output_path).exists():
                    raise RuntimeError("ffmpeg completed but output file not found")

                logger.info(f"✅ ffmpeg completed successfully with images")
                logger.debug(
                    f"🎉 Video generation complete! Output: {Path(output_path).name}"
                )
                return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed: {e}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise RuntimeError(f"ffmpeg failed: {e}")
        except Exception as e:
            logger.error(f"Video creation with images failed: {e}")
            raise RuntimeError(f"Video creation with images failed: {e}")

    def _create_image_segment(
        self, image_path: str, output_path: Path, duration: float
    ) -> None:
        """Create a video segment from a single image."""
        try:
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-loop",
                "1",
                "-i",
                image_path,
                "-t",
                str(duration),
                "-vf",
                f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            logger.debug(f"Created image segment: {output_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create image segment {image_path}: {e}")
            raise RuntimeError(f"Failed to create image segment: {e}")
        except Exception as e:
            logger.error(f"Failed to create image segment: {e}")
            raise RuntimeError(f"Failed to create image segment: {e}")

    def _create_image_filter_complex(
        self, image_groups: List[Dict], audio_duration: float
    ) -> str:
        """Create complex filter for image transitions based on ASR timing."""
        try:
            # For now, we'll create a simple approach: show each image for equal duration
            # In the future, this could be enhanced to use actual ASR timestamps
            num_images = len(image_groups)
            image_duration = audio_duration / num_images

            logger.info(f"⏱️ Each image will display for {image_duration:.2f} seconds")

            # Build the filter complex
            filters = []
            inputs = []

            # Add each image as an input
            for i, group in enumerate(image_groups):
                image_path = group.get("image_file")
                if not image_path or not Path(image_path).exists():
                    logger.warning(f"⚠️ Image file not found: {image_path}")
                    continue

                inputs.append(f"-loop 1 -t {image_duration} -i {image_path}")
                filters.append(
                    f"[{i}:v]scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:black[v{i}]"
                )

            if not inputs:
                raise RuntimeError("No valid images found for video generation")

            # Concatenate all images
            concat_inputs = "".join([f"[v{i}]" for i in range(len(inputs))])
            filters.append(f"{concat_inputs}concat=n={len(inputs)}:v=1:a=0[outv]")

            # Add subtitle overlay
            filters.append(f"[outv]ass={subtitle_file}[final]")

            filter_complex = ";".join(filters)

            logger.info(f"🔧 Created filter complex with {len(inputs)} image inputs")
            return filter_complex

        except Exception as e:
            logger.error(f"Failed to create image filter complex: {e}")
            raise RuntimeError(f"Failed to create image filter complex: {e}")

    def _create_video_with_ffmpeg_fallback(
        self,
        audio_file: str,
        subtitle_file: str,
        output_path: str,
        audio_duration: float,
    ) -> str:
        """Create video using ffmpeg with black background and subtitles (fallback)."""
        try:
            # Build ffmpeg command for fallback
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-f",
                "lavfi",
                "-i",
                f"color=black:size={self.width}x{self.height}:duration={audio_duration}",
                "-i",
                audio_file,
                "-vf",
                f"ass={subtitle_file}",
                "-c:a",
                "aac",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-shortest",
                output_path,
            ]

            logger.info(f"🎬 Running ffmpeg fallback command...")
            logger.debug(f"ffmpeg fallback command: {' '.join(cmd)}")

            # Run ffmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if not Path(output_path).exists():
                raise RuntimeError(
                    "ffmpeg fallback completed but output file not found"
                )

            logger.info(f"✅ ffmpeg fallback completed successfully")
            return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg fallback failed: {e}")
            logger.error(f"ffmpeg fallback stderr: {e.stderr}")
            raise RuntimeError(f"ffmpeg fallback failed: {e}")
        except Exception as e:
            logger.error(f"Video creation fallback failed: {e}")
            raise RuntimeError(f"Video creation fallback failed: {e}")

    def process_and_save(
        self,
        asr_file_path: str,
        audio_file_path: str,
        main_yaml_path: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """Process ASR data, audio, and content to generate video, then save to output path.

        This is a convenience method that combines generate_video and saves the result.

        Args:
            asr_file_path: Path to the ASR JSON file
            audio_file_path: Path to the audio file
            main_yaml_path: Path to the main.yaml content structure file
            output_path: Path where the output video should be saved

        Returns:
            Dictionary containing video generation results
        """
        return self.generate_video(
            asr_file_path, audio_file_path, main_yaml_path, output_path
        )

    def create_video(
        self,
        audio_path: str,
        timeline: List[Dict[str, Any]],
        subtitles_path: str,
        output_path: str,
        size: Tuple[int, int] = (1024, 1024),
        fps: int = 30,
    ) -> Dict[str, Any]:
        """Create video from audio, timeline, and optional subtitles.

        This method implements the interface required by the segment video generation.

        Args:
            audio_path: Path to the audio file
            timeline: List of dicts with image_path, start_ms, duration_ms, text
            subtitles_path: Path to VTT subtitles file (optional)
            output_path: Path where the output video should be saved
            size: Video resolution (width, height)
            fps: Video frame rate

        Returns:
            Dictionary containing video generation results
        """
        try:
            logger.info(f"🎬 Starting segment video generation...")
            logger.info(f"🎵 Audio: {audio_path}")
            logger.info(f"📊 Timeline: {len(timeline)} items")
            logger.info(f"📝 Subtitles: {subtitles_path}")
            logger.info(f"🎥 Output: {output_path}")

            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)

            # Get audio duration
            audio_duration = self._get_audio_duration(audio_path)
            if not audio_duration:
                raise RuntimeError("Failed to get audio duration")

            logger.info(f"⏱️ Audio duration: {audio_duration:.2f} seconds")

            # Create video with images from timeline
            video_path = self._create_video_from_timeline(
                audio_path,
                timeline,
                subtitles_path,
                output_path,
                audio_duration,
                size,
                fps,
            )

            logger.info(f"✅ Segment video generation completed successfully")
            logger.info(f"🎥 Video saved to: {video_path}")

            return {
                "success": True,
                "video_path": video_path,
                "duration": audio_duration,
                "resolution": f"{size[0]}x{size[1]}",
                "fps": fps,
            }

        except Exception as e:
            logger.error(f"❌ Segment video generation failed: {e}")
            raise RuntimeError(f"Segment video generation failed: {e}")

    def _create_video_from_timeline(
        self,
        audio_file: str,
        timeline: List[Dict[str, Any]],
        subtitle_file: str,
        output_path: str,
        audio_duration: float,
        size: Tuple[int, int],
        fps: int,
    ) -> str:
        """Create video using ffmpeg with timeline data."""
        try:
            width, height = size

            if not timeline:
                raise RuntimeError("No timeline items provided")

            logger.info(
                f"🎨 Processing {len(timeline)} timeline items for video generation"
            )

            # Create a temporary directory for intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)

                # Create individual video segments for each timeline item
                video_segments = []
                for i, item in enumerate(timeline):
                    item_type = item.get("type", "content")
                    image_path = item.get("image_path")
                    duration_ms = item.get("duration_ms", 0)
                    duration_seconds = duration_ms / 1000.0
                    text = item.get("text", "")

                    if duration_seconds <= 0:
                        logger.warning(
                            f"⚠️ Invalid duration for item {i}: {duration_ms}ms"
                        )
                        continue

                    # Handle different timeline item types
                    if image_path and Path(image_path).exists():
                        # Regular image segment
                        image_name = Path(image_path).name
                        logger.debug(
                            f"   🖼️  Processing timeline item {i+1}/{len(timeline)}: {image_name} ({duration_seconds:.2f}s)"
                        )

                        # Create a video segment for this image
                        segment_path = temp_dir_path / f"segment_{i:03d}.mp4"
                        self._create_image_segment(
                            image_path,
                            segment_path,
                            duration_seconds,
                            width,
                            height,
                            fps,
                        )
                        video_segments.append(segment_path)

                        logger.debug(
                            f"   ✅ Created video segment {i+1}/{len(timeline)}: {segment_path.name}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Skipping timeline item {i}: no valid image path"
                        )
                        continue

                if not video_segments:
                    raise RuntimeError("No valid video segments created")

                logger.debug(
                    f"🎬 Successfully created {len(video_segments)} video segments"
                )

                # Create a file list for ffmpeg concat
                concat_list_path = temp_dir_path / "concat_list.txt"
                with open(concat_list_path, "w") as f:
                    for segment in video_segments:
                        f.write(f"file '{segment}'\n")

                # Build ffmpeg command
                cmd = [
                    "ffmpeg",
                    "-y",  # Overwrite output file
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_list_path),
                    "-i",
                    audio_file,
                ]

                # Add subtitle filter if subtitles exist
                if subtitle_file and Path(subtitle_file).exists():
                    # Check if it's VTT or ASS format
                    if subtitle_file.endswith(".vtt"):
                        # For VTT files, we need to convert to ASS or use subtitles filter
                        # For now, we'll use the subtitles filter which supports VTT
                        cmd.extend(["-vf", f"subtitles={subtitle_file}"])
                    else:
                        # For ASS files, use the ass filter
                        cmd.extend(["-vf", f"ass={subtitle_file}"])

                # Add video encoding options
                cmd.extend(
                    [
                        "-c:v",
                        "libx264",
                        "-c:a",
                        "aac",
                        "-preset",
                        "medium",
                        "-crf",
                        "23",
                        "-shortest",
                        output_path,
                    ]
                )

                logger.info(
                    f"🎬 Running ffmpeg concat command with {len(video_segments)} timeline segments..."
                )
                logger.debug(f"ffmpeg command: {' '.join(cmd)}")

                # Run ffmpeg
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)

                if not Path(output_path).exists():
                    raise RuntimeError("ffmpeg completed but output file not found")

                logger.info(f"✅ ffmpeg completed successfully with timeline")
                logger.debug(
                    f"🎉 Video generation complete! Output: {Path(output_path).name}"
                )
                return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed: {e}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise RuntimeError(f"ffmpeg failed: {e}")
        except Exception as e:
            logger.error(f"Video creation from timeline failed: {e}")
            raise RuntimeError(f"Video creation from timeline failed: {e}")

    def _create_image_segment(
        self,
        image_path: str,
        output_path: Path,
        duration: float,
        width: int,
        height: int,
        fps: int,
    ) -> None:
        """Create a video segment from a single image with specified duration and resolution."""
        try:
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-loop",
                "1",
                "-i",
                image_path,
                "-t",
                str(duration),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            logger.debug(f"Created image segment: {output_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create image segment {image_path}: {e}")
            raise RuntimeError(f"Failed to create image segment: {e}")
        except Exception as e:
            logger.error(f"Failed to create image segment: {e}")
            raise RuntimeError(f"Failed to create image segment: {e}")

    def _create_title_segment(
        self,
        text: str,
        output_path: Path,
        duration: float,
        width: int,
        height: int,
        fps: int,
    ) -> None:
        """Create a video segment with black background, title text, and emojis."""
        try:
            # Parse the text to extract title and emojis
            # Format: "TITLE:title text|EMOJIS:emoji1 emoji2 emoji3 emoji4"
            title_text = ""
            emoji_text = ""

            if "TITLE:" in text and "|EMOJIS:" in text:
                parts = text.split("|EMOJIS:")
                title_text = parts[0].replace("TITLE:", "").strip()
                emoji_text = parts[1].strip()
            else:
                # Fallback if format is unexpected
                title_text = text
                emoji_text = ""

            # Escape special characters in text for ffmpeg
            def escape_text(text):
                # Escape single quotes and backslashes for ffmpeg
                return text.replace("\\", "\\\\").replace("'", "\\'")

            escaped_title = escape_text(title_text)
            escaped_emoji = escape_text(emoji_text)

            # Create a simpler approach using drawtext filter
            # First create the background, then add text overlays
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-f",
                "lavfi",
                "-i",
                f"color=black:size={width}x{height}:duration={duration}",
                "-vf",
                f"drawtext=text='{escaped_title}':fontsize=48:fontcolor=orange:"
                f"x=(w-tw)/2:y=(h-th)/2-50:borderw=3:bordercolor=white,"
                f"drawtext=text='{escaped_emoji}':fontsize=36:fontcolor=white:"
                f"x=(w-tw)/2:y=(h-th)/2+50",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            logger.debug(f"Created title segment: {output_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create title segment: {e}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise RuntimeError(f"Failed to create title segment: {e}")
        except Exception as e:
            logger.error(f"Failed to create title segment: {e}")
            raise RuntimeError(f"Failed to create title segment: {e}")
