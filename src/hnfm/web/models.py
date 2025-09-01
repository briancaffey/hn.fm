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
    hn_item_id: int = Field(
        ...,
        description="Hacker News item ID",
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


class AudioSegment(CustomBaseModel):
    """Represents a single audio segment for TTS narration"""

    id: str = Field(
        ...,
        description="Unique identifier for the audio segment (UUID)",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    content_item_id: str = Field(
        ...,
        description="Content item UUID this segment belongs to",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    text: str = Field(
        ...,
        description="Text to be narrated",
        example="Welcome to today's discussion on AI in healthcare.",
    )
    sequence_number: int = Field(
        ...,
        description="Sequence number for ordering",
        example=1,
    )
    audio_file_path: Optional[str] = Field(
        None,
        description="Path to the generated audio file",
        example="/outputs/audio/segment_001.wav",
    )


class ImageSegment(CustomBaseModel):
    """Represents a single image segment for visual content"""

    id: str = Field(
        ...,
        description="Unique identifier for the image segment (UUID)",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    content_item_id: str = Field(
        ...,
        description="Content item UUID this segment belongs to",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    prompt: str = Field(
        ...,
        description="Image generation prompt",
        example="A detailed cartoon style illustration of AI in healthcare",
    )
    sequence_number: int = Field(
        ...,
        description="Sequence number for ordering",
        example=1,
    )
    image_file_path: Optional[str] = Field(
        None,
        description="Path to the generated image file",
        example="/outputs/images/image_001.png",
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

    hn_item_id: int = Field(
        ...,
        description="Hacker News item ID to process",
        example=123456789,
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


class TaskResponse(BaseModel):
    """Response model for task operations"""

    message: str = Field(
        ..., description="Status message", example="Task queued successfully"
    )
    task_id: str = Field(
        ...,
        description="Unique task identifier",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    status: str = Field(..., description="Task status", example="queued")


class TaskStatus(BaseModel):
    """Response model for task status"""

    task_id: str = Field(
        ...,
        description="Unique task identifier",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    status: str = Field(..., description="Task status", example="SUCCESS")
    ready: bool = Field(..., description="Whether task is complete", example=True)
    successful: bool = Field(..., description="Whether task succeeded", example=True)
    failed: bool = Field(..., description="Whether task failed", example=False)
    result: Optional[Any] = Field(None, description="Task result if successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    info: Optional[Dict[str, Any]] = Field(None, description="Progress information")


class ActiveTasksResponse(BaseModel):
    """Response model for active tasks"""

    active_tasks: List[Dict[str, Any]] = Field(
        ..., description="List of active tasks with worker information"
    )


class ErrorResponse(CustomBaseModel):
    """Standard error response model"""

    detail: str = Field(..., description="Error message", example="Content not found")
    error_code: Optional[str] = Field(
        None,
        description="Error code for programmatic handling",
        example="CONTENT_NOT_FOUND",
    )
    timestamp: datetime = Field(
        ..., description="When the error occurred", example="2024-01-15T15:00:00Z"
    )
