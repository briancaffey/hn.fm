"""Image generation service for hn.fm."""

import base64
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
import requests
from PIL import Image
import io

from ..utils.config import config_manager

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating images using the image generation API."""

    def __init__(self):
        """Initialize the image generation service."""
        self.base_url = config_manager.get("image_generation.base_url")
        self.default_height = config_manager.get("image_generation.default_height", 1024)
        self.default_width = config_manager.get("image_generation.default_width", 1024)
        self.default_cfg_scale = config_manager.get("image_generation.default_cfg_scale", 5)
        self.default_mode = config_manager.get("image_generation.default_mode", "base")
        self.default_steps = config_manager.get("image_generation.default_steps", 50)
        self.default_samples = config_manager.get("image_generation.default_samples", 1)
        self.output_directory = config_manager.get("image_generation.output_directory", "images")

    def generate_image(
        self,
        prompt: str,
        height: Optional[int] = None,
        width: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        mode: Optional[str] = None,
        steps: Optional[int] = None,
        samples: Optional[int] = None,
        seed: Optional[int] = None,
        image: Optional[str] = None,
    ) -> Dict[str, any]:
        """Generate an image using the image generation API.

        Args:
            prompt: Text prompt for image generation
            height: Image height (defaults to config value)
            width: Image width (defaults to config value)
            cfg_scale: CFG scale for generation (defaults to config value)
            mode: Generation mode (defaults to config value)
            steps: Number of generation steps (defaults to config value)
            samples: Number of samples to generate (defaults to config value)
            seed: Random seed for generation
            image: Base64 encoded image for img2img (optional)

        Returns:
            Dictionary containing generation results
        """
        # Use defaults from config if not specified
        height = height or self.default_height
        width = width or self.default_width
        cfg_scale = cfg_scale or self.default_cfg_scale
        mode = mode or self.default_mode
        steps = steps or self.default_steps
        samples = samples or self.default_samples

        payload = {
            "prompt": prompt,
            "height": height,
            "width": width,
            "cfg_scale": cfg_scale,
            "mode": mode,
            "image": image,
            "samples": samples,
            "seed": seed or 0,
            "steps": steps,
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
        }

        try:
            # Show the beginning of the prompt for context
            prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
            logger.debug(f"🎨 Generating image with prompt: {prompt_preview}")
            logger.debug(f"   📐 Settings: {width}x{height}, {steps} steps, CFG {cfg_scale}")

            response = requests.post(
                f"{self.base_url}/v1/infer",
                json=payload,
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()

            result = response.json()
            artifacts_count = len(result.get('artifacts', []))
            logger.info(f"✅ Successfully generated {artifacts_count} image(s)")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to generate image: {e}")
            raise RuntimeError(f"Image generation failed: {e}")

    def save_image_from_base64(
        self,
        base64_data: str,
        output_path: Union[str, Path],
        filename: Optional[str] = None,
    ) -> Path:
        """Save a base64 encoded image to disk.

        Args:
            base64_data: Base64 encoded image data
            output_path: Directory or full path to save the image
            filename: Optional filename (if not provided, will generate one)

        Returns:
            Path to the saved image file
        """
        try:
            # Decode base64 data
            image_data = base64.b64decode(base64_data)

            # Create PIL Image object
            image = Image.open(io.BytesIO(image_data))

            # Determine output path
            if filename:
                if Path(output_path).is_dir():
                    output_file = Path(output_path) / filename
                else:
                    output_file = Path(output_path)
            else:
                # Generate filename based on timestamp
                import time
                timestamp = int(time.time())
                if Path(output_path).is_dir():
                    output_file = Path(output_path) / f"generated_image_{timestamp}.png"
                else:
                    output_file = Path(output_path)

            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Save image
            image.save(output_file, "PNG")
            logger.debug(f"💾 Successfully saved image to: {output_file}")

            return output_file

        except Exception as e:
            logger.error(f"❌ Failed to save image: {e}")
            raise RuntimeError(f"Failed to save image: {e}")

    def generate_and_save_image(
        self,
        prompt: str,
        output_dir: Union[str, Path],
        filename: Optional[str] = None,
        **kwargs,
    ) -> Path:
        """Generate an image and save it to disk.

        Args:
            prompt: Text prompt for image generation
            output_dir: Directory to save the generated image
            filename: Optional filename for the image
            **kwargs: Additional arguments for generate_image

        Returns:
            Path to the saved image file
        """
        # Generate the image
        result = self.generate_image(prompt, **kwargs)

        # Get the first artifact
        artifacts = result.get("artifacts", [])
        if not artifacts:
            raise RuntimeError("No images generated")

        # Save the first image
        base64_data = artifacts[0]["base64"]
        return self.save_image_from_base64(base64_data, output_dir, filename)

    def generate_images_for_script(
        self,
        script_segments: List[Dict[str, any]],
        output_dir: Union[str, Path],
        **kwargs,
    ) -> List[Path]:
        """Generate images for each script segment.

        Args:
            script_segments: List of script segments with text content
            output_dir: Directory to save generated images
            **kwargs: Additional arguments for image generation

        Returns:
            List of paths to generated images
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        generated_images = []
        total_segments = len(script_segments)

        logger.info(f"🎬 Starting image generation for {total_segments} script segments")
        logger.debug(f"📁 Output directory: {output_path}")

        for i, segment in enumerate(script_segments):
            try:
                # Extract text content from segment
                text_content = segment.get("text", "")
                if not text_content:
                    logger.warning(f"⚠️ Segment {i} has no text content, skipping")
                    continue

                # Generate prompt from text content
                prompt = self._create_image_prompt(text_content)

                # Show what we're generating for this segment
                text_preview = text_content[:80] + "..." if len(text_content) > 80 else text_content
                logger.debug(f"🖼️  Generating image {i+1}/{total_segments}")
                logger.debug(f"   📝 Text: {text_preview}")
                logger.debug(f"   🎯 Prompt: {prompt[:80]}...")

                # Generate and save image
                filename = f"segment_{i:03d}.png"
                image_path = self.generate_and_save_image(
                    prompt, output_path, filename, **kwargs
                )
                generated_images.append(image_path)

                logger.info(f"✅ Completed image {i+1}/{total_segments}: {image_path.name}")

            except Exception as e:
                logger.error(f"❌ Failed to generate image for segment {i}: {e}")
                # Continue with next segment
                continue

        logger.info(f"🎉 Image generation complete! Generated {len(generated_images)}/{total_segments} images")
        return generated_images

    def _create_image_prompt(self, text_content: str) -> str:
        """Create an image prompt from text content.

        Args:
            text_content: Text content to convert to image prompt

        Returns:
            Image generation prompt
        """
        # Simple prompt creation - can be enhanced with LLM later
        # For now, just use the first sentence or a truncated version
        sentences = text_content.split('.')
        first_sentence = sentences[0].strip()

        # Limit length and clean up
        if len(first_sentence) > 100:
            first_sentence = first_sentence[:100] + "..."

        # Add some context to make it more image-friendly
        prompt = f"a professional, high-quality image representing: {first_sentence}"

        return prompt

    def health_check(self) -> bool:
        """Check if the image generation service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/v1/health/ready", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
