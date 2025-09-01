"""Data models for the web API"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .custom_types import CustomBaseModel


class ContentItem(CustomBaseModel):
    """Represents a single content item from the pipeline"""

    id: str = Field(
        ...,
        description="Unique identifier for the content item (UUID)",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    hn_item_id: Optional[int] = Field(
        None,
        description="Hacker News item ID (optional)",
        example=123456789,
    )
    title: str = Field(
        ...,
        description="Title of the content",
        example="The Future of Artificial Intelligence in Healthcare",
    )
    url: str = Field(
        ...,
        description="Original URL of the content",
        example="https://example.com/ai-healthcare-future",
    )
    post_text: Optional[str] = Field(
        None,
        description="Text content from the HN post",
        example="This article explores how AI is improving diagnosis accuracy...",
    )
    status: str = Field(..., description="Processing status", example="completed")
    created_at: str = Field(
        ...,
        description="When the content was created (ISO format)",
        example="2024-01-15T10:30:00Z",
    )
    updated_at: str = Field(
        ...,
        description="When the content was last updated (ISO format)",
        example="2024-01-15T11:45:00Z",
    )

    # Content fields
    raw_content: Optional[str] = Field(
        None,
        description="Raw scraped text from the source URL",
        example="Artificial intelligence is revolutionizing healthcare...",
    )
    processed_content: Optional[str] = Field(
        None,
        description="Processed/cleaned text ready for script generation",
        example="AI in healthcare is transforming patient care...",
    )
    script: Optional[str] = Field(
        None,
        description="Generated script for audio/video narration",
        example="Welcome to today's discussion on AI in healthcare...",
    )

    # Media fields
    audio_file_path: Optional[str] = Field(
        None,
        description="Path to generated combined audio file",
        example="/outputs/audio/ai-healthcare-20240115.mp3",
    )

    # ASR data (JSON)
    asr_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Automated speech recognition data in JSON format",
        example={
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "Welcome to today's discussion"}
            ]
        },
    )


# Response models for API endpoints
class ContentListResponse(BaseModel):
    """Response model for listing content items"""

    items: List[ContentItem] = Field(..., description="List of content items")
    total: int = Field(..., description="Total number of items", example=42)
    page: int = Field(..., description="Current page number", example=1)
    per_page: int = Field(..., description="Items per page", example=20)
    has_next: bool = Field(
        ..., description="Whether there are more pages", example=True
    )
    has_prev: bool = Field(
        ..., description="Whether there are previous pages", example=False
    )


class ContentCreateRequest(BaseModel):
    """Request model for creating new content"""

    url: str = Field(
        ...,
        description="URL to process",
        example="https://example.com/article",
    )
    content_type: str = Field(
        default="article",
        description="Type of content",
        example="article",
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Processing options and configuration",
        example={
            "voice": "en-US-Standard-A",
            "speed": 1.0,
            "quality": "high",
            "max_length": 5000,
        },
    )


class PipelineProcessRequest(BaseModel):
    """Request model for processing existing content through pipeline"""

    hn_item_id: int = Field(
        ...,
        description="Hacker News item ID to process",
        example=123456789,
    )


class ContentUpdateRequest(BaseModel):
    """Request model for updating content"""

    title: Optional[str] = Field(
        None,
        description="New title for the content item",
        example="Updated Article Title",
    )
    status: Optional[str] = Field(
        None,
        description="New processing status",
        example="completed",
        pattern="^(pending|processing|completed|failed|cancelled)$",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata",
        example={"voice": "en-US-Standard-A", "speed": 1.0},
    )


class PipelineStatus(CustomBaseModel):
    """Pipeline status information"""

    is_running: bool = Field(
        ..., description="Whether the pipeline is currently running", example=False
    )
    active_jobs: int = Field(..., description="Number of active jobs", example=3)
    completed_today: int = Field(
        ..., description="Number of jobs completed today", example=15
    )
    total_processed: int = Field(
        ..., description="Total number of processed items", example=127
    )
    last_completion: Optional[datetime] = Field(
        None, description="Last completion time", example="2024-01-15T14:30:00Z"
    )


class HealthCheck(CustomBaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status", example="healthy")
    timestamp: datetime = Field(
        ..., description="Current timestamp", example="2024-01-15T15:00:00Z"
    )
    version: str = Field(..., description="API version", example="0.1.0")
    redis_status: str = Field(
        ..., description="Redis connection status", example="healthy"
    )


class ServiceStatus(BaseModel):
    """Individual service status"""

    name: str = Field(..., description="Service name", example="Local LLM")
    url: str = Field(
        ..., description="Service URL", example="http://192.168.5.253:1234/v1"
    )
    status: str = Field(
        ..., description="Service status (online/offline/error)", example="online"
    )
    response_time: float = Field(
        ..., description="Response time in seconds", example=0.107
    )
    error_message: Optional[str] = Field(
        None, description="Error message if any", example="Connection timeout"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional service details",
        example={"models": 0, "version": "1.0.0"},
    )


class ServicesStatusResponse(CustomBaseModel):
    """Response model for services status"""

    all_healthy: bool = Field(
        ..., description="Whether all services are healthy", example=False
    )
    services: List[ServiceStatus] = Field(..., description="List of service statuses")
    timestamp: datetime = Field(
        ..., description="When the status was checked", example="2024-01-15T15:00:00Z"
    )
