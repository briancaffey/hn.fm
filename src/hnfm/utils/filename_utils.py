"""Filename utilities for hn.fm."""

import re
from typing import Optional


def sanitize_filename(filename: str, max_length: Optional[int] = 100) -> str:
    """Sanitize a filename to be safe for file systems.

    Args:
        filename: Original filename to sanitize
        max_length: Maximum length for the filename (default: 100)

    Returns:
        Sanitized filename safe for file systems
    """
    if not filename:
        return "untitled_article"

    # Replace problematic characters with safe alternatives
    replacements = {
        ":": " - ",  # Colon -> dash
        "?": "",  # Question mark -> remove
        "!": "",  # Exclamation mark -> remove
        '"': "",  # Double quote -> remove
        "'": "",  # Single quote -> remove
        "<": "(",  # Less than -> parenthesis
        ">": ")",  # Greater than -> parenthesis
        "|": "-",  # Pipe -> dash
        "*": "",  # Asterisk -> remove
        "/": "-",  # Forward slash -> dash
        "\\": "-",  # Backslash -> dash
        "[": "(",  # Square bracket -> parenthesis
        "]": ")",  # Square bracket -> parenthesis
        "{": "(",  # Curly brace -> parenthesis
        "}": ")",  # Curly brace -> parenthesis
        "&": "and",  # Ampersand -> 'and'
        "%": "pct",  # Percent -> 'pct'
        "#": "num",  # Hash -> 'num'
        "@": "at",  # At symbol -> 'at'
        "+": "plus",  # Plus -> 'plus'
        "=": "equals",  # Equals -> 'equals'
        "$": "dollar",  # Dollar -> 'dollar'
        ";": ",",  # Semicolon -> comma
    }

    # Apply replacements
    sanitized = filename
    for char, replacement in replacements.items():
        sanitized = sanitized.replace(char, replacement)

    # Remove any remaining non-alphanumeric characters except spaces, dashes, underscores, and dots
    sanitized = re.sub(r"[^\w\s\-_.]", "", sanitized)

    # Replace multiple spaces/dashes/underscores with single underscore
    sanitized = re.sub(r"[\s\-_]+", "_", sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    # Ensure the filename isn't too long
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip("_")

    # Ensure we have a valid filename
    if not sanitized:
        sanitized = "untitled_article"

    # Convert to lowercase for consistency
    sanitized = sanitized.lower()

    return sanitized
