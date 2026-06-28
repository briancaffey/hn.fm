"""ASR (Automatic Speech Recognition) service for hn.fm."""

import os
import requests
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from ..utils.config import config_manager

logger = logging.getLogger(__name__)


def _normalize_asr(raw: dict) -> dict:
    """Normalize OpenAI/Nemotron transcription output to the shape the rest of
    the pipeline expects: a flat `words` list plus caption-sized `segments`
    (each with its own words). Grouping breaks on sentence punctuation, a word
    cap, or a time gap so subtitle lines are readable.
    """
    words = []
    for w in raw.get("words", []) or []:
        word = (w.get("word") or w.get("text") or "").strip()
        if not word:
            continue
        words.append(
            {"word": word, "start": float(w.get("start", 0)), "end": float(w.get("end", 0))}
        )

    segments = []
    cur = []
    MAX_WORDS = 7
    MAX_DUR = 3.2
    for w in words:
        if cur:
            span = w["end"] - cur[0]["start"]
            gap = w["start"] - cur[-1]["end"]
            if len(cur) >= MAX_WORDS or span > MAX_DUR or gap > 0.7:
                segments.append(_seg_from_words(cur))
                cur = []
        cur.append(w)
        if cur[-1]["word"].endswith((".", "!", "?")) and len(cur) >= 3:
            segments.append(_seg_from_words(cur))
            cur = []
    if cur:
        segments.append(_seg_from_words(cur))

    return {
        "text": raw.get("text", " ".join(w["word"] for w in words)),
        "language": raw.get("language", "en"),
        "duration": raw.get("duration", words[-1]["end"] if words else 0),
        "words": words,
        "segments": segments,
    }


def _seg_from_words(ws: list) -> dict:
    return {
        "start": ws[0]["start"],
        "end": ws[-1]["end"],
        "text": " ".join(w["word"] for w in ws),
        "words": list(ws),
    }


def asr_qa_report(transcript: str, script: str) -> dict:
    """Compare what was actually narrated (ASR transcript) to the script text.

    A low-effort quality gate: high ratio = the TTS faithfully spoke the script;
    drift can mean dropped lines, mispronunciations, or TTS artifacts worth
    fixing. Returns a small report suitable as a UI receipt.
    """
    import re
    import difflib

    def norm(t: str):
        t = re.sub(r"\[S[12]\]", " ", t or "")
        t = re.sub(r"[^a-z0-9' ]", " ", t.lower())
        return t.split()

    a, b = norm(script), norm(transcript)
    sm = difflib.SequenceMatcher(None, a, b)
    ratio = round(sm.ratio(), 3)
    verdict = "good" if ratio >= 0.9 else ("ok" if ratio >= 0.75 else "drift")
    mismatches = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal" and len(mismatches) < 10:
            mismatches.append(
                {
                    "op": tag,
                    "script": " ".join(a[i1:i2])[:80],
                    "heard": " ".join(b[j1:j2])[:80],
                }
            )
    return {
        "ratio": ratio,
        "verdict": verdict,
        "script_words": len(a),
        "heard_words": len(b),
        "mismatches": mismatches,
    }


class ASRService:
    """Service for processing audio through WhisperX ASR."""

    def __init__(self):
        """Initialize the ASR service."""
        self.base_url = config_manager.get("asr.base_url")
        self.model_size = config_manager.get("asr.model_size", "large-v2")
        self.min_speakers = config_manager.get("asr.min_speakers", 1)
        self.max_speakers = config_manager.get("asr.max_speakers", 2)

        # Timeout and retry configuration
        self.timeout_seconds = config_manager.get(
            "asr.timeout_seconds", 300
        )  # 5 minutes default
        self.retry_delay = config_manager.get(
            "asr.retry_delay", 10
        )  # 10 seconds default
        self.max_attempts = config_manager.get(
            "asr.max_attempts", 5
        )  # 5 attempts default

        # Get HF token from environment variable
        self.hf_token = os.getenv("HF_TOKEN")

        if not self.base_url:
            raise ValueError(
                "ASR base URL not configured. Please set asr.base_url in config."
            )

        self.base_url = self.base_url.rstrip("/")

        if not self.hf_token:
            logger.warning(
                "HF_TOKEN environment variable not set. ASR may not work properly."
            )

    def get_timeout_info(self) -> Dict[str, Any]:
        """Get timeout configuration information for debugging.

        Returns:
            Dictionary with timeout settings
        """
        return {
            "timeout_seconds": self.timeout_seconds,
            "retry_delay": self.retry_delay,
            "max_attempts": self.max_attempts,
            "base_url": self.base_url,
            "model_size": self.model_size,
        }

    def is_healthy(self) -> bool:
        """Check if the ASR service is healthy and responsive.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """Check ASR server health.

        Returns:
            Health check response from the server

        Raises:
            requests.exceptions.RequestException: If health check fails
        """
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"ASR health check failed: {e}")
            raise

    def process_audio(
        self,
        audio_file_path: str,
        model_size: Optional[str] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process audio file through ASR service with retry mechanism.

        Args:
            audio_file_path: Path to the audio file to process
            model_size: Whisper model size (defaults to config value)
            min_speakers: Minimum number of speakers (defaults to config value)
            max_speakers: Maximum number of speakers (defaults to config value)

        Returns:
            ASR processing results as a dictionary

        Raises:
            FileNotFoundError: If audio file doesn't exist
            RuntimeError: If ASR processing fails after all retries
        """
        if not Path(audio_file_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        # Use provided values or fall back to defaults
        model_size = model_size or self.model_size
        min_speakers = min_speakers if min_speakers is not None else self.min_speakers
        max_speakers = max_speakers if max_speakers is not None else self.max_speakers

        logger.info(f"🎙️ Processing audio through ASR service: {self.base_url}")
        logger.info(f"📁 Audio file: {audio_file_path}")
        logger.info(f"🎯 Model: {model_size}, Speakers: {min_speakers}-{max_speakers}")
        logger.info(
            f"⏱️ Timeout: {self.timeout_seconds}s, Max attempts: {self.max_attempts}"
        )

        # Check service health before starting
        if not self.is_healthy():
            logger.warning("⚠️ ASR service appears unhealthy, attempting anyway...")

        for attempt in range(1, self.max_attempts + 1):
            try:
                logger.info(f"🔄 ASR attempt {attempt}/{self.max_attempts}")

                # Process audio with timeout protection
                results = self._process_audio_with_timeout(
                    audio_file_path, model_size, min_speakers, max_speakers
                )

                if results:
                    logger.info(
                        f"✅ ASR processing completed successfully on attempt {attempt}"
                    )
                    logger.info(
                        f"📊 Results: {len(results.get('segments', []))} segments, {results.get('language', 'Unknown')} language"
                    )
                    return results

            except Exception as e:
                logger.warning(f"❌ ASR attempt {attempt} failed: {e}")

                if attempt < self.max_attempts:
                    logger.info(
                        f"⏳ Waiting {self.retry_delay} seconds before retry..."
                    )
                    import time

                    time.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"❌ All {self.max_attempts} ASR attempts failed. Last error: {e}"
                    )
                    raise RuntimeError(
                        f"ASR processing failed after {self.max_attempts} attempts: {e}"
                    )

        # This should never be reached, but just in case
        raise RuntimeError(f"ASR processing failed after {self.max_attempts} attempts")

    def _process_audio_with_timeout(
        self,
        audio_file_path: str,
        model_size: str,
        min_speakers: int,
        max_speakers: int,
    ) -> Optional[Dict[str, Any]]:
        """Process audio with timeout protection.

        Args:
            audio_file_path: Path to the audio file
            model_size: Whisper model size
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers

        Returns:
            ASR results or None if failed
        """
        import threading
        import queue

        result_queue = queue.Queue()
        exception_queue = queue.Queue()

        def _asr_worker():
            """Worker function to run ASR in separate thread."""
            try:
                logger.debug(f"🎙️ Starting ASR processing in worker thread...")

                # Nemotron-ASR speaks the OpenAI transcription API with
                # word-level timestamps (verbose_json).
                files = {"file": open(audio_file_path, "rb")}
                data = {
                    "model": os.getenv("ASR_MODEL", "nemotron"),
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "word",
                }

                try:
                    response = requests.post(
                        f"{self.base_url}/v1/audio/transcriptions",
                        files=files,
                        data=data,
                        timeout=self.timeout_seconds,
                    )
                    response.raise_for_status()
                    results = _normalize_asr(response.json())
                    result_queue.put(results)
                    logger.debug(f"🎙️ ASR worker thread completed successfully")

                except Exception as e:
                    exception_queue.put(e)
                finally:
                    if "file" in files and hasattr(files["file"], "close"):
                        files["file"].close()

            except Exception as e:
                logger.error(f"🎙️ ASR worker thread failed: {e}")
                exception_queue.put(e)

        # Start ASR worker thread
        worker_thread = threading.Thread(target=_asr_worker, daemon=True)
        worker_thread.start()
        logger.debug(
            f"🎙️ ASR worker thread started, waiting up to {self.timeout_seconds}s..."
        )

        # Wait for result with timeout
        try:
            worker_thread.join(timeout=self.timeout_seconds)

            if worker_thread.is_alive():
                logger.warning(
                    f"⏰ ASR request timed out after {self.timeout_seconds} seconds"
                )
                # Try to get a quick response with a shorter timeout
                logger.info("🔄 Attempting quick retry with shorter timeout...")
                worker_thread.join(timeout=60)  # 1 minute quick retry

                if worker_thread.is_alive():
                    logger.error("⏰ Quick retry also timed out, giving up")
                    return None
                else:
                    logger.info("✅ Quick retry succeeded")

            # Check for exceptions
            try:
                exception = exception_queue.get_nowait()
                logger.error(f"❌ ASR worker thread failed: {exception}")
                raise exception
            except queue.Empty:
                pass

            # Get result
            try:
                result = result_queue.get_nowait()
                if result:
                    logger.debug(
                        f"✅ ASR worker thread returned results with {len(result.get('segments', []))} segments"
                    )
                else:
                    logger.warning("⚠️ ASR worker thread returned None")
                return result
            except queue.Empty:
                logger.error("❌ ASR worker thread completed but no result available")
                return None

        except Exception as e:
            logger.error(f"❌ Error in ASR timeout wrapper: {e}")
            raise e

    def save_results(self, results: Dict[str, Any], output_path: str) -> str:
        """Save ASR results to a JSON file.

        Args:
            results: ASR processing results
            output_path: Path where to save the results

        Returns:
            Path to the saved file
        """
        import json

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 ASR results saved to: {output_path}")
        return str(output_path)

    def process_and_save(
        self,
        audio_file_path: str,
        output_path: str,
        model_size: Optional[str] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process audio and save results in one operation.

        Args:
            audio_file_path: Path to the audio file to process
            output_path: Path where to save the results
            model_size: Whisper model size (defaults to config value)
            min_speakers: Minimum number of speakers (defaults to config value)
            max_speakers: Maximum number of speakers (defaults to config value)

        Returns:
            ASR processing results
        """
        # Process the audio
        results = self.process_audio(
            audio_file_path=audio_file_path,
            model_size=model_size,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        # Save the results
        self.save_results(results, output_path)

        return results
