"""Tests for audio utilities"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

from ..audio.audio_utils import (
    split_script_into_sections,
    k_sec,
    k_sec_list,
    sec_audio_path,
    combined_audio_path,
    _get_audio_duration_ms,
)


class TestScriptSplitting:
    """Test script splitting functionality"""

    def test_split_script_into_sections_pairs_and_last_single(self):
        """Test splitting 5 lines into 3 sections (2,2,1)"""
        script = """[S1] First line of dialogue
[S2] Second line of dialogue
[S1] Third line of dialogue
[S2] Fourth line of dialogue
[S1] Fifth line of dialogue"""

        sections = split_script_into_sections(script)

        assert len(sections) == 3
        assert sections[0] == "[S1] First line of dialogue\n[S2] Second line of dialogue"
        assert sections[1] == "[S1] Third line of dialogue\n[S2] Fourth line of dialogue"
        assert sections[2] == "[S1] Fifth line of dialogue"

    def test_split_script_with_empty_lines(self):
        """Test splitting script with empty lines"""
        script = """[S1] First line

[S2] Second line

[S1] Third line"""

        sections = split_script_into_sections(script)

        assert len(sections) == 2
        assert sections[0] == "[S1] First line\n[S2] Second line"
        assert sections[1] == "[S1] Third line"

    def test_split_script_single_line(self):
        """Test splitting single line script"""
        script = "[S1] Only one line"

        sections = split_script_into_sections(script)

        assert len(sections) == 1
        assert sections[0] == "[S1] Only one line"


class TestKeyHelpers:
    """Test Redis key and path helper functions"""

    def test_k_sec(self):
        """Test section key generation"""
        key = k_sec(123, 1, 2, 3)
        assert key == "hnfm:seg:123:1:2:sec:3"

    def test_k_sec_list(self):
        """Test section list key generation"""
        key = k_sec_list(123, 1, 2)
        assert key == "hnfm:seg:123:1:2:sec:list"

    def test_sec_audio_path(self):
        """Test section audio path generation"""
        path = sec_audio_path("/outputs", 123, 1, 2, 3)
        expected = "/outputs/hn/item/123/runs/1/segments/2/audio/sections/3/audio.wav"
        assert path == expected

    def test_combined_audio_path(self):
        """Test combined audio path generation"""
        path = combined_audio_path("/outputs", 123, 1, 2)
        expected = "/outputs/hn/item/123/runs/1/segments/2/audio/segment.wav"
        assert path == expected


class TestAudioDuration:
    """Test audio duration calculation"""

    def test_get_audio_duration_ms(self):
        """Test getting audio duration from WAV file"""
        # Create a temporary WAV file with known duration
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name

            # Create a simple WAV file (1 second, 44.1kHz, 16-bit, mono)
            import wave
            import struct

            sample_rate = 44100
            duration_seconds = 1.0
            num_frames = int(sample_rate * duration_seconds)

            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)

                # Write silence (zeros)
                silence = b'\x00\x00' * num_frames
                wav_file.writeframes(silence)

            try:
                duration_ms = _get_audio_duration_ms(temp_path)
                assert duration_ms == 1000  # 1 second = 1000ms
            finally:
                os.unlink(temp_path)

    def test_get_audio_duration_invalid_file(self):
        """Test getting duration from invalid file"""
        with pytest.raises(RuntimeError):
            _get_audio_duration_ms("/nonexistent/file.wav")


class TestSectionMetadata:
    """Test section metadata operations"""

    @patch('redis.Redis')
    @patch('pathlib.Path.mkdir')
    def test_save_get_list_section_meta_roundtrip(self, mock_mkdir, mock_redis_class):
        """Test saving, getting, and listing section metadata"""
        from ..audio.audio_utils import save_section_meta, get_section_meta, list_section_numbers
        from ..web.models import SegmentSection

        # Setup mock Redis client
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis

        # Create test section metadata
        now = datetime.utcnow()
        section_meta = SegmentSection(
            key="hnfm:seg:123:1:2:sec:1",
            item_id=123,
            run=1,
            seg=2,
            section=1,
            text="Test text",
            audio_path="/path/to/audio.wav",
            cleaned=True,
            duration_ms=1000,
            created_at=now,
            updated_at=now
        )

        # Mock Redis operations
        mock_redis.set.return_value = True
        mock_redis.get.return_value = section_meta.model_dump_json().encode()
        mock_redis.lrange.return_value = [b"1"]

        # Test save
        with patch('builtins.open', mock_open()):
            save_section_meta(section_meta, redis_client=mock_redis, outputs_root="/outputs")

        # Verify Redis set was called
        mock_redis.set.assert_called_once()

        # Test get
        retrieved_meta = get_section_meta(123, 1, 2, 1, redis_client=mock_redis)
        assert retrieved_meta is not None
        assert retrieved_meta.text == "Test text"
        assert retrieved_meta.duration_ms == 1000

        # Test list
        section_numbers = list_section_numbers(123, 1, 2, redis_client=mock_redis)
        assert section_numbers == [1]


class TestAudioStitching:
    """Test audio stitching functionality"""

    @patch('wave.open')
    @patch('pathlib.Path.mkdir')
    def test_stitch_sections_to_wav(self, mock_mkdir, mock_wave_open):
        """Test stitching multiple WAV files"""
        from ..audio.audio_utils import stitch_sections_to_wav

        # Mock wave file objects
        mock_wav1 = Mock()
        mock_wav1.getnchannels.return_value = 1
        mock_wav1.getsampwidth.return_value = 2
        mock_wav1.getframerate.return_value = 44100
        mock_wav1.getnframes.return_value = 44100  # 1 second
        mock_wav1.readframes.return_value = b'\x00\x00' * 44100
        mock_wav1.__enter__ = Mock(return_value=mock_wav1)
        mock_wav1.__exit__ = Mock(return_value=None)

        mock_wav2 = Mock()
        mock_wav2.getnchannels.return_value = 1
        mock_wav2.getsampwidth.return_value = 2
        mock_wav2.getframerate.return_value = 44100
        mock_wav2.getnframes.return_value = 22050  # 0.5 seconds
        mock_wav2.readframes.return_value = b'\x00\x00' * 22050
        mock_wav2.__enter__ = Mock(return_value=mock_wav2)
        mock_wav2.__exit__ = Mock(return_value=None)

        mock_out_wav = Mock()
        mock_out_wav.__enter__ = Mock(return_value=mock_out_wav)
        mock_out_wav.__exit__ = Mock(return_value=None)

        # Configure wave.open to return appropriate mocks
        def wave_open_side_effect(path, mode):
            if mode == 'rb':
                if 'section1' in path:
                    return mock_wav1
                elif 'section2' in path:
                    return mock_wav2
            elif mode == 'wb':
                return mock_out_wav
            return Mock()

        mock_wave_open.side_effect = wave_open_side_effect

        # Mock os.path.exists
        with patch('os.path.exists', return_value=True):
            duration_ms = stitch_sections_to_wav(
                ["/path/section1.wav", "/path/section2.wav"],
                "/path/combined.wav"
            )

        # Should be 1.5 seconds = 1500ms
        assert duration_ms == 1500

        # Verify output file was written
        mock_out_wav.setnchannels.assert_called_with(1)
        mock_out_wav.setsampwidth.assert_called_with(2)
        mock_out_wav.setframerate.assert_called_with(44100)
        mock_out_wav.writeframes.assert_called_once()

    @patch('pathlib.Path.mkdir')
    def test_stitch_sections_empty_list(self, mock_mkdir):
        """Test stitching with empty section list"""
        from ..audio.audio_utils import stitch_sections_to_wav

        with pytest.raises(ValueError, match="No section paths provided"):
            stitch_sections_to_wav([], "/path/combined.wav")
