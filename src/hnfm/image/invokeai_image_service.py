"""InvokeAI image generation service wrapper for hn.fm."""

import base64
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Union
from PIL import Image
import io
import requests

from ..utils.config import config_manager
from .invokeai import InvokeAIClient, HnfmImageProcessor

logger = logging.getLogger(__name__)


class InvokeAIImageService:
    """InvokeAI-based image generation service that matches the ImageGenerationService interface."""

    def __init__(self):
        """Initialize the InvokeAI image generation service."""
        self.invokeai_config = config_manager.get("image_generation.invokeai", {})
        self.base_url = self.invokeai_config.get("base_url", "http://127.0.0.1:9090")
        # Board ID is optional - if not provided, we'll use None and let InvokeAI handle it
        self.board_id = self.invokeai_config.get("board_id")

        # Default values from config
        self.default_height = config_manager.get(
            "image_generation.default_height", 1024
        )
        self.default_width = config_manager.get("image_generation.default_width", 1024)
        self.default_cfg_scale = config_manager.get(
            "image_generation.default_cfg_scale", 5
        )
        self.default_mode = config_manager.get("image_generation.default_mode", "base")
        self.default_steps = config_manager.get("image_generation.default_steps", 50)
        self.default_samples = config_manager.get("image_generation.default_samples", 1)
        self.output_directory = config_manager.get(
            "image_generation.output_directory", "images"
        )

        # Initialize InvokeAI client and processor
        self.client = InvokeAIClient(self.base_url)
        self.processor = HnfmImageProcessor(self.base_url)

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
        """Generate an image using InvokeAI.

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

        try:
            # Show the beginning of the prompt for context
            prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
            logger.debug(f"🎨 Generating image with InvokeAI: {prompt_preview}")
            logger.debug(
                f"   📐 Settings: {width}x{height}, {steps} steps, CFG {cfg_scale}"
            )

            # For now, we'll generate one image at a time (samples=1)
            # InvokeAI workflow doesn't directly support multiple samples in the same way
            generated_images = []

            for i in range(samples):
                # Modify the workflow with the prompt
                # For text-to-image generation, we don't need an image name
                workflow = self.processor.modify_workflow(prompt, "")

                # Update workflow parameters based on input
                # Always update the flux_denoise node with the provided parameters
                denoise_node = workflow["batch"]["graph"]["nodes"][
                    "flux_denoise:vKUCA9K7C0"
                ]

                # Update dimensions if provided
                if height and width:
                    denoise_node["width"] = width
                    denoise_node["height"] = height

                # Always update cfg_scale and steps
                denoise_node["cfg_scale"] = cfg_scale
                denoise_node["num_steps"] = steps
                denoise_node["guidance"] = cfg_scale

                if seed is not None:
                    # Update seed in both seed node and denoise node
                    seed_node = workflow["batch"]["graph"]["nodes"]["seed:Lcn2HpBb1d"]
                    seed_node["value"] = seed
                    denoise_node["seed"] = seed

                # Submit the workflow
                batch_info = self.client.submit_workflow(workflow)
                if not batch_info:
                    raise RuntimeError("Failed to submit workflow to InvokeAI")

                # Wait for completion
                queue_id = batch_info.get("queue_id", "default")
                batch_id = batch_info.get("batch_id")

                if not self.client.wait_for_batch_completion(
                    queue_id, batch_id, timeout=600
                ):
                    raise RuntimeError("InvokeAI batch processing timed out")

                # Get batch results - try to find session_id from queue
                session_id = batch_info.get("session_id")
                if not session_id:
                    # Try to get session_id from queue item
                    item_ids = batch_info.get("item_ids", [])
                    if item_ids:
                        item_id = item_ids[0]  # Get first item ID
                        item_response = self.client.session.get(
                            f"{self.client.base_url}/api/v1/queue/{queue_id}/i/{item_id}"
                        )
                        if item_response.status_code == 200:
                            item_data = item_response.json()
                            session_id = item_data.get("session_id")
                            logger.info(f"Found session_id from queue item: {session_id}")

                item_ids = batch_info.get("item_ids", [])
                results = self.client.get_batch_results(queue_id, batch_id, session_id, item_ids)
                if not results:
                    raise RuntimeError("Failed to get batch results from InvokeAI")

                # Extract image information from results
                # The exact structure depends on InvokeAI's response format
                # We'll need to adapt this based on the actual response structure
                if "items" in results and results["items"]:
                    for item in results["items"]:
                        if "images" in item and item["images"]:
                            for img_info in item["images"]:
                                image_name = img_info.get("image_name")
                                if image_name:
                                    # Download the image to get base64 data
                                    temp_path = (
                                        f"/tmp/invokeai_temp_{int(time.time())}_{i}.png"
                                    )
                                    if self.client.download_image(
                                        image_name, temp_path
                                    ):
                                        # Read the image and convert to base64
                                        with open(temp_path, "rb") as f:
                                            image_data = f.read()
                                        base64_data = base64.b64encode(
                                            image_data
                                        ).decode("utf-8")

                                        generated_images.append(
                                            {
                                                "base64": base64_data,
                                                "seed": seed or 0,
                                                "width": width,
                                                "height": height,
                                                "cfg_scale": cfg_scale,
                                                "steps": steps,
                                            }
                                        )

                                        # Clean up temp file
                                        try:
                                            os.remove(temp_path)
                                        except:
                                            pass

                                        break  # Only take the first image from this item
                            break  # Only process the first item

            if not generated_images:
                raise RuntimeError("No images were generated by InvokeAI")

            logger.info(
                f"✅ Successfully generated {len(generated_images)} image(s) with InvokeAI"
            )

            # Return in the same format as the original service
            return {"artifacts": generated_images, "status": "success"}

        except requests.exceptions.Timeout:
            logger.error("❌ InvokeAI request timed out")
            raise RuntimeError("InvokeAI request timed out - service may be overloaded")
        except requests.exceptions.ConnectionError:
            logger.error("❌ Failed to connect to InvokeAI service")
            raise RuntimeError(
                "Failed to connect to InvokeAI service - check if service is running"
            )
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ InvokeAI HTTP error: {e}")
            raise RuntimeError(f"InvokeAI HTTP error: {e}")
        except KeyError as e:
            logger.error(f"❌ InvokeAI response format error: {e}")
            raise RuntimeError(
                f"InvokeAI response format error - unexpected response structure: {e}"
            )
        except FileNotFoundError as e:
            logger.error(f"❌ File operation failed: {e}")
            raise RuntimeError(f"File operation failed: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to generate image with InvokeAI: {e}")
            raise RuntimeError(f"InvokeAI image generation failed: {e}")

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

        except FileNotFoundError as e:
            logger.error(f"❌ Output directory not found: {e}")
            raise RuntimeError(f"Output directory not found: {e}")
        except PermissionError as e:
            logger.error(f"❌ Permission denied when saving image: {e}")
            raise RuntimeError(f"Permission denied when saving image: {e}")
        except ValueError as e:
            logger.error(f"❌ Invalid image data: {e}")
            raise RuntimeError(f"Invalid image data: {e}")
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
        try:
            # Generate the image
            result = self.generate_image(prompt, **kwargs)

            # Get the first artifact
            artifacts = result.get("artifacts", [])
            if not artifacts:
                raise RuntimeError("No images generated")

            # Save the first image
            base64_data = artifacts[0]["base64"]
            return self.save_image_from_base64(base64_data, output_dir, filename)

        except KeyError as e:
            logger.error(f"❌ Missing required data in generation result: {e}")
            raise RuntimeError(f"Missing required data in generation result: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to generate and save image: {e}")
            raise RuntimeError(f"Failed to generate and save image: {e}")

    def health_check(self) -> bool:
        """Check if the InvokeAI service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            return self.client.test_connection()
        except Exception as e:
            logger.warning(f"InvokeAI health check failed: {e}")
            return False
