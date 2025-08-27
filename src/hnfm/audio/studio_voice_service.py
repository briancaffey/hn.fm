"""Studio Voice service for hn.fm using NVIDIA's gRPC-based audio enhancement."""

import logging
import time
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
import soundfile as sf
import numpy as np

# Add the studio-voice interfaces to the path
studio_voice_path = Path(__file__).parent.parent.parent / "studio-voice" / "interfaces"
sys.path.insert(0, str(studio_voice_path))

try:
    import grpc
    from studio_voice import studiovoice_pb2, studiovoice_pb2_grpc

    GRPC_AVAILABLE = True
except ImportError as e:
    # Logger not available yet, use print for now
    print(f"Studio Voice gRPC not available: {e}")
    GRPC_AVAILABLE = False

logger = logging.getLogger(__name__)


class StudioVoiceService:
    """Audio enhancement service using NVIDIA Studio Voice gRPC."""

    def __init__(
        self,
        target: str = None,
        model_type: str = "48k-hq",
        streaming: bool = False,
        ssl_mode: Optional[str] = None,
    ):
        """Initialize the Studio Voice service.

        Args:
            target: Studio Voice server address
            model_type: Model type to use (48k-hq, 48k-ll, 16k-hq)
            streaming: Enable streaming mode
            ssl_mode: SSL mode (TLS, MTLS, or None for insecure)
        """
        if target is None:
            # Get from config if not provided
            try:
                from ..utils.config import ConfigManager

                config_manager = ConfigManager()
                target = config_manager.get("studio_voice.target")
                if not target:
                    raise ValueError("STUDIO_VOICE_TARGET environment variable not set")
            except Exception as e:
                raise ValueError(f"Failed to get Studio Voice target from config: {e}")

        self.target = target
        self.model_type = model_type
        self.streaming = streaming
        self.ssl_mode = ssl_mode

        # Set sample rate based on model type
        if model_type == "16k-hq":
            self.sample_rate = 16000
        else:
            self.sample_rate = 48000

        logger.debug(f"🎵 Initializing Studio Voice service: {target} ({model_type})")
        logger.debug(f"🎵 Sample rate: {self.sample_rate}Hz, Streaming: {streaming}")

    def _convert_sample_rate(
        self, audio_data: bytes, target_rate: int = 48000
    ) -> bytes:
        """Convert audio data to target sample rate.

        Args:
            audio_data: Raw audio data
            target_rate: Target sample rate

        Returns:
            Converted audio data
        """
        try:
            # Create temporary file for conversion
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_in:
                temp_in.write(audio_data)
                temp_in_path = temp_in.name

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_out:
                temp_out_path = temp_out.name

            try:
                # Read audio data
                data, sample_rate = sf.read(temp_in_path)

                if sample_rate == target_rate:
                    logger.debug(
                        f"Sample rate already {target_rate}Hz, no conversion needed"
                    )
                    return audio_data

                logger.debug(
                    f"Converting sample rate: {sample_rate}Hz → {target_rate}Hz"
                )

                # Calculate new length
                new_length = int(len(data) * target_rate / sample_rate)

                # Resample using scipy
                from scipy import signal

                resampled_data = signal.resample(data, new_length)

                # Ensure correct data type
                if resampled_data.dtype != data.dtype:
                    resampled_data = resampled_data.astype(data.dtype)

                # Write converted file
                sf.write(temp_out_path, resampled_data, target_rate)

                # Read converted data
                with open(temp_out_path, "rb") as f:
                    converted_data = f.read()

                logger.debug(
                    f"Sample rate conversion successful: {len(audio_data)} → {len(converted_data)} bytes"
                )
                return converted_data

            finally:
                # Clean up temporary files
                os.unlink(temp_in_path)
                os.unlink(temp_out_path)

        except Exception as e:
            logger.error(f"Sample rate conversion failed: {e}")
            return audio_data

    def _create_grpc_channel(self):
        """Create gRPC channel with appropriate security settings."""
        if self.ssl_mode == "TLS":
            # TLS mode - you would need to provide root certificates
            logger.warning("TLS mode not fully implemented, using insecure channel")
            return grpc.insecure_channel(self.target)
        elif self.ssl_mode == "MTLS":
            # mTLS mode - you would need to provide certificates
            logger.warning("mTLS mode not fully implemented, using insecure channel")
            return grpc.insecure_channel(self.target)
        else:
            # Insecure channel (default for local development)
            return grpc.insecure_channel(self.target)

    def _generate_enhancement_requests(self, audio_data: bytes) -> list:
        """Generate gRPC requests for audio enhancement.

        Args:
            audio_data: Raw audio data

        Returns:
            List of EnhancementAudioRequest objects
        """
        if self.streaming:
            # Streaming mode - chunk audio based on model requirements
            input_audio, sample_rate = sf.read(
                tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            )
            input_audio = input_audio.astype(np.float32)

            # Chunk size based on model type
            input_size_in_ms = 10 if (self.model_type == "48k-ll") else 6000
            samples_per_ms = sample_rate // 1000
            input_float_size = int(input_size_in_ms * samples_per_ms)

            # Pad audio to chunk size
            pad_length = input_float_size - len(input_audio) % input_float_size
            input_audio = np.pad(input_audio, (0, pad_length), "constant")

            requests = []
            for i in range(0, len(input_audio), input_float_size):
                data = input_audio[i : i + input_float_size]
                requests.append(
                    studiovoice_pb2.EnhanceAudioRequest(
                        audio_stream_data=data.tobytes()
                    )
                )

            return requests
        else:
            # Non-streaming mode - send in 64KB chunks
            chunk_size = 64 * 1024
            requests = []

            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i : i + chunk_size]
                requests.append(
                    studiovoice_pb2.EnhanceAudioRequest(audio_stream_data=chunk)
                )

            return requests

    def enhance_audio(self, audio_data: bytes) -> Optional[bytes]:
        """Enhance audio using Studio Voice gRPC service.

        Args:
            audio_data: Raw audio data

        Returns:
            Enhanced audio data or None if failed
        """
        if not GRPC_AVAILABLE:
            logger.error("Studio Voice gRPC not available")
            return None

        try:
            logger.debug(f"🎵 Enhancing audio with Studio Voice ({self.model_type})")
            start_time = time.time()

            # Convert sample rate if needed
            converted_audio = self._convert_sample_rate(audio_data, self.sample_rate)

            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(converted_audio)
                temp_file_path = temp_file.name

            try:
                # Create gRPC channel
                with self._create_grpc_channel() as channel:
                    # Create stub
                    stub = studiovoice_pb2_grpc.MaxineStudioVoiceStub(channel)

                    # Generate requests
                    requests = self._generate_enhancement_requests(converted_audio)

                    # Call the service
                    logger.debug(
                        f"🎵 Sending {len(requests)} chunks to Studio Voice service"
                    )
                    response_iter = stub.EnhanceAudio(iter(requests))

                    # Collect enhanced audio data
                    enhanced_audio = b""
                    for response in response_iter:
                        enhanced_audio += response.audio_stream_data

                    duration = time.time() - start_time
                    logger.debug(f"✅ Audio enhancement completed in {duration:.2f}s")
                    logger.debug(
                        f"📊 Processed {len(audio_data)} → {len(enhanced_audio)} bytes"
                    )

                    return enhanced_audio

            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Failed to enhance audio: {e}")
            return None
