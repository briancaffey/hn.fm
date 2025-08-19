#!/usr/bin/env python3
"""
Quick script to convert test_1.wav to 48kHz for Studio Voice model.
"""

import soundfile as sf
import numpy as np
from scipy import signal
import os


def convert_test_audio():
    """
    Convert test_1.wav from 44.1kHz to 48kHz
    """
    input_file = "../assets/test_1.wav"
    output_file = "../assets/test_1_48k.wav"
    target_sample_rate = 48000

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist.")
        return False

    try:
        # Read the input file
        print(f"Reading audio file: {input_file}")
        data, sample_rate = sf.read(input_file)

        print(f"Original sample rate: {sample_rate} Hz")
        print(f"Target sample rate: {target_sample_rate} Hz")
        print(f"Audio duration: {len(data) / sample_rate:.2f} seconds")

        # High-quality resampling using scipy
        if sample_rate != target_sample_rate:
            print("Performing high-quality resampling...")
            # Calculate the number of samples for the new sample rate
            new_length = int(len(data) * target_sample_rate / sample_rate)

            # Use scipy's resample function for better quality
            resampled_data = signal.resample(data, new_length)

            # Ensure the data is in the correct format
            if resampled_data.dtype != data.dtype:
                resampled_data = resampled_data.astype(data.dtype)
        else:
            print("Sample rates match, no conversion needed.")
            resampled_data = data

        # Write the output file
        print(f"Writing output file: {output_file}")
        sf.write(output_file, resampled_data, target_sample_rate)

        print(f"Conversion complete! Output saved to: {output_file}")
        print(f"\nYou can now use the converted file with Studio Voice:")
        print(
            f"python studio_voice.py --target 192.168.5.96:8001 --input {output_file} --output test_1_enhanced.wav --model-type 48k-hq"
        )

        return True

    except Exception as e:
        print(f"Error during conversion: {e}")
        return False


if __name__ == "__main__":
    success = convert_test_audio()
    if not success:
        exit(1)
