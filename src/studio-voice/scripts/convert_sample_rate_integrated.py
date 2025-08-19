#!/usr/bin/env python3
"""
Integrated sample rate converter for studio_voice.py processing.
Automatically converts audio files to 48kHz if needed.
"""

import sys
import os
import shutil
import soundfile as sf
import numpy as np
from scipy import signal


def convert_to_48k(input_file, output_file):
    """
    Convert audio file to 48kHz using high-quality resampling.

    Args:
        input_file (str): Path to input audio file
        output_file (str): Path to output audio file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Read the input file
        print(f"Reading audio file: {input_file}")
        data, sample_rate = sf.read(input_file)

        print(f"Original sample rate: {sample_rate} Hz")
        target_sample_rate = 48000
        print(f"Target sample rate: {target_sample_rate} Hz")

        # Check if conversion is needed
        if sample_rate == target_sample_rate:
            print("Sample rate already 48kHz, no conversion needed.")
            print(f"Copying file to output location: {output_file}")
            shutil.copy2(input_file, output_file)
            return True

        print("Converting to 48kHz using high-quality resampling...")

        # Calculate the number of samples for the new sample rate
        new_length = int(len(data) * target_sample_rate / sample_rate)

        # Use scipy's resample function for better quality
        resampled_data = signal.resample(data, new_length)

        # Ensure the data is in the correct format
        if resampled_data.dtype != data.dtype:
            resampled_data = resampled_data.astype(data.dtype)

        # Write the output file
        print(f"Writing converted file: {output_file}")
        sf.write(output_file, resampled_data, target_sample_rate)

        print(f"Sample rate conversion complete!")
        return True

    except Exception as e:
        print(f"Error during sample rate conversion: {e}")
        return False


def main():
    if len(sys.argv) != 3:
        print(
            "Usage: python convert_sample_rate_integrated.py <input_file> <output_file>"
        )
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist.")
        sys.exit(1)

    success = convert_to_48k(input_file, output_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
