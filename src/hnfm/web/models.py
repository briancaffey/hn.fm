"""Data models for the web API"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """Represents a single content item from the pipeline"""
    id: str = Field(
        ...,
        description="Unique identifier for the content item",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    title: str = Field(
        ...,
        description="Title of the content",
        example="The Future of Artificial Intelligence in Healthcare"
    )
    url: str = Field(
        ...,
        description="Original URL of the content",
        example="https://example.com/ai-healthcare-future"
    )
    content_type: str = Field(
        ...,
        description="Type of content (article, podcast, video, etc.)",
        example="article"
    )
    status: str = Field(
        ...,
        description="Processing status",
        example="completed"
    )
    created_at: datetime = Field(
        ...,
        description="When the content was created",
        example="2024-01-15T10:30:00Z"
    )
    updated_at: datetime = Field(
        ...,
        description="When the content was last updated",
        example="2024-01-15T11:45:00Z"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
        example={
            "author": "Dr. Jane Smith",
            "category": "Technology",
            "read_time": "8 min",
            "difficulty": "Intermediate"
        }
    )

    # Content fields
    raw_text: Optional[str] = Field(
        None,
        description="Raw scraped text from the source URL",
        example="Artificial intelligence is revolutionizing healthcare..."
    )
    processed_text: Optional[str] = Field(
        None,
        description="Processed/cleaned text ready for script generation",
        example="AI in healthcare is transforming patient care..."
    )
    script: Optional[str] = Field(
        None,
        description="Generated script for audio/video narration",
        example="Welcome to today's discussion on AI in healthcare..."
    )
    summary: Optional[str] = Field(
        None,
        description="Content summary and key points",
        example="This article explores how AI is improving diagnosis accuracy..."
    )

    # Media fields
    audio_path: Optional[str] = Field(
        None,
        description="Path to generated audio file",
        example="/outputs/audio/ai-healthcare-20240115.mp3"
    )
    video_path: Optional[str] = Field(
        None,
        description="Path to generated video file",
        example="/outputs/video/ai-healthcare-20240115.mp4"
    )
    image_paths: List[str] = Field(
        default_factory=list,
        description="Paths to generated images",
        example=["/outputs/images/ai-healthcare-1.png", "/outputs/images/ai-healthcare-2.png"]
    )

    # Processing info
    processing_steps: List[str] = Field(
        default_factory=list,
        description="Completed processing steps",
        example=["scraped", "processed", "script_generated", "audio_created"]
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Any processing errors encountered",
        example=["Image generation failed: API timeout"]
    )


class ContentListResponse(BaseModel):
    """Response model for listing content items"""
    items: List[ContentItem] = Field(..., description="List of content items")
    total: int = Field(..., description="Total number of items", example=42)
    page: int = Field(..., description="Current page number", example=1)
    per_page: int = Field(..., description="Items per page", example=20)
    has_next: bool = Field(..., description="Whether there are more pages", example=True)
    has_prev: bool = Field(..., description="Whether there are previous pages", example=False)


class ContentCreateRequest(BaseModel):
    """Request model for creating new content"""
    url: str = Field(
        ...,
        description="URL to scrape and process",
        example="https://example.com/article",
        pattern=r"^https?://.+"
    )
    content_type: str = Field(
        default="article",
        description="Type of content to generate",
        example="article",
        pattern="^(article|podcast|video|news|blog)$"
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Processing options and configuration",
        example={
            "voice": "en-US-Standard-A",
            "speed": 1.0,
            "quality": "high",
            "max_length": 5000
        }
    )


class ContentUpdateRequest(BaseModel):
    """Request model for updating content"""
    title: Optional[str] = Field(
        None,
        description="New title for the content item",
        example="Updated Article Title"
    )
    status: Optional[str] = Field(
        None,
        description="New processing status",
        example="completed",
        pattern="^(pending|processing|completed|failed|cancelled)$"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated metadata and processing options",
        example={
            "priority": "high",
            "tags": ["tech", "ai"],
            "notes": "User requested changes"
        }
    )


class PipelineStatus(BaseModel):
    """Pipeline status information"""
    is_running: bool = Field(..., description="Whether the pipeline is currently running", example=False)
    active_jobs: int = Field(..., description="Number of active jobs", example=3)
    completed_today: int = Field(..., description="Number of jobs completed today", example=15)
    total_processed: int = Field(..., description="Total number of processed items", example=127)
    last_completion: Optional[datetime] = Field(None, description="Last completion time", example="2024-01-15T14:30:00Z")


class HealthCheck(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status", example="healthy")
    timestamp: datetime = Field(..., description="Current timestamp", example="2024-01-15T15:00:00Z")
    version: str = Field(..., description="API version", example="0.1.0")
    redis_status: str = Field(..., description="Redis connection status", example="healthy")


class ServiceStatus(BaseModel):
    """Individual service status"""
    name: str = Field(..., description="Service name", example="Local LLM")
    url: str = Field(..., description="Service URL", example="http://192.168.5.253:1234/v1")
    status: str = Field(..., description="Service status (online/offline/error)", example="online")
    response_time: float = Field(..., description="Response time in seconds", example=0.107)
    error_message: Optional[str] = Field(None, description="Error message if any", example="Connection timeout")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional service details",
        example={"models": 0, "version": "1.0.0"}
    )


class ServicesStatusResponse(BaseModel):
    """Response model for services status"""
    all_healthy: bool = Field(..., description="Whether all services are healthy", example=False)
    services: List[ServiceStatus] = Field(..., description="List of service statuses")
    timestamp: datetime = Field(..., description="When the status was checked", example="2024-01-15T15:00:00Z")


class TaskResponse(BaseModel):
    """Response model for task operations"""
    message: str = Field(..., description="Status message", example="Task queued successfully")
    task_id: str = Field(..., description="Unique task identifier", example="550e8400-e29b-41d4-a716-446655440000")
    status: str = Field(..., description="Task status", example="queued")


class TaskStatus(BaseModel):
    """Response model for task status"""
    task_id: str = Field(..., description="Unique task identifier", example="550e8400-e29b-41d4-a716-446655440000")
    status: str = Field(..., description="Task status", example="SUCCESS")
    ready: bool = Field(..., description="Whether task is complete", example=True)
    successful: bool = Field(..., description="Whether task succeeded", example=True)
    failed: bool = Field(..., description="Whether task failed", example=False)
    result: Optional[Any] = Field(None, description="Task result if successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    info: Optional[Dict[str, Any]] = Field(None, description="Progress information")


class ActiveTasksResponse(BaseModel):
    """Response model for active tasks"""
    active_tasks: List[Dict[str, Any]] = Field(..., description="List of active tasks with worker information")


class ErrorResponse(BaseModel):
    """Standard error response model"""
    detail: str = Field(..., description="Error message", example="Content not found")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling", example="CONTENT_NOT_FOUND")
    timestamp: datetime = Field(..., description="When the error occurred", example="2024-01-15T15:00:00Z")
