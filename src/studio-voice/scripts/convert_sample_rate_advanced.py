#!/usr/bin/env python3
"""
Advanced audio sample rate converter utility.
Uses scipy for high-quality resampling.
"""

import argparse
import os
import soundfile as sf
import numpy as np
from scipy import signal


def convert_sample_rate_advanced(input_file, output_file, target_sample_rate):
    """
    Convert audio file to target sample rate using high-quality resampling.

    Args:
        input_file (str): Path to input audio file
        output_file (str): Path to output audio file
        target_sample_rate (int): Target sample rate in Hz
    """
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


def main():
    parser = argparse.ArgumentParser(
        description="Convert audio file sample rate with high quality"
    )
    parser.add_argument("--input", "-i", required=True, help="Input audio file path")
    parser.add_argument("--output", "-o", required=True, help="Output audio file path")
    parser.add_argument(
        "--sample-rate",
        "-s",
        type=int,
        default=48000,
        help="Target sample rate (default: 48000)",
    )

    args = parser.parse_args()

    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.")
        return 1

    try:
        convert_sample_rate_advanced(args.input, args.output, args.sample_rate)
        return 0
    except Exception as e:
        print(f"Error during conversion: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
