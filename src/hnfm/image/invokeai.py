import os
import json
import time
import logging
import requests
import mimetypes
import copy
from pathlib import Path
from typing import Dict, Any, Optional, List
import argparse

BOARD_ID = "4a247625-0a09-4577-967b-53c118cce2b4"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class InvokeAIClient:
    """Client for interacting with InvokeAI API."""

    def __init__(self, base_url: str = "http://127.0.0.1:9090"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def test_connection(self) -> bool:
        """Test if InvokeAI is running and accessible."""
        try:
            # Use the queue status endpoint to test connectivity
            response = self.session.get(f"{self.base_url}/api/v1/queue/default/status")
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def upload_image(self, image_path: str, board_id: str = None) -> Optional[str]:
        """
        Uploads an image to InvokeAI and returns the image name.

        Args:
            image_path (str): Path to the image file
            board_id (str): ID of the board to upload to (optional)

        Returns:
            str: The image name returned by InvokeAI, or None if upload failed
        """
        upload_url = f"{self.base_url}/api/v1/images/upload"
        params = {
            "image_category": "user",
            "is_intermediate": "false",
            "crop_visible": "false",
        }

        # Add board_id to params if provided
        if board_id:
            params["board_id"] = board_id

        try:
            # Get the MIME type of the image
            mime_type, _ = mimetypes.guess_type(image_path)
            if mime_type is None:
                mime_type = "image/png"  # Default to PNG if guess fails

            # Prepare the file for upload
            with open(image_path, "rb") as f:
                files = {
                    "file": (os.path.basename(image_path), f, mime_type),
                }

                # Make the request
                response = self.session.post(
                    upload_url,
                    params=params,
                    files=files,
                    headers={"accept": "application/json"},
                )

                response.raise_for_status()
                result = response.json()
                image_name = result.get("image_name")
                logger.info(f"Uploaded image: {image_name}")
                return image_name

        except Exception as e:
            logger.error(f"Error uploading image to InvokeAI: {e}")
            return None

    def submit_workflow(
        self, workflow_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Submits the workflow data to the InvokeAI API endpoint.

        Args:
            workflow_data (dict): The workflow data to submit

        Returns:
            dict: Batch information on success, None on failure
        """
        api_endpoint = f"{self.base_url}/api/v1/queue/default/enqueue_batch"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        logger.info(f"Submitting workflow to InvokeAI API at {api_endpoint}...")

        try:
            response = self.session.post(
                api_endpoint, json=workflow_data, headers=headers, timeout=60
            )

            # Check for HTTP errors
            response.raise_for_status()

            logger.info("Workflow submitted successfully to the queue!")
            logger.info(f"API Response Status Code: {response.status_code}")

            try:
                response_json = response.json()
                logger.info("Workflow queued successfully")

                # Extract batch information
                batch_info = {
                    "batch_id": response_json.get("batch", {}).get("batch_id"),
                    "item_ids": response_json.get("item_ids", []),
                    "queue_id": response_json.get("queue_id"),
                    "session_id": response_json.get("batch", {}).get("session_id"),
                    "response": response_json,
                }

                logger.info(
                    f"Batch ID: {batch_info['batch_id']}, Item IDs: {batch_info['item_ids']}"
                )
                return batch_info

            except json.JSONDecodeError:
                logger.info(f"API Response (non-JSON): {response.text}")
                return None

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Could not connect to the InvokeAI server at {self.base_url}")
            logger.error(f"Details: {e}")
            return None
        except requests.exceptions.Timeout:
            logger.error(
                "The request to the InvokeAI server timed out after 60 seconds"
            )
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"InvokeAI API request failed with status code {e.response.status_code}"
            )
            logger.error(f"URL: {e.request.url}")
            try:
                error_json = e.response.json()
                logger.error(f"Error Response: {json.dumps(error_json, indent=2)}")
            except json.JSONDecodeError:
                logger.error(f"Error Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during API submission: {e}")
            return None

    def get_queue_status(self) -> Optional[Dict[str, Any]]:
        """Get the current queue status."""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/queue/default/status")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get queue status: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return None

    def wait_for_completion(self, timeout: int = 600) -> bool:
        """
        Wait for the queue to complete processing.

        Args:
            timeout (int): Maximum time to wait in seconds

        Returns:
            bool: True if processing completed, False if timed out
        """
        logger.info(f"Waiting for queue completion (timeout: {timeout}s)...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_queue_status()
            if status:
                queue_size = status.get("queue_size", 0)
                if queue_size == 0:
                    logger.info("Queue processing completed!")
                    return True
                else:
                    logger.info(f"Queue size: {queue_size}, waiting...")

            time.sleep(5)

        logger.error(f"Queue processing timed out after {timeout} seconds")
        return False

    def download_image(
        self, image_name: str, output_path: str, max_retries: int = 3
    ) -> bool:
        """
        Download an image from InvokeAI with retry logic.

        Args:
            image_name (str): Name of the image to download
            output_path (str): Path where to save the image
            max_retries (int): Maximum number of retry attempts

        Returns:
            bool: True if download successful, False otherwise
        """
        for attempt in range(max_retries):
            try:
                # Try to download the image directly first
                download_url = f"{self.base_url}/api/v1/images/i/{image_name}/full"
                response = self.session.get(download_url)

                if response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    logger.info(f"Downloaded image: {output_path}")
                    return True
                else:
                    logger.warning(
                        f"Download attempt {attempt + 1}/{max_retries} failed with status {response.status_code}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(2**attempt)  # Exponential backoff: 1s, 2s, 4s
                        continue
                    else:
                        logger.error(
                            f"Failed to download image after {max_retries} attempts: {response.status_code}"
                        )
                        return False

            except Exception as e:
                logger.warning(
                    f"Download attempt {attempt + 1}/{max_retries} failed with error: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
                else:
                    logger.error(
                        f"Failed to download image after {max_retries} attempts: {e}"
                    )
                    return False

        return False

    def get_recent_images(
        self, limit: int = 10, board_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent images from InvokeAI.

        Args:
            limit (int): Maximum number of images to return
            board_id (str): Optional board ID to filter images by
        """
        try:
            params = {"limit": limit}
            if board_id:
                params["board_id"] = board_id

            response = self.session.get(
                f"{self.base_url}/api/v1/images/", params=params
            )
            if response.status_code == 200:
                return response.json().get("items", [])
            else:
                logger.error(f"Failed to get recent images: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting recent images: {e}")
            return []

    def get_board_images(self, board_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get images from a specific board.

        Args:
            board_id (str): The board ID to get images from
            limit (int): Maximum number of images to return

        Returns:
            List[Dict]: List of image information from the board
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/boards/{board_id}/images?limit={limit}"
            )
            if response.status_code == 200:
                return response.json().get("items", [])
            else:
                logger.error(f"Failed to get board images: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting board images: {e}")
            return []

    def get_batch_status(
        self, queue_id: str, batch_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the status of a specific batch."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/queue/{queue_id}/b/{batch_id}/status"
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get batch status: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting batch status: {e}")
            return None

    def wait_for_batch_completion(
        self, queue_id: str, batch_id: str, timeout: int = 600
    ) -> bool:
        """
        Wait for a specific batch to complete processing.

        Args:
            queue_id (str): The queue ID
            batch_id (str): The batch ID to monitor
            timeout (int): Maximum time to wait in seconds

        Returns:
            bool: True if batch completed successfully, False if timed out or failed
        """
        logger.info(f"Waiting for batch {batch_id} completion (timeout: {timeout}s)...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            batch_status = self.get_batch_status(queue_id, batch_id)

            if batch_status:
                # Check if batch is complete based on counts
                completed = batch_status.get("completed", 0)
                failed = batch_status.get("failed", 0)
                total = batch_status.get("total", 0)

                if completed > 0 and completed == total:
                    logger.info(
                        f"Batch {batch_id} completed successfully ({completed}/{total})"
                    )
                    return True
                elif failed > 0:
                    logger.error(f"Batch {batch_id} failed ({failed}/{total})")
                    return False
                else:
                    pending = batch_status.get("pending", 0)
                    in_progress = batch_status.get("in_progress", 0)
                    logger.info(
                        f"Batch {batch_id} status: {pending} pending, {in_progress} in progress, {completed} completed, waiting..."
                    )

            time.sleep(2)

        logger.error(f"Batch {batch_id} timed out after {timeout} seconds")
        return False

    def get_batch_results(
        self,
        queue_id: str,
        batch_id: str,
        session_id: str = None,
        item_ids: List[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the results of a completed batch by finding the session and extracting image results.

        Args:
            queue_id (str): The queue ID
            batch_id (str): The batch ID to get results for
            session_id (str): The session ID (if available from batch submission)
            item_ids (List[int]): The item IDs from the batch submission

        Returns:
            dict: Batch results including generated images or None if failed
        """
        try:
            # If we have item_ids, try to get the session data directly from the queue item
            if item_ids:
                for item_id in item_ids:
                    item_response = self.session.get(
                        f"{self.base_url}/api/v1/queue/{queue_id}/i/{item_id}"
                    )

                    if item_response.status_code == 200:
                        item_data = item_response.json()
                        if "session" in item_data:
                            session = item_data["session"]
                            results = session.get("results", {})

                            # Look for image outputs in the results
                            images = []
                            for node_id, result in results.items():
                                if result.get("type") == "image_output":
                                    image_info = result.get("image", {})
                                    if "image_name" in image_info:
                                        images.append(
                                            {
                                                "image_name": image_info["image_name"],
                                                "width": result.get("width", 1024),
                                                "height": result.get("height", 1024),
                                                "session_id": item_data.get(
                                                    "session_id"
                                                ),
                                                "node_id": node_id,
                                            }
                                        )

                            if images:
                                logger.info(
                                    f"Found {len(images)} images in queue item {item_id}"
                                )
                                return {"items": [{"images": images}]}

            # Fallback: try to find session_id from queue list
            if session_id:
                logger.info(f"Using provided session_id: {session_id}")
            else:
                # Try to find the session_id from the queue list
                session_response = self.session.get(
                    f"{self.base_url}/api/v1/queue/{queue_id}/list?limit=100"
                )

                if session_response.status_code != 200:
                    logger.error(
                        f"Failed to get queue list: {session_response.status_code}"
                    )
                    return None

                session_data = session_response.json()

                # Find the session with this batch_id
                for item in session_data.get("items", []):
                    if item.get("batch_id") == batch_id:
                        session_id = item.get("session_id")
                        break

                if not session_id:
                    logger.error(f"No session found for batch_id: {batch_id}")
                    return None

            # Get the session data to find the results
            session_detail_response = self.session.get(
                f"{self.base_url}/api/v1/queue/{queue_id}/list?session_id={session_id}"
            )

            if session_detail_response.status_code != 200:
                logger.error(
                    f"Failed to get session detail: {session_detail_response.status_code}"
                )
                return None

            session_detail_data = session_detail_response.json()

            # Find the session with results
            images = []
            for item in session_detail_data.get("items", []):
                if item.get("session_id") == session_id and "session" in item:
                    session = item["session"]
                    results = session.get("results", {})

                    # Look for image outputs in the results
                    for node_id, result in results.items():
                        if result.get("type") == "image_output":
                            image_info = result.get("image", {})
                            if "image_name" in image_info:
                                images.append(
                                    {
                                        "image_name": image_info["image_name"],
                                        "width": result.get("width", 1024),
                                        "height": result.get("height", 1024),
                                        "session_id": session_id,
                                        "node_id": node_id,
                                    }
                                )
                    break

            if not images:
                logger.error("No images found in session results")
                return None

            # Return the images in the expected format
            return {"items": [{"images": images}]}

        except Exception as e:
            logger.error(f"Error getting batch results: {e}")
            return None


class HnfmImageProcessor:
    """Main class for processing images with InvokeAI using Flux Krea model."""

    def __init__(self, invokeai_url: str = "http://127.0.0.1:9090"):
        self.invokeai = InvokeAIClient(invokeai_url)
        self.workflow = self.get_flux_kontext_workflow()

    def get_flux_kontext_workflow(self) -> Dict[str, Any]:
        """Get the Flux Kontext workflow template."""
        return {
            "queue_id": "default",
            "enqueued": 0,
            "requested": 0,
            "batch": {
                "data": [],
                "graph": {
                    "id": "flux_graph:0jvJra19ex",
                    "nodes": {
                        "flux_model_loader:bd0MVf7iCK": {
                            "id": "flux_model_loader:bd0MVf7iCK",
                            "is_intermediate": True,
                            "use_cache": True,
                            "model": {
                                "key": "ca0800b8-85ad-49ad-9479-4cd4f5a36f06",
                                "hash": "blake3:ce954e44b3c37036200c27a78f062b237391db05158f46978cb26de7a1829a0f",
                                "name": "FLUX.1 Krea dev (quantized)",
                                "base": "flux",
                                "type": "main",
                            },
                            "t5_encoder_model": {
                                "key": "bff4ecd3-58a1-46b9-b584-70afbe24c28d",
                                "hash": "blake3:40a5cc4644387715e55e9683ad3c583d03080fa5e5819ae687f836e22a6f2590",
                                "name": "SD3.5 Medium",
                                "base": "sd-3",
                                "type": "main",
                            },
                            "clip_embed_model": {
                                "key": "f4269feb-2e98-4174-9c22-74dca9140584",
                                "hash": "blake3:17c19f0ef941c3b7609a9c94a659ca5364de0be364a91d4179f0e39ba17c3b70",
                                "name": "clip-vit-large-patch14",
                                "base": "any",
                                "type": "clip_embed",
                            },
                            "vae_model": {
                                "key": "0f0ccb31-5bd9-4a29-b2a4-56168596f4d6",
                                "hash": "blake3:ce21cb76364aa6e2421311cf4a4b5eb052a76c4f1cd207b50703d8978198a068",
                                "name": "FLUX.1-schnell_ae",
                                "base": "flux",
                                "type": "vae",
                            },
                            "type": "flux_model_loader",
                        },
                        "positive_prompt:lPuYTEDPlS": {
                            "id": "positive_prompt:lPuYTEDPlS",
                            "is_intermediate": True,
                            "use_cache": True,
                            "value": "ancient chinese painting of a scene from dream of the red chamber brilliant colors soft tones and elegance pavilion lush green rocks and palm trees with young women in beautiful traditional dress isometric perspective skew ",
                            "type": "string",
                        },
                        "flux_text_encoder:9Xql5lnART": {
                            "id": "flux_text_encoder:9Xql5lnART",
                            "is_intermediate": True,
                            "use_cache": True,
                            "type": "flux_text_encoder",
                        },
                        "pos_cond_collect:UyS8BAHzCI": {
                            "id": "pos_cond_collect:UyS8BAHzCI",
                            "is_intermediate": True,
                            "use_cache": True,
                            "collection": [],
                            "type": "collect",
                        },
                        "seed:Lcn2HpBb1d": {
                            "id": "seed:Lcn2HpBb1d",
                            "is_intermediate": True,
                            "use_cache": True,
                            "value": 2442312641,
                            "type": "integer",
                        },
                        "flux_denoise:vKUCA9K7C0": {
                            "id": "flux_denoise:vKUCA9K7C0",
                            "is_intermediate": True,
                            "use_cache": True,
                            "denoising_start": 0,
                            "denoising_end": 1,
                            "add_noise": True,
                            "cfg_scale": 1,
                            "cfg_scale_start_step": 0,
                            "cfg_scale_end_step": -1,
                            "width": 1360,
                            "height": 768,
                            "num_steps": 50,
                            "guidance": 6,
                            "seed": 0,
                            "type": "flux_denoise",
                        },
                        "core_metadata:pngrOI8yWW": {
                            "id": "core_metadata:pngrOI8yWW",
                            "is_intermediate": True,
                            "use_cache": True,
                            "generation_mode": "flux_txt2img",
                            "width": 1360,
                            "height": 768,
                            "steps": 50,
                            "model": {
                                "key": "ca0800b8-85ad-49ad-9479-4cd4f5a36f06",
                                "hash": "blake3:ce954e44b3c37036200c27a78f062b237391db05158f46978cb26de7a1829a0f",
                                "name": "FLUX.1 Krea dev (quantized)",
                                "base": "flux",
                                "type": "main",
                            },
                            "vae": {
                                "key": "0f0ccb31-5bd9-4a29-b2a4-56168596f4d6",
                                "hash": "blake3:ce21cb76364aa6e2421311cf4a4b5eb052a76c4f1cd207b50703d8978198a068",
                                "name": "FLUX.1-schnell_ae",
                                "base": "flux",
                                "type": "vae",
                            },
                            "type": "core_metadata",
                            "guidance": 6,
                            "t5_encoder": {
                                "key": "bff4ecd3-58a1-46b9-b584-70afbe24c28d",
                                "hash": "blake3:40a5cc4644387715e55e9683ad3c583d03080fa5e5819ae687f836e22a6f2590",
                                "name": "SD3.5 Medium",
                                "base": "sd-3",
                                "type": "main",
                            },
                            "clip_embed_model": {
                                "key": "f4269feb-2e98-4174-9c22-74dca9140584",
                                "hash": "blake3:17c19f0ef941c3b7609a9c94a659ca5364de0be364a91d4179f0e39ba17c3b70",
                                "name": "clip-vit-large-patch14",
                                "base": "any",
                                "type": "clip_embed",
                            },
                            "ref_images": [],
                        },
                        "canvas_output:4PsihW6GLM": {
                            "id": "canvas_output:4PsihW6GLM",
                            "is_intermediate": False,
                            "use_cache": False,
                            "type": "flux_vae_decode",
                        },
                    },
                    "edges": [
                        {
                            "source": {
                                "node_id": "flux_model_loader:bd0MVf7iCK",
                                "field": "transformer",
                            },
                            "destination": {
                                "node_id": "flux_denoise:vKUCA9K7C0",
                                "field": "transformer",
                            },
                        },
                        {
                            "source": {
                                "node_id": "flux_model_loader:bd0MVf7iCK",
                                "field": "vae",
                            },
                            "destination": {
                                "node_id": "flux_denoise:vKUCA9K7C0",
                                "field": "controlnet_vae",
                            },
                        },
                        {
                            "source": {
                                "node_id": "flux_model_loader:bd0MVf7iCK",
                                "field": "vae",
                            },
                            "destination": {
                                "node_id": "canvas_output:4PsihW6GLM",
                                "field": "vae",
                            },
                        },
                        {
                            "source": {
                                "node_id": "flux_model_loader:bd0MVf7iCK",
                                "field": "clip",
                            },
                            "destination": {
                                "node_id": "flux_text_encoder:9Xql5lnART",
                                "field": "clip",
                            },
                        },
                        {
                            "source": {
                                "node_id": "flux_model_loader:bd0MVf7iCK",
                                "field": "t5_encoder",
                            },
                            "destination": {
                                "node_id": "flux_text_encoder:9Xql5lnART",
                                "field": "t5_encoder",
                            },
                        },
                        {
                            "source": {
                                "node_id": "flux_model_loader:bd0MVf7iCK",
                                "field": "max_seq_len",
                            },
                            "destination": {
                                "node_id": "flux_text_encoder:9Xql5lnART",
                                "field": "t5_max_seq_len",
                            },
                        },
                        {
                            "source": {
                                "node_id": "positive_prompt:lPuYTEDPlS",
                                "field": "value",
                            },
                            "destination": {
                                "node_id": "flux_text_encoder:9Xql5lnART",
                                "field": "prompt",
                            },
                        },
                        {
                            "source": {
                                "node_id": "flux_text_encoder:9Xql5lnART",
                                "field": "conditioning",
                            },
                            "destination": {
                                "node_id": "pos_cond_collect:UyS8BAHzCI",
                                "field": "item",
                            },
                        },
                        {
                            "source": {
                                "node_id": "pos_cond_collect:UyS8BAHzCI",
                                "field": "collection",
                            },
                            "destination": {
                                "node_id": "flux_denoise:vKUCA9K7C0",
                                "field": "positive_text_conditioning",
                            },
                        },
                        {
                            "source": {"node_id": "seed:Lcn2HpBb1d", "field": "value"},
                            "destination": {
                                "node_id": "flux_denoise:vKUCA9K7C0",
                                "field": "seed",
                            },
                        },
                        {
                            "source": {
                                "node_id": "flux_denoise:vKUCA9K7C0",
                                "field": "latents",
                            },
                            "destination": {
                                "node_id": "canvas_output:4PsihW6GLM",
                                "field": "latents",
                            },
                        },
                        {
                            "source": {"node_id": "seed:Lcn2HpBb1d", "field": "value"},
                            "destination": {
                                "node_id": "core_metadata:pngrOI8yWW",
                                "field": "seed",
                            },
                        },
                        {
                            "source": {
                                "node_id": "positive_prompt:lPuYTEDPlS",
                                "field": "value",
                            },
                            "destination": {
                                "node_id": "core_metadata:pngrOI8yWW",
                                "field": "positive_prompt",
                            },
                        },
                        {
                            "source": {
                                "node_id": "core_metadata:pngrOI8yWW",
                                "field": "metadata",
                            },
                            "destination": {
                                "node_id": "canvas_output:4PsihW6GLM",
                                "field": "metadata",
                            },
                        },
                    ],
                },
                "runs": 1,
            },
            "priority": 0,
        }

    def modify_workflow(self, prompt: str, image_name: str) -> Dict[str, Any]:
        """
        Modifies the workflow with the provided prompt and image name.

        Args:
            prompt (str): The prompt to use for generation
            image_name (str): The name of the uploaded image

        Returns:
            dict: The modified workflow data
        """
        try:
            # Create a deep copy of the workflow to avoid modifying the original
            modified_workflow = copy.deepcopy(self.workflow)

            # Update the prompt node
            prompt_node_id = "positive_prompt:lPuYTEDPlS"
            modified_workflow["batch"]["graph"]["nodes"][prompt_node_id][
                "value"
            ] = prompt
            logger.info(f"Updated prompt to: {prompt}")

            return modified_workflow

        except Exception as e:
            logger.error(f"Error modifying workflow: {e}")
            return None
