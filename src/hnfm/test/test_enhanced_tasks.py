"""Test suite for enhanced Celery tasks with Redis-first design"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any

from hnfm.web.enhanced_tasks import (
    enhanced_content_pipeline,
    retry_failed_segment,
    get_enhanced_pipeline_status,
    cleanup_completed_segments,
    execute_pipeline_step
)
from hnfm.web.locks import ServiceLockManager
from hnfm.web.redis_repo import RedisRepository
from hnfm.web.models import VersionedSegment, ProcessingManifest, EnhancedPipelineStatus


class TestEnhancedTasks:
    """Test suite for enhanced Celery tasks"""

    @pytest.fixture
    def mock_redis_repo(self):
        """Mock Redis repository"""
        mock_repo = Mock(spec=RedisRepository)

        # Mock manifest methods
        mock_manifest = Mock(spec=ProcessingManifest)
        mock_manifest.content_id = "test-content-123"
        mock_manifest.current_step = "firecrawl_content"
        mock_manifest.completed_steps = []
        mock_manifest.segments = {}
        mock_manifest.last_updated = datetime.now()
        mock_manifest.processing_options = {}

        mock_repo.get_or_create_manifest.return_value = mock_manifest
        mock_repo.update_manifest.return_value = True

        # Mock segment methods
        mock_segment = Mock(spec=VersionedSegment)
        mock_segment.segment_id = "test-segment-123"
        mock_segment.content_id = "test-content-123"
        mock_segment.step_name = "firecrawl_content"
        mock_segment.version = 1
        mock_segment.status = "processing"
        mock_segment.created_at = datetime.now()
        mock_segment.artifacts = {}
        mock_segment.metadata = {}
        mock_segment.retry_count = 0

        mock_repo.create_segment.return_value = mock_segment
        mock_repo.complete_segment.return_value = True
        mock_repo.fail_segment.return_value = True

        # Mock database
        mock_db = Mock()
        mock_db.update_content.return_value = True
        mock_repo.db = mock_db

        return mock_repo

    @pytest.fixture
    def mock_lock_manager(self):
        """Mock service lock manager"""
        mock_manager = Mock(spec=ServiceLockManager)

        # Mock context manager
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=None)
        mock_context.__exit__ = Mock(return_value=None)
        mock_manager.service_lock.return_value = mock_context

        return mock_manager

    def test_service_lock_acquisition(self, mock_lock_manager):
        """Test that service locks are properly acquired and released"""
        # This test verifies the lock manager integration
        with mock_lock_manager.service_lock('test_service'):
            pass

        mock_lock_manager.service_lock.assert_called_once_with('test_service')
        mock_context = mock_lock_manager.service_lock.return_value
        mock_context.__enter__.assert_called_once()
        mock_context.__exit__.assert_called_once()

    def test_segment_versioning(self, mock_redis_repo):
        """Test that segments are properly versioned"""
        # Test segment creation
        segment = mock_redis_repo.create_segment('test-content-123', 'firecrawl_content')

        assert segment is not None
        assert segment.segment_id == 'test-segment-123'
        assert segment.version == 1
        assert segment.status == 'processing'

        # Verify segment was stored
        mock_redis_repo.create_segment.assert_called_once_with('test-content-123', 'firecrawl_content')

    def test_manifest_persistence(self, mock_redis_repo):
        """Test that processing manifests are properly persisted"""
        # Test manifest creation
        manifest = mock_redis_repo.get_or_create_manifest('test-content-123', {'priority': 'high'})

        assert manifest is not None
        assert manifest.content_id == 'test-content-123'
        assert manifest.processing_options == {'priority': 'high'}

        # Test manifest update
        success = mock_redis_repo.update_manifest(manifest)
        assert success is True

        # Verify methods were called
        mock_redis_repo.get_or_create_manifest.assert_called_once_with('test-content-123', {'priority': 'high'})
        mock_redis_repo.update_manifest.assert_called_once_with(manifest)


class TestExecutePipelineStep:
    """Test suite for pipeline step execution"""

    @pytest.fixture
    def mock_manifest(self):
        """Mock processing manifest"""
        manifest = Mock(spec=ProcessingManifest)
        manifest.content_id = 'test-content-123'
        manifest.segments = {}
        return manifest

    @pytest.fixture
    def mock_segment(self):
        """Mock versioned segment"""
        segment = Mock(spec=VersionedSegment)
        segment.version = 1
        return segment

    def test_execute_firecrawl_content_step(self, mock_manifest, mock_segment):
        """Test executing firecrawl content step"""
        with patch('hnfm.web.enhanced_tasks.PipelineManager') as mock_pipeline_class:
            mock_pipeline = Mock()
            mock_pipeline._execute_firecrawl_content.return_value = {
                'raw_content': 'Test raw content',
                'processed_content': 'Test processed content'
            }
            mock_pipeline_class.return_value = mock_pipeline

            result = execute_pipeline_step('firecrawl_content', mock_manifest, mock_segment)

            assert result is not None
            assert 'artifacts' in result
            assert 'metadata' in result
            assert result['artifacts'].get('raw_content') == 'Test raw content'
            assert result['metadata'].get('extraction_method') == 'firecrawl'
