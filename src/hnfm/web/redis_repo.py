"""Enhanced Redis operations with versioning and manifest management"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from .models import (
    VersionedSegment,
    ProcessingManifest,
    EnhancedPipelineStatus,
    PipelineStepStatus,
)
from .database import ContentDatabase

logger = logging.getLogger(__name__)


class RedisRepository:
    """Enhanced Redis operations with versioning and manifest management"""

    def __init__(self):
        self.db = ContentDatabase()
        self.redis_client = self.db.redis_client

    def _get_key(self, key_type: str, *parts) -> str:
        """Generate Redis key for different types"""
        return f"hnfm:{key_type}:{':'.join(str(part) for part in parts)}"

    def _serialize_datetime(self, obj: Any) -> Any:
        """Serialize datetime objects for JSON storage"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    def _deserialize_datetime(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize datetime strings from JSON"""
        for field in [
            "created_at",
            "updated_at",
            "completed_at",
            "last_updated",
            "estimated_completion",
            "start_time",
            "end_time",
        ]:
            if field in data and data[field]:
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    logger.warning(
                        f"Could not parse datetime for {field}: {data[field]}"
                    )
        return data

    def get_or_create_manifest(
        self, content_id: str, options: Dict[str, Any] = None
    ) -> ProcessingManifest:
        """Get existing manifest or create new one"""
        manifest_key = self._get_key("manifest", content_id)
        manifest_data = self.redis_client.get(manifest_key)

        if manifest_data:
            try:
                manifest_dict = json.loads(manifest_data)
                manifest_dict = self._deserialize_datetime(manifest_dict)
                return ProcessingManifest(**manifest_dict)
            except Exception as e:
                logger.error(f"Error parsing existing manifest for {content_id}: {e}")
                # Fall through to create new manifest

        # Create new manifest
        manifest = ProcessingManifest(
            content_id=content_id,
            current_step="firecrawl_content",
            completed_steps=[],
            segments={},
            last_updated=datetime.now(),
            processing_options=options or {},
            pipeline_version="1.0",
            priority=1,
        )

        self.redis_client.set(manifest_key, manifest.json())
        logger.info(f"Created new manifest for content {content_id}")
        return manifest

    def update_manifest(self, manifest: ProcessingManifest) -> bool:
        """Update a processing manifest"""
        try:
            manifest_key = self._get_key("manifest", manifest.content_id)
            manifest.last_updated = datetime.now()
            self.redis_client.set(manifest_key, manifest.json())
            return True
        except Exception as e:
            logger.error(f"Error updating manifest for {manifest.content_id}: {e}")
            return False

    def create_segment(self, content_id: str, step_name: str) -> VersionedSegment:
        """Create new versioned segment for a pipeline step"""
        try:
            # Get current version
            version_key = self._get_key("segment_versions", content_id, step_name)
            current_version = self.redis_client.incr(version_key)

            segment = VersionedSegment(
                segment_id=f"{content_id}_{step_name}_v{current_version}",
                content_id=content_id,
                step_name=step_name,
                version=current_version,
                status="processing",
                created_at=datetime.now(),
                artifacts={},
                metadata={},
                retry_count=0,
            )

            # Store segment
            segment_key = self._get_key("segments", content_id, step_name)
            self.redis_client.set(segment_key, segment.json())

            # Store in segments list for content
            segments_list_key = self._get_key("segments_list", content_id)
            self.redis_client.sadd(segments_list_key, segment.segment_id)

            logger.info(
                f"Created segment {segment.segment_id} for {content_id}:{step_name}"
            )
            return segment

        except Exception as e:
            logger.error(f"Error creating segment for {content_id}:{step_name}: {e}")
            raise

    def get_segment(self, segment_id: str) -> Optional[VersionedSegment]:
        """Get a segment by ID"""
        try:
            # Find segment in all content segments
            for content_id in self.redis_client.smembers(
                self._get_key("segments_list", "*")
            ):
                segment_key = self._get_key("segments", content_id, "*")
                segment_data = self.redis_client.get(segment_key)
                if segment_data:
                    segment_dict = json.loads(segment_data)
                    if segment_dict.get("segment_id") == segment_id:
                        segment_dict = self._deserialize_datetime(segment_dict)
                        return VersionedSegment(**segment_dict)
            return None
        except Exception as e:
            logger.error(f"Error getting segment {segment_id}: {e}")
            return None

    def complete_segment(self, segment_id: str, result: Dict[str, Any]) -> bool:
        """Mark segment as completed with results"""
        try:
            segment = self.get_segment(segment_id)
            if not segment:
                logger.error(f"Segment {segment_id} not found")
                return False

            # Update segment
            segment.status = "completed"
            segment.completed_at = datetime.now()
            segment.artifacts = result.get("artifacts", {})
            segment.metadata = result.get("metadata", {})

            # Calculate processing time
            if segment.created_at:
                segment.processing_time = (
                    segment.completed_at - segment.created_at
                ).total_seconds()

            # Store updated segment
            segment_key = self._get_key(
                "segments", segment.content_id, segment.step_name
            )
            self.redis_client.set(segment_key, segment.json())

            # Update manifest
            manifest = self.get_or_create_manifest(segment.content_id)
            manifest.segments[segment.step_name] = segment
            if segment.step_name not in manifest.completed_steps:
                manifest.completed_steps.append(segment.step_name)
            manifest.current_step = self._get_next_step(segment.step_name)
            self.update_manifest(manifest)

            logger.info(f"Completed segment {segment_id}")
            return True

        except Exception as e:
            logger.error(f"Error completing segment {segment_id}: {e}")
            return False

    def fail_segment(self, segment_id: str, error: str) -> bool:
        """Mark segment as failed with error"""
        try:
            segment = self.get_segment(segment_id)
            if not segment:
                logger.error(f"Segment {segment_id} not found")
                return False

            # Update segment
            segment.status = "failed"
            segment.error = error
            segment.completed_at = datetime.now()

            # Calculate processing time
            if segment.created_at:
                segment.processing_time = (
                    segment.completed_at - segment.created_at
                ).total_seconds()

            # Store updated segment
            segment_key = self._get_key(
                "segments", segment.content_id, segment.step_name
            )
            self.redis_client.set(segment_key, segment.json())

            # Update manifest
            manifest = self.get_or_create_manifest(segment.content_id)
            manifest.segments[segment.step_name] = segment
            self.update_manifest(manifest)

            logger.info(f"Failed segment {segment_id}: {error}")
            return True

        except Exception as e:
            logger.error(f"Error failing segment {segment_id}: {e}")
            return False

    def retry_segment(self, segment_id: str) -> Optional[VersionedSegment]:
        """Retry a failed segment by creating a new version"""
        try:
            segment = self.get_segment(segment_id)
            if not segment:
                logger.error(f"Segment {segment_id} not found")
                return None

            if segment.status != "failed":
                logger.warning(f"Segment {segment_id} is not failed, cannot retry")
                return None

            # Create new version
            new_segment = self.create_segment(segment.content_id, segment.step_name)
            new_segment.retry_count = segment.retry_count + 1

            # Store updated segment
            segment_key = self._get_key(
                "segments", new_segment.content_id, new_segment.step_name
            )
            self.redis_client.set(segment_key, new_segment.json())

            logger.info(f"Retrying segment {segment_id} as {new_segment.segment_id}")
            return new_segment

        except Exception as e:
            logger.error(f"Error retrying segment {segment_id}: {e}")
            return None

    def get_enhanced_pipeline_status(
        self, content_id: str
    ) -> Optional[EnhancedPipelineStatus]:
        """Get enhanced pipeline status for a content item"""
        try:
            manifest = self.get_or_create_manifest(content_id)

            # Build step statuses
            step_statuses = []
            total_steps = len(self._get_pipeline_steps())
            completed_steps = len(manifest.completed_steps)

            for step_name in self._get_pipeline_steps():
                segment = manifest.segments.get(step_name)
                if segment:
                    step_status = PipelineStepStatus(
                        step_name=step_name,
                        status=segment.status,
                        segment_id=segment.segment_id,
                        start_time=segment.created_at,
                        end_time=segment.completed_at,
                        error=segment.error,
                        progress=100 if segment.status == "completed" else 0,
                        dependencies=self._get_step_dependencies(step_name),
                    )
                else:
                    step_status = PipelineStepStatus(
                        step_name=step_name,
                        status="pending",
                        segment_id=None,
                        start_time=None,
                        end_time=None,
                        error=None,
                        progress=0,
                        dependencies=self._get_step_dependencies(step_name),
                    )

                step_statuses.append(step_status)

            # Calculate overall progress
            progress_percentage = (
                (completed_steps / total_steps) * 100 if total_steps > 0 else 0
            )

            # Determine overall status
            if any(step.status == "failed" for step in step_statuses):
                overall_status = "failed"
            elif completed_steps == total_steps:
                overall_status = "completed"
            elif any(step.status == "processing" for step in step_statuses):
                overall_status = "processing"
            else:
                overall_status = "pending"

            return EnhancedPipelineStatus(
                content_id=content_id,
                overall_status=overall_status,
                current_step=manifest.current_step,
                step_statuses=step_statuses,
                completed_steps=manifest.completed_steps,
                failed_steps=[
                    step.step_name for step in step_statuses if step.status == "failed"
                ],
                total_steps=total_steps,
                progress_percentage=progress_percentage,
                estimated_completion=manifest.estimated_completion,
                last_updated=manifest.last_updated,
                processing_options=manifest.processing_options,
            )

        except Exception as e:
            logger.error(
                f"Error getting enhanced pipeline status for {content_id}: {e}"
            )
            return None

    def mark_content_failed(self, content_id: str, error: str) -> bool:
        """Mark a content item as failed"""
        try:
            # Update content status
            self.db.update_content(
                content_id,
                {"status": "failed", "errors": [error], "updated_at": datetime.now()},
            )

            # Update manifest
            manifest = self.get_or_create_manifest(content_id)
            manifest.current_step = "failed"
            self.update_manifest(manifest)

            logger.info(f"Marked content {content_id} as failed: {error}")
            return True

        except Exception as e:
            logger.error(f"Error marking content {content_id} as failed: {e}")
            return False

    def _get_pipeline_steps(self) -> List[str]:
        """Get list of pipeline steps in order"""
        return [
            "firecrawl_content",
            "content_processing",
            "script_generation",
            "tts_generation",
            "image_generation",
            "video_generation",
        ]

    def _get_step_dependencies(self, step_name: str) -> List[str]:
        """Get dependencies for a pipeline step"""
        dependencies = {
            "firecrawl_content": [],
            "content_processing": ["firecrawl_content"],
            "script_generation": ["content_processing"],
            "tts_generation": ["script_generation"],
            "image_generation": ["script_generation"],
            "video_generation": ["tts_generation", "image_generation"],
        }
        return dependencies.get(step_name, [])

    def _get_next_step(self, current_step: str) -> str:
        """Get the next step in the pipeline"""
        steps = self._get_pipeline_steps()
        try:
            current_index = steps.index(current_step)
            if current_index + 1 < len(steps):
                return steps[current_index + 1]
            else:
                return "completed"
        except ValueError:
            return "unknown"
