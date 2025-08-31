#!/usr/bin/env python3
"""Test ErrorResponse datetime serialization"""

import pytest
import json
from datetime import datetime
from hnfm.web.models import ErrorResponse, CustomBaseModel


class TestErrorResponseSerialization:
    """Test suite for ErrorResponse datetime serialization"""

    def test_error_response_creation(self):
        """Test that ErrorResponse can be created with datetime"""
        error_response = ErrorResponse(
            detail="Test error message",
            error_code="TEST_ERROR",
            timestamp=datetime.now()
        )

        assert error_response.detail == "Test error message"
        assert error_response.error_code == "TEST_ERROR"
        assert isinstance(error_response.timestamp, datetime)

    def test_error_response_model_dump(self):
        """Test that ErrorResponse.model_dump() properly serializes datetime"""
        now = datetime.now()
        error_response = ErrorResponse(
            detail="Test error message",
            error_code="TEST_ERROR",
            timestamp=now
        )

        # Test model_dump (Pydantic v2)
        result_dict = error_response.model_dump()

        assert result_dict["detail"] == "Test error message"
        assert result_dict["error_code"] == "TEST_ERROR"
        assert result_dict["timestamp"] == now.isoformat()  # Should be ISO string

        # Verify it's JSON serializable
        json_str = json.dumps(result_dict)
        assert isinstance(json_str, str)

    def test_error_response_model_dump_json(self):
        """Test that ErrorResponse.model_dump_json() works correctly"""
        now = datetime.now()
        error_response = ErrorResponse(
            detail="Test error message",
            error_code="TEST_ERROR",
            timestamp=now
        )

        # Test model_dump_json (Pydantic v2)
        json_str = error_response.model_dump_json()

        assert isinstance(json_str, str)

        # Parse back and verify
        parsed = json.loads(json_str)
        assert parsed["detail"] == "Test error message"
        assert parsed["error_code"] == "TEST_ERROR"
        assert parsed["timestamp"] == now.isoformat()

    def test_error_response_dict_method_deprecated(self):
        """Test that .dict() method still works but is deprecated"""
        now = datetime.now()
        error_response = ErrorResponse(
            detail="Test error message",
            error_code="TEST_ERROR",
            timestamp=now
        )

        # Test .dict() method (deprecated in Pydantic v2)
        with pytest.warns(DeprecationWarning):
            result_dict = error_response.dict()

        assert result_dict["detail"] == "Test error message"
        assert result_dict["error_code"] == "TEST_ERROR"
        assert result_dict["timestamp"] == now.isoformat()  # Should be ISO string

        # Verify it's JSON serializable
        json_str = json.dumps(result_dict)
        assert isinstance(json_str, str)

    def test_error_response_json_method_deprecated(self):
        """Test that .json() method still works but is deprecated"""
        now = datetime.now()
        error_response = ErrorResponse(
            detail="Test error message",
            error_code="TEST_ERROR",
            timestamp=now
        )

        # Test .json() method (deprecated in Pydantic v2)
        with pytest.warns(DeprecationWarning):
            json_str = error_response.json()

        assert isinstance(json_str, str)

        # Parse back and verify
        parsed = json.loads(json_str)
        assert parsed["detail"] == "Test error message"
        assert parsed["error_code"] == "TEST_ERROR"
        assert parsed["timestamp"] == now.isoformat()

    def test_error_response_without_error_code(self):
        """Test ErrorResponse without error_code (optional field)"""
        now = datetime.now()
        error_response = ErrorResponse(
            detail="Test error message",
            timestamp=now
        )

        result_dict = error_response.model_dump()

        assert result_dict["detail"] == "Test error message"
        assert result_dict["error_code"] is None
        assert result_dict["timestamp"] == now.isoformat()

    def test_error_response_custom_base_model_inheritance(self):
        """Test that ErrorResponse properly inherits from CustomBaseModel"""
        error_response = ErrorResponse(
            detail="Test error message",
            error_code="TEST_ERROR",
            timestamp=datetime.now()
        )

        assert isinstance(error_response, CustomBaseModel)
        assert hasattr(error_response, 'model_dump')
        assert hasattr(error_response, 'model_dump_json')

    def test_error_response_validation(self):
        """Test ErrorResponse field validation"""
        # Test with invalid timestamp (should raise validation error)
        with pytest.raises(Exception):  # Pydantic validation error
            ErrorResponse(
                detail="Test error message",
                error_code="TEST_ERROR",
                timestamp="invalid_datetime"  # Should be datetime object
            )

    def test_error_response_serialization_consistency(self):
        """Test that serialization is consistent across methods"""
        now = datetime.now()
        error_response = ErrorResponse(
            detail="Test error message",
            error_code="TEST_ERROR",
            timestamp=now
        )

        # Test all serialization methods produce consistent results
        dict_result = error_response.model_dump()
        json_result = json.loads(error_response.model_dump_json())

        assert dict_result == json_result
        assert dict_result["timestamp"] == now.isoformat()
        assert json_result["timestamp"] == now.isoformat()


class TestCustomBaseModelSerialization:
    """Test suite for CustomBaseModel datetime serialization"""

    def test_custom_base_model_datetime_serialization(self):
        """Test that CustomBaseModel properly handles datetime serialization"""
        # Create a simple model inheriting from CustomBaseModel
        class TestModel(CustomBaseModel):
            name: str
            created_at: datetime

        now = datetime.now()
        test_model = TestModel(
            name="Test Model",
            created_at=now
        )

        result_dict = test_model.model_dump()

        assert result_dict["name"] == "Test Model"
        assert result_dict["created_at"] == now.isoformat()

        # Verify JSON serialization
        json_str = test_model.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["created_at"] == now.isoformat()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
