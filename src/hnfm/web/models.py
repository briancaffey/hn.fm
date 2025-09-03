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
    content_clean: str = Field(..., description="Cleaned text (whitespace/boilerplate removed)")
    summary: str = Field(..., description="LLM summary text")
    short_description: str = Field(..., description="Short 1-2 sentence description of the article")
    tags: List[str] = Field(..., description="List of lowercase alphanumeric tags (2-6 tags)")
    emoji: List[str] = Field(..., description="List of exactly 4 emoji characters describing the content")
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
