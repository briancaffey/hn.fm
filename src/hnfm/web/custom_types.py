"""Custom Pydantic types for the web API"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Any


class CustomBaseModel(BaseModel):
    """A custom base model with datetime serialization"""

    model_config = ConfigDict(
        # Use the new Pydantic v2 serialization configuration
        ser_json_timedelta="iso8601",
        ser_json_datetime="iso8601",
    )

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Override model_dump to ensure datetime serialization"""
        result = super().model_dump(**kwargs)
        # Convert any datetime objects to ISO strings
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
        return result
