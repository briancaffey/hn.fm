"""Content manager for hn.fm video content structure."""

import yaml
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ContentManager:
    """Manages the main content YAML file for video generation."""

    def __init__(self):
        """Initialize the content manager."""
        pass

    def create_main_content_structure(
        self, title: str, script: str, tts_lines: List[str], story_dir: Path, **kwargs
    ) -> Path:
        """Create the main content YAML structure.

        Args:
            title: Story title
            script: Full script text
            tts_lines: List of TTS lines
            story_dir: Story output directory
            **kwargs: Additional metadata

        Returns:
            Path to the created main.yaml file
        """
        try:
            # Create content directory
            content_dir = story_dir / "content"
            content_dir.mkdir(parents=True, exist_ok=True)

            # Create the main content structure
            content_data = {
                "metadata": {
                    "title": title,
                    "created_at": datetime.now().isoformat(),
                    "script_length": len(script),
                    "tts_lines_count": len(tts_lines),
                    **kwargs,
                },
                "script": {"full_text": script, "tts_lines": tts_lines},
                "narration": [],
                "images": {
                    "style": kwargs.get("image_style", "detailed cartoon style"),
                    "generated": [],
                    "pending": [],
                },
                "audio": {"tts_generated": False, "files": [], "duration": None},
                "video": {"generated": False, "file": None, "duration": None},
            }

            # Group TTS lines into narration pairs
            narration_groups = self._group_tts_lines(tts_lines)
            content_data["narration"] = narration_groups

            # Mark images as pending
            content_data["images"]["pending"] = [
                {
                    "group_id": i,
                    "lines": group["lines"],
                    "status": "pending",
                    "image_prompt": None,
                    "image_file": None,
                }
                for i, group in enumerate(narration_groups)
            ]

            # Save to main.yaml
            main_yaml_path = content_dir / "main.yaml"
            with open(main_yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    content_data,
                    f,
                    default_flow_style=False,
                    indent=2,
                    allow_unicode=True,
                    sort_keys=False,
                )

            logger.info(f"Created main content structure: {main_yaml_path}")
            return main_yaml_path

        except Exception as e:
            logger.error(f"Failed to create main content structure: {e}")
            raise RuntimeError(f"Content structure creation failed: {e}")

    def _group_tts_lines(self, tts_lines: List[str]) -> List[Dict[str, Any]]:
        """Group TTS lines into pairs for narration.

        Args:
            tts_lines: List of TTS lines

        Returns:
            List of narration groups
        """
        groups = []

        for i in range(0, len(tts_lines), 2):
            group_lines = tts_lines[i : i + 2]
            group = {
                "group_id": len(groups),
                "lines": group_lines,
                "speaker_tags": [f"[S{i+1}]" for i in range(len(group_lines))],
                "start_time": None,  # Will be filled by ASR
                "end_time": None,  # Will be filled by ASR
                "duration": None,  # Will be filled by ASR
            }
            groups.append(group)

        return groups

    def load_main_content(self, story_dir: Path) -> Dict[str, Any]:
        """Load the main content YAML file.

        Args:
            story_dir: Story output directory

        Returns:
            Content data dictionary
        """
        main_yaml_path = story_dir / "content" / "main.yaml"

        if not main_yaml_path.exists():
            raise FileNotFoundError(f"Main content file not found: {main_yaml_path}")

        try:
            with open(main_yaml_path, "r", encoding="utf-8") as f:
                content_data = yaml.safe_load(f)

            logger.info(f"Loaded main content from: {main_yaml_path}")
            return content_data

        except Exception as e:
            logger.error(f"Failed to load main content: {e}")
            raise RuntimeError(f"Content loading failed: {e}")

    def save_main_content(self, content_data: Dict[str, Any], story_dir: Path) -> Path:
        """Save the main content YAML file.

        Args:
            content_data: Content data to save
            story_dir: Story output directory

        Returns:
            Path to the saved file
        """
        try:
            content_dir = story_dir / "content"
            content_dir.mkdir(parents=True, exist_ok=True)

            main_yaml_path = content_dir / "main.yaml"
            with open(main_yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    content_data,
                    f,
                    default_flow_style=False,
                    indent=2,
                    allow_unicode=True,
                    sort_keys=False,
                )

            logger.info(f"Saved main content to: {main_yaml_path}")
            return main_yaml_path

        except Exception as e:
            logger.error(f"Failed to save main content: {e}")
            raise RuntimeError(f"Content saving failed: {e}")

    def update_asr_timestamps(
        self, story_dir: Path, asr_results: Dict[str, Any]
    ) -> Path:
        """Update the main content with ASR timestamps.

        Args:
            story_dir: Story output directory
            asr_results: ASR processing results

        Returns:
            Path to the updated file
        """
        try:
            content_data = self.load_main_content(story_dir)

            # Extract timestamps from ASR results
            segments = asr_results.get("segments", [])

            # Update narration groups with timestamps
            for group in content_data["narration"]:
                group_lines = group["lines"]

                # Find matching segments by text content
                matching_segments = []
                for segment in segments:
                    segment_text = segment.get("text", "").strip()
                    for line in group_lines:
                        if line.strip() in segment_text or segment_text in line.strip():
                            matching_segments.append(segment)
                            break

                if matching_segments:
                    # Calculate group timing
                    start_times = [s.get("start", 0) for s in matching_segments]
                    end_times = [s.get("end", 0) for s in matching_segments]

                    group["start_time"] = min(start_times) if start_times else None
                    group["end_time"] = max(end_times) if end_times else None

                    if (
                        group["start_time"] is not None
                        and group["end_time"] is not None
                    ):
                        group["duration"] = group["end_time"] - group["start_time"]

            # Save updated content
            return self.save_main_content(content_data, story_dir)

        except Exception as e:
            logger.error(f"Failed to update ASR timestamps: {e}")
            raise RuntimeError(f"ASR timestamp update failed: {e}")

    def update_image_prompts(
        self, story_dir: Path, image_prompts: List[Dict[str, Any]]
    ) -> Path:
        """Update the main content with generated image prompts.

        Args:
            story_dir: Story output directory
            image_prompts: List of image prompts with group_id

        Returns:
            Path to the updated file
        """
        try:
            content_data = self.load_main_content(story_dir)

            # Update pending images with prompts
            for prompt_data in image_prompts:
                group_id = prompt_data.get("group_id")
                prompt = prompt_data.get("prompt")

                if group_id is not None and prompt:
                    # Find the pending image for this group
                    for pending_image in content_data["images"]["pending"]:
                        if pending_image["group_id"] == group_id:
                            pending_image["image_prompt"] = prompt
                            pending_image["status"] = "prompt_ready"
                            break

            # Save updated content
            return self.save_main_content(content_data, story_dir)

        except Exception as e:
            logger.error(f"Failed to update image prompts: {e}")
            raise RuntimeError(f"Image prompt update failed: {e}")

    def update_generated_images(self, story_dir: Path, image_files: List[Path]) -> Path:
        """Update the main content with generated image files.

        Args:
            story_dir: Story output directory
            image_files: List of generated image file paths

        Returns:
            Path to the updated file
        """
        try:
            content_data = self.load_main_content(story_dir)

            # Update pending images with file paths
            for i, image_file in enumerate(image_files):
                if i < len(content_data["images"]["pending"]):
                    pending_image = content_data["images"]["pending"][i]
                    pending_image["image_file"] = str(image_file)
                    pending_image["status"] = "generated"

                    # Move to generated list
                    content_data["images"]["generated"].append(pending_image)

            # Remove generated images from pending
            content_data["images"]["pending"] = [
                img
                for img in content_data["images"]["pending"]
                if img["status"] != "generated"
            ]

            # Save updated content
            return self.save_main_content(content_data, story_dir)

        except Exception as e:
            logger.error(f"Failed to update generated images: {e}")
            raise RuntimeError(f"Generated image update failed: {e}")
