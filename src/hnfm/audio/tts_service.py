"""Text-to-speech service for hn.fm."""


class TTSService:
    """Text-to-speech service."""

    def __init__(self):
        """Initialize the TTS service."""
        pass

    def generate_speech(self, text: str) -> bytes:
        """Generate speech from text.

        Args:
            text: Text to convert to speech

        Returns:
            Audio data as bytes
        """
        # TODO: Implement TTS
        return b"placeholder_audio_data"
