"""Deterministic quality measurement for generated content.

Every metric here can be computed without a model and without a human, so a
prompt change is judged by whether the number moved rather than by whether the
output "feels" better. Anything needing taste is left to a person; anything
that can be counted is counted.
"""

from .metrics import (  # noqa: F401
    digest_report,
    image_set_report,
    lexical_diversity,
    repeated_openings,
    script_report,
)
