"""Custom Pydantic types for the web API"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CustomBaseModel(BaseModel):
    """A custom base model with datetime serialization"""
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
        }
    )
