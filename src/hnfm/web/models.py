"""Data models for the web API"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HNItem(BaseModel):
    """Hacker News item model"""

    id: int
    type: Optional[str] = None
    by: Optional[str] = None
    time: Optional[int] = None  # Unix seconds
    url: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None
    score: Optional[int] = None
    descendants: Optional[int] = None
    kids: Optional[List[int]] = None


class HealthCheck(BaseModel):
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


class ServicesStatusResponse(BaseModel):
    """Response model for services status"""

    all_healthy: bool = Field(
        ..., description="Whether all services are healthy", example=False
    )
    services: List[ServiceStatus] = Field(..., description="List of service statuses")
    timestamp: datetime = Field(
        ..., description="When the status was checked", example="2024-01-15T15:00:00Z"
    )


class ProcessedRun(BaseModel):
    """Model for processed HN item runs"""

    key: str = Field(..., description="Redis key format: hnfm:item:{item_id}:run:{run}")
    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number for this item")
    created_at: datetime = Field(..., description="When the run was created")
    source_url: str = Field(..., description="Original URL that was scraped")
    content_raw: str = Field(..., description="Raw text/markdown from Firecrawl")
    content_clean: str = Field(
        ..., description="Cleaned text (whitespace/boilerplate removed)"
    )
    summary: str = Field(..., description="LLM summary text")
    short_description: str = Field(
        ..., description="Short 1-2 sentence description of the article"
    )
    tags: List[str] = Field(
        ..., description="List of lowercase alphanumeric tags (2-6 tags)"
    )
    emoji: List[str] = Field(
        ..., description="List of exactly 4 emoji characters describing the content"
    )
    haiku: str = Field(..., description="Haiku describing the article content")


class RunSummary(BaseModel):
    """Summary view of a run for listing"""

    run: int = Field(..., description="Run number")
    summary: str = Field(..., description="LLM summary text")


class RunsListResponse(BaseModel):
    """Response model for listing runs"""

    item_id: int = Field(..., description="Hacker News item ID")
    runs: List[RunSummary] = Field(..., description="List of runs with summaries")
    pagination: Dict[str, int] = Field(..., description="Pagination info")


class CreateRunResponse(BaseModel):
    """Response model for creating a new run"""

    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number that was created")
    status: str = Field(..., description="Status of the operation")


class CreateRunRequest(BaseModel):
    """Request model for creating a new run"""

    continue_chain: bool = Field(
        False, description="Whether to continue the full pipeline chain"
    )


class CreateSegmentRequest(BaseModel):
    """Request model for creating a new segment"""

    continue_chain: bool = Field(
        False, description="Whether to continue the full pipeline chain"
    )


class Segment(BaseModel):
    """Model for script segments tied to a specific run"""

    key: str = Field(
        ..., description="Redis key format: hnfm:seg:{item_id}:{run}:{seg}"
    )
    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number for this item")
    seg: int = Field(..., description="Segment number within the run")
    created_at: datetime = Field(..., description="When the segment was created")
    processed_run_key: str = Field(
        ..., description="Reference to the processed run key"
    )
    script: str = Field(..., description="Full script text generated by LLM")

    # Art direction (the visual theme/style for this take)
    style_theme: Optional[str] = Field(
        default=None, description="art_direction theme key for this take's visuals"
    )
    style_theme_name: Optional[str] = Field(
        default=None, description="Human-readable theme name for this take"
    )
    aspect_format: Optional[str] = Field(
        default="16:9", description="Aspect format for this take: 16:9 | 1:1 | 9:16"
    )

    # ASR quality check (transcript-vs-script) receipt
    asr_qa: Optional[dict] = Field(
        default=None, description="ASR QA report: ratio/verdict/mismatches"
    )

    # Audio fields
    sections_total: int = Field(default=0, description="Total number of audio sections")
    audio_combined_path: Optional[str] = Field(
        default=None, description="Path to combined audio file"
    )
    audio_ready: bool = Field(
        default=False, description="Whether audio is ready for playback"
    )

    # ASR fields
    asr_json_path: Optional[str] = Field(
        default=None, description="Path to ASR JSON file with word timestamps"
    )

    # Image fields
    images_total: int = Field(
        default=0, description="Total number of image entries tracked"
    )
    images_ready: bool = Field(
        default=False, description="True when all images are generated"
    )

    # Video fields
    video_path: Optional[str] = Field(
        default=None, description="Path to generated video file"
    )
    subtitles_path: Optional[str] = Field(
        default=None, description="Path to subtitles VTT file"
    )
    video_ready: bool = Field(
        default=False, description="True when video is generated and ready"
    )


class SegmentSection(BaseModel):
    """Model for individual audio sections within a segment"""

    key: str = Field(
        ...,
        description="Redis key format: hnfm:seg:{item_id}:{run}:{seg}:sec:{section}",
    )
    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number for this item")
    seg: int = Field(..., description="Segment number within the run")
    section: int = Field(..., description="Section number within the segment (1-based)")
    text: str = Field(..., description="The exact text used for TTS")
    audio_path: Optional[str] = Field(default=None, description="Path to audio file")
    cleaned: bool = Field(
        default=False,
        description="Whether audio has been processed through studio-voice",
    )
    duration_ms: Optional[int] = Field(
        default=None, description="Duration in milliseconds"
    )
    created_at: datetime = Field(..., description="When the section was created")
    updated_at: datetime = Field(..., description="When the section was last updated")


class SegmentImage(BaseModel):
    """Model for individual image entries within a segment"""

    key: str = Field(
        ..., description="Redis key format: hnfm:seg:{item_id}:{run}:{seg}:img:{index}"
    )
    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number for this item")
    seg: int = Field(..., description="Segment number within the run")
    index: int = Field(..., description="Image index within the segment (1-based)")
    line_text: str = Field(
        ..., description="The line/section text this image illustrates"
    )
    prompt: str = Field(..., description="Generated prompt text")
    image_path: Optional[str] = Field(
        default=None, description="Path to generated image file (first frame)"
    )
    sequence_paths: Optional[List[str]] = Field(
        default=None,
        description="Ordered image-sequence frame paths (root + edits) for dynamic visuals",
    )
    video_clip_path: Optional[str] = Field(
        default=None,
        description="Optional LTX-2 motion clip (stretched) used for this section",
    )
    start_ms: Optional[int] = Field(
        default=None, description="Alignment start time in milliseconds"
    )
    duration_ms: Optional[int] = Field(
        default=None, description="Alignment duration in milliseconds"
    )
    created_at: datetime = Field(..., description="When the image was created")
    updated_at: datetime = Field(..., description="When the image was last updated")


class SegmentSummary(BaseModel):
    """Summary view of a segment for listing"""

    seg: int = Field(..., description="Segment number")
    script_preview: str = Field(..., description="First 200 characters of script")


class SegmentsListResponse(BaseModel):
    """Response model for listing segments"""

    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number")
    segments: List[SegmentSummary] = Field(
        ..., description="List of segments with previews"
    )
    pagination: Dict[str, int] = Field(..., description="Pagination info")


class CreateSegmentResponse(BaseModel):
    """Response model for creating a new segment"""

    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number")
    seg: int = Field(..., description="Segment number that was created")
    status: str = Field(..., description="Status of the operation")


class DeleteSegmentResponse(BaseModel):
    """Response model for deleting a segment"""

    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number")
    seg: int = Field(..., description="Segment number that was deleted")
    status: str = Field(..., description="Status of the operation")


class BuildAudioResponse(BaseModel):
    """Response model for building audio"""

    status: str = Field(..., description="Status of the operation")
    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number")
    seg: int = Field(..., description="Segment number")
    mode: str = Field(..., description="Build mode (all or one)")
    section: Optional[int] = Field(
        default=None, description="Section number if mode is one"
    )


class SectionsListResponse(BaseModel):
    """Response model for listing sections"""

    item_id: int = Field(..., description="Hacker News item ID")
    run: int = Field(..., description="Run number")
    seg: int = Field(..., description="Segment number")
    sections: List[Dict[str, Any]] = Field(
        ..., description="List of sections with metadata"
    )


class AllSegmentsListResponse(BaseModel):
    """Response model for listing all segments across all items and runs"""

    segments: List[Segment] = Field(..., description="List of segments")
    pagination: Dict[str, int] = Field(..., description="Pagination info")
