"""Data models for the web API"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .custom_types import CustomBaseModel


class HNStoryData(BaseModel):
    """Hacker News story data from the HN API"""

    id: int = Field(..., description="The item's unique id from HN")
    deleted: Optional[bool] = Field(None, description="true if the item is deleted")
    type: str = Field(
        ..., description="The type of item (job, story, comment, poll, pollopt)"
    )
    by: Optional[str] = Field(None, description="The username of the item's author")
    time: int = Field(..., description="Creation date of the item, in Unix Time")
    text: Optional[str] = Field(
        None, description="The comment, story or poll text. HTML."
    )
    dead: Optional[bool] = Field(None, description="true if the item is dead")
    parent: Optional[int] = Field(
        None,
        description="The comment's parent: either another comment or the relevant story",
    )
    poll: Optional[int] = Field(None, description="The pollopt's associated poll")
    kids: Optional[List[int]] = Field(
        None, description="The ids of the item's comments, in ranked display order"
    )
    url: Optional[str] = Field(None, description="The URL of the story")
    score: Optional[int] = Field(
        None, description="The story's score, or the votes for a pollopt"
    )
    title: Optional[str] = Field(
        None, description="The title of the story, poll or job. HTML."
    )
    parts: Optional[List[int]] = Field(
        None, description="A list of related pollopts, in display order"
    )
    descendants: Optional[int] = Field(
        None, description="In the case of stories or polls, the total comment count"
    )


class ContentItem(CustomBaseModel):
    """Represents a single content item from the pipeline"""

    id: str = Field(
        ...,
        description="Unique identifier for the content item",
        example="550e8400-e29b-41d4-a716-446655440000",
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
    content_type: str = Field(
        ...,
        description="Type of content (article, podcast, video, etc.)",
        example="article",
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
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
        example={
            "author": "Dr. Jane Smith",
            "category": "Technology",
            "read_time": "8 min",
            "difficulty": "Intermediate",
        },
    )

    # Hacker News specific fields
    hn_story_data: Optional[HNStoryData] = Field(
        None, description="Original Hacker News story data if this content came from HN"
    )

    # Content fields
    raw_text: Optional[str] = Field(
        None,
        description="Raw scraped text from the source URL",
        example="Artificial intelligence is revolutionizing healthcare...",
    )
    processed_text: Optional[str] = Field(
        None,
        description="Processed/cleaned text ready for script generation",
        example="AI in healthcare is transforming patient care...",
    )
    script: Optional[str] = Field(
        None,
        description="Generated script for audio/video narration",
        example="Welcome to today's discussion on AI in healthcare...",
    )
    summary: Optional[str] = Field(
        None,
        description="Content summary and key points",
        example="This article explores how AI is improving diagnosis accuracy...",
    )

    # Media fields
    audio_path: Optional[str] = Field(
        None,
        description="Path to generated audio file",
        example="/outputs/audio/ai-healthcare-20240115.mp3",
    )
    video_path: Optional[str] = Field(
        None,
        description="Path to generated video file",
        example="/outputs/video/ai-healthcare-20240115.mp4",
    )
    image_paths: List[str] = Field(
        default_factory=list,
        description="Paths to generated images",
        example=[
            "/outputs/images/ai-healthcare-1.png",
            "/outputs/images/ai-healthcare-2.png",
        ],
    )

    # Processing info
    processing_steps: List[str] = Field(
        default_factory=list,
        description="Completed processing steps",
        example=["scraped", "processed", "script_generated", "audio_created"],
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Any processing errors encountered",
        example=["Image generation failed: API timeout"],
    )


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
        description="URL to scrape and process",
        example="https://example.com/article",
        pattern=r"^https?://.+",
    )
    content_type: str = Field(
        default="article",
        description="Type of content to generate",
        example="article",
        pattern="^(article|podcast|video|news|blog)$",
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
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated metadata and processing options",
        example={
            "priority": "high",
            "tags": ["tech", "ai"],
            "notes": "User requested changes",
        },
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


class VersionedSegment(CustomBaseModel):
    """Represents a versioned pipeline segment with artifact tracking"""

    segment_id: str = Field(..., description="Unique segment identifier")
    content_id: str = Field(..., description="Parent content item ID")
    step_name: str = Field(..., description="Pipeline step name")
    version: int = Field(..., description="Segment version number")
    status: str = Field(..., description="Segment processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    artifacts: Dict[str, str] = Field(
        default_factory=dict, description="Output file paths"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Processing metadata"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    processing_time: Optional[float] = Field(
        None, description="Processing time in seconds"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts")


class ProcessingManifest(CustomBaseModel):
    """Tracks complete processing state for a content item"""

    content_id: str = Field(..., description="Content item identifier")
    current_step: str = Field(..., description="Currently executing step")
    completed_steps: List[str] = Field(
        default_factory=list, description="Completed steps"
    )
    segments: Dict[str, VersionedSegment] = Field(
        default_factory=dict, description="Step segments"
    )
    last_updated: datetime = Field(..., description="Last update timestamp")
    processing_options: Dict[str, Any] = Field(
        default_factory=dict, description="Processing configuration"
    )
    pipeline_version: str = Field(default="1.0", description="Pipeline version")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )
    priority: int = Field(default=1, description="Processing priority (1-10)")


class ServiceLockStatus(BaseModel):
    """Status information for a service lock"""

    service_name: str = Field(..., description="Service name")
    is_locked: bool = Field(..., description="Whether service is currently locked")
    locked_at: Optional[datetime] = Field(None, description="When lock was acquired")
    ttl: Optional[int] = Field(None, description="Time to live in seconds")
    lock_owner: Optional[str] = Field(None, description="Lock owner identifier")


class PipelineStepStatus(BaseModel):
    """Status of a pipeline step execution"""

    step_name: str = Field(..., description="Pipeline step name")
    status: str = Field(
        ..., description="Step status (pending, processing, completed, failed)"
    )
    segment_id: Optional[str] = Field(None, description="Associated segment ID")
    start_time: Optional[datetime] = Field(None, description="Step start time")
    end_time: Optional[datetime] = Field(None, description="Step completion time")
    error: Optional[str] = Field(None, description="Error message if failed")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    dependencies: List[str] = Field(
        default_factory=list, description="Required dependencies"
    )


class EnhancedPipelineStatus(CustomBaseModel):
    """Enhanced pipeline status with step-level details"""

    content_id: str = Field(..., description="Content item identifier")
    overall_status: str = Field(..., description="Overall pipeline status")
    current_step: Optional[str] = Field(None, description="Currently executing step")
    step_statuses: List[PipelineStepStatus] = Field(
        default_factory=list, description="Individual step statuses"
    )
    completed_steps: List[str] = Field(
        default_factory=list, description="Completed steps"
    )
    failed_steps: List[str] = Field(default_factory=list, description="Failed steps")
    total_steps: int = Field(..., description="Total number of steps")
    progress_percentage: float = Field(..., description="Overall progress (0-100)")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )
    last_updated: datetime = Field(..., description="Last status update")
    processing_options: Dict[str, Any] = Field(
        default_factory=dict, description="Processing configuration"
    )
