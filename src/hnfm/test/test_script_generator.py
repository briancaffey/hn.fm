"""Test suite for ScriptGenerator refactored functions."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock
from typing import List

from hnfm.content.script_generator import ScriptGenerator


class TestScriptGenerator:
    """Test cases for ScriptGenerator class."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        mock_tts = Mock()
        mock_audio_processor = Mock()
        mock_studio_voice = Mock()

        # Configure mock TTS service
        mock_tts.generate_speech.return_value = b"mock_audio_data"
        mock_tts.is_healthy.return_value = True

        # Configure mock audio processor
        mock_audio_processor.save_audio_data.return_value = None
        mock_audio_processor.combine_audio_files.return_value = None

        # Configure mock studio voice service
        mock_studio_voice.enhance_audio.return_value = b"cleaned_audio_data"
        mock_studio_voice.convert_sample_rate.return_value = b"converted_audio_data"
        mock_studio_voice.sample_rate = 48000

        return mock_tts, mock_audio_processor, mock_studio_voice

    @pytest.fixture
    def script_generator(self, mock_services):
        """Create ScriptGenerator instance with mocked services."""
        mock_tts, mock_audio_processor, mock_studio_voice = mock_services

        with (
            patch("hnfm.content.script_generator.TtsApiService", return_value=mock_tts),
            patch(
                "hnfm.content.script_generator.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch(
                "hnfm.content.script_generator.StudioVoiceService",
                return_value=mock_studio_voice,
            ),
            patch("hnfm.utils.config.ConfigManager") as mock_config,
        ):

            # Mock config manager
            mock_config.return_value.get.side_effect = lambda key, default=None: {
                "studio_voice": {
                    "target": "localhost:50051",
                    "studio_voice.model_type": "48k-hq",
                    "studio_voice.streaming": False,
                    "studio_voice.ssl_mode": None,
                }
            }.get(key, default)

            generator = ScriptGenerator()
            generator.tts_service = mock_tts
            generator.audio_processor = mock_audio_processor
            generator.studio_voice_service = mock_studio_voice

            return generator

    @pytest.fixture
    def sample_tts_lines_file(self):
        """Create a temporary TTS lines file for testing."""
        content = """[S1] Hello, welcome to the podcast.
[S2] Today we're discussing an interesting topic.
[S1] Let's dive right in.
[S2] This is the second speaker talking.
[S1] And now back to the first speaker."""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write(content)
            f.flush()
            yield f.name

        # Cleanup
        os.unlink(f.name)

    def test_clean_and_validate_input_success(
        self, script_generator, sample_tts_lines_file
    ):
        """Test successful input cleaning and validation."""
        lines = script_generator._clean_and_validate_input(sample_tts_lines_file)

        assert len(lines) == 5
        assert lines[0] == "[S1] Hello, welcome to the podcast."
        assert lines[1] == "[S2] Today we're discussing an interesting topic."

    def test_clean_and_validate_input_empty_file(self, script_generator):
        """Test input validation with empty file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("")
            f.flush()
            empty_file = f.name

        try:
            with pytest.raises(RuntimeError, match="No TTS lines found in file"):
                script_generator._clean_and_validate_input(empty_file)
        finally:
            os.unlink(empty_file)

    def test_clean_and_validate_input_whitespace_only(self, script_generator):
        """Test input validation with whitespace-only file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("   \n\n  \t  \n  ")
            f.flush()
            whitespace_file = f.name

        try:
            with pytest.raises(RuntimeError, match="No TTS lines found in file"):
                script_generator._clean_and_validate_input(whitespace_file)
        finally:
            os.unlink(whitespace_file)

    def test_setup_output_directories_default(self, script_generator):
        """Test setting up output directories with default story directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "hnfm.content.script_generator.sanitize_filename",
                return_value="test_story",
            ):
                story_dir, content_dir, audio_dir = (
                    script_generator._setup_output_directories("Test Story")
                )

                # Check that directories are created correctly
                assert story_dir.name == "test_story"
                assert content_dir.name == "content"
                assert audio_dir.name == "audio"
                assert content_dir.parent == story_dir
                assert audio_dir.parent == story_dir

    def test_setup_output_directories_custom(self, script_generator):
        """Test setting up output directories with custom story directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_dir = Path(temp_dir) / "custom_story"
            custom_dir.mkdir()

            story_dir, content_dir, audio_dir = (
                script_generator._setup_output_directories(
                    "Test Story", str(custom_dir)
                )
            )

            assert story_dir == custom_dir
            assert content_dir == custom_dir / "content"
            assert audio_dir == custom_dir / "audio"

    def test_save_tts_lines_success(self, script_generator):
        """Test successful saving of TTS lines."""
        lines = ["[S1] Line 1", "[S2] Line 2"]

        with tempfile.TemporaryDirectory() as temp_dir:
            content_dir = Path(temp_dir)

            script_generator._save_tts_lines(lines, content_dir)

            tts_file = content_dir / "tts_lines.txt"
            assert tts_file.exists()

            with open(tts_file, "r") as f:
                saved_content = f.read()
                assert "[S1] Line 1" in saved_content
                assert "[S2] Line 2" in saved_content

    def test_save_tts_lines_write_error(self, script_generator):
        """Test handling of write errors when saving TTS lines."""
        lines = ["[S1] Line 1"]

        with tempfile.TemporaryDirectory() as temp_dir:
            content_dir = Path(temp_dir)

            # Make the directory read-only to cause a write error
            content_dir.chmod(0o444)

            try:
                script_generator._save_tts_lines(lines, content_dir)
                # Should not raise an exception, just log a warning
            finally:
                # Restore write permissions for cleanup
                content_dir.chmod(0o755)

    def test_generate_audio_from_text_success(self, script_generator):
        """Test successful audio generation from text."""
        text = "Hello world"
        batch_number = 1

        audio_data = script_generator._generate_audio_from_text(text, batch_number)

        assert audio_data == b"mock_audio_data"
        script_generator.tts_service.generate_speech.assert_called_once_with(text)

    def test_generate_audio_from_text_tts_unavailable(self, script_generator):
        """Test audio generation when TTS service is unavailable."""
        script_generator.tts_service = Mock()
        del script_generator.tts_service.generate_speech

        audio_data = script_generator._generate_audio_from_text("Hello", 1)

        assert audio_data is None

    def test_generate_audio_from_text_tts_unhealthy(self, script_generator):
        """Test audio generation when TTS service is unhealthy."""
        script_generator.tts_service.is_healthy.return_value = False

        audio_data = script_generator._generate_audio_from_text("Hello", 1)

        assert audio_data == b"mock_audio_data"
        # Should still attempt generation despite being unhealthy

    def test_generate_audio_from_text_tts_failure(self, script_generator):
        """Test audio generation when TTS service fails."""
        script_generator.tts_service.generate_speech.return_value = None

        audio_data = script_generator._generate_audio_from_text("Hello", 1)

        assert audio_data is None

    def test_clean_audio_segment_success(self, script_generator):
        """Test successful audio cleaning."""
        audio_data = b"raw_audio_data"
        batch_number = 1

        cleaned_data = script_generator._clean_audio_segment(audio_data, batch_number)

        assert cleaned_data == b"cleaned_audio_data"
        script_generator.studio_voice_service.enhance_audio.assert_called_once_with(
            audio_data
        )

    def test_clean_audio_segment_studio_voice_unavailable(self, script_generator):
        """Test audio cleaning when Studio Voice service is unavailable."""
        script_generator.studio_voice_service = Mock()
        del script_generator.studio_voice_service.enhance_audio

        audio_data = b"raw_audio_data"
        cleaned_data = script_generator._clean_audio_segment(audio_data, 1)

        assert cleaned_data == audio_data  # Should return original data

    def test_clean_audio_segment_cleaning_fails(self, script_generator):
        """Test audio cleaning when enhancement fails."""
        script_generator.studio_voice_service.enhance_audio.return_value = None

        audio_data = b"raw_audio_data"
        cleaned_data = script_generator._clean_audio_segment(audio_data, 1)

        # Should fallback to original audio with sample rate conversion
        assert cleaned_data == b"converted_audio_data"
        script_generator.studio_voice_service.convert_sample_rate.assert_called_once()

    def test_clean_audio_segment_sample_rate_conversion_fails(self, script_generator):
        """Test audio cleaning when sample rate conversion fails."""
        script_generator.studio_voice_service.enhance_audio.return_value = None
        script_generator.studio_voice_service.convert_sample_rate.side_effect = (
            Exception("Conversion failed")
        )

        audio_data = b"raw_audio_data"
        cleaned_data = script_generator._clean_audio_segment(audio_data, 1)

        assert cleaned_data == audio_data  # Should return original data

    def test_save_batch_audio_success(self, script_generator):
        """Test successful saving of batch audio."""
        audio_data = b"audio_data"

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_dir = Path(temp_dir)

            # Test raw audio
            script_generator._save_batch_audio(
                audio_data, audio_dir, 1, is_cleaned=False
            )
            script_generator.audio_processor.save_audio_data.assert_called()

            # Test cleaned audio
            script_generator._save_batch_audio(
                audio_data, audio_dir, 1, is_cleaned=True
            )
            script_generator.audio_processor.save_audio_data.assert_called()

    def test_save_batch_audio_processor_unavailable(self, script_generator):
        """Test saving batch audio when audio processor is unavailable."""
        script_generator.audio_processor = Mock()
        del script_generator.audio_processor.save_audio_data

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_dir = Path(temp_dir)

            # Should not raise an exception
            script_generator._save_batch_audio(b"data", audio_dir, 1)

    def test_combine_audio_files_success(self, script_generator):
        """Test successful audio file combination."""
        audio_data_list = [b"audio1", b"audio2", b"audio3"]
        story_name = "Test Story"

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_dir = Path(temp_dir)

            final_path = script_generator._combine_audio_files(
                audio_data_list, story_name, audio_dir
            )

            expected_path = audio_dir / "test_story_final.wav"
            assert final_path == expected_path
            script_generator.audio_processor.combine_audio_files.assert_called_once_with(
                audio_data_list, expected_path
            )

    def test_combine_audio_files_processor_unavailable(self, script_generator):
        """Test audio combination when processor is unavailable."""
        script_generator.audio_processor = Mock()
        del script_generator.audio_processor.combine_audio_files

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_dir = Path(temp_dir)

            with pytest.raises(RuntimeError, match="Audio processor not available"):
                script_generator._combine_audio_files([b"data"], "story", audio_dir)

    def test_combine_audio_files_combination_fails(self, script_generator):
        """Test audio combination when combination fails."""
        script_generator.audio_processor.combine_audio_files.side_effect = Exception(
            "Combination failed"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_dir = Path(temp_dir)

            with pytest.raises(RuntimeError, match="Audio combination failed"):
                script_generator._combine_audio_files([b"data"], "story", audio_dir)

    def test_verify_final_audio_success(self, script_generator):
        """Test successful final audio verification."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"some audio data")
            f.flush()
            audio_path = Path(f.name)

        try:
            # Should not raise an exception
            script_generator._verify_final_audio(audio_path)
        finally:
            os.unlink(audio_path)

    def test_verify_final_audio_file_not_exists(self, script_generator):
        """Test final audio verification when file doesn't exist."""
        non_existent_path = Path("/non/existent/path.wav")

        with pytest.raises(RuntimeError, match="Final audio file was not created"):
            script_generator._verify_final_audio(non_existent_path)

    def test_verify_final_audio_empty_file(self, script_generator):
        """Test final audio verification when file is empty."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Write nothing to create empty file
            f.flush()
            empty_path = Path(f.name)

        try:
            with pytest.raises(RuntimeError, match="Final audio file is empty"):
                script_generator._verify_final_audio(empty_path)
        finally:
            os.unlink(empty_path)

    def test_log_processing_summary_all_cleaned(self, script_generator):
        """Test logging processing summary when all audio is cleaned."""
        all_audio_data = [b"audio1", b"audio2"]
        all_cleaned_audio_data = [b"cleaned1", b"cleaned2"]

        # Should not raise an exception
        script_generator._log_processing_summary(all_audio_data, all_cleaned_audio_data)

    def test_log_processing_summary_with_fallbacks(self, script_generator):
        """Test logging processing summary when some audio uses fallback."""
        all_audio_data = [b"audio1", b"audio2"]
        all_cleaned_audio_data = [b"audio1", b"cleaned2"]  # First one is fallback

        # Should not raise an exception
        script_generator._log_processing_summary(all_audio_data, all_cleaned_audio_data)

    def test_process_tts_lines_integration_success(
        self, script_generator, sample_tts_lines_file
    ):
        """Test the complete process_tts_lines integration."""
        story_name = "Test Story"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the final audio file creation
            final_audio_path = Path(temp_dir) / "test_story_final.wav"
            final_audio_path.write_bytes(b"final audio content")

            with patch.object(
                script_generator, "_combine_audio_files", return_value=final_audio_path
            ):
                result_path = script_generator.process_tts_lines(
                    sample_tts_lines_file, story_name, batch_size=2
                )

                assert result_path == final_audio_path

    def test_process_tts_lines_no_audio_generated(
        self, script_generator, sample_tts_lines_file
    ):
        """Test process_tts_lines when no audio is generated."""
        script_generator.tts_service.generate_speech.return_value = None

        with pytest.raises(
            RuntimeError, match="No audio was generated and cleaned successfully"
        ):
            script_generator.process_tts_lines(sample_tts_lines_file, "Test Story")

    def test_process_tts_lines_empty_batches(self, script_generator):
        """Test process_tts_lines with empty batches."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("   \n\n  \t  \n  ")
            f.flush()
            empty_file = f.name

        try:
            with pytest.raises(RuntimeError, match="No TTS lines found in file"):
                script_generator.process_tts_lines(empty_file, "Test Story")
        finally:
            os.unlink(empty_file)

    def test_process_tts_lines_custom_story_dir(
        self, script_generator, sample_tts_lines_file
    ):
        """Test process_tts_lines with custom story directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_dir = Path(temp_dir) / "custom"
            custom_dir.mkdir()

            final_audio_path = custom_dir / "audio" / "test_story_final.wav"
            final_audio_path.parent.mkdir()
            final_audio_path.write_bytes(b"final audio content")

            with patch.object(
                script_generator, "_combine_audio_files", return_value=final_audio_path
            ):
                result_path = script_generator.process_tts_lines(
                    sample_tts_lines_file, "Test Story", story_dir=str(custom_dir)
                )

                assert result_path == final_audio_path

    def test_process_tts_lines_batch_processing(
        self, script_generator, sample_tts_lines_file
    ):
        """Test that batch processing works correctly."""
        story_name = "Test Story"
        batch_size = 2

        with tempfile.TemporaryDirectory() as temp_dir:
            final_audio_path = Path(temp_dir) / "test_story_final.wav"
            final_audio_path.write_bytes(b"final audio content")

            with patch.object(
                script_generator, "_combine_audio_files", return_value=final_audio_path
            ):
                result_path = script_generator.process_tts_lines(
                    sample_tts_lines_file, story_name, batch_size=batch_size
                )

                # Should have called generate_speech for each batch
                # 5 lines with batch_size=2 should create 3 batches
                assert script_generator.tts_service.generate_speech.call_count == 3
