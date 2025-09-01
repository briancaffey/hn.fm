#!/usr/bin/env python3
"""Test script for the hn.fm web server"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hnfm.web.database import ContentDatabase
from hnfm.web.models import ContentItem
from datetime import datetime


async def test_database():
    """Test the Redis database connection and operations"""
    print("Testing Redis database connection...")

    try:
        db = ContentDatabase()

        # Test connection
        if not db.health_check():
            print("❌ Failed to connect to Redis")
            return False

        print("✅ Redis connection successful")

        # Test storing content
        test_content = {
            "id": "test-123",
            "title": "Test Article",
            "url": "https://example.com/test",
            "content_type": "article",
            "status": "pending",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "metadata": {"test": True},
            "processing_steps": [],
            "errors": [],
        }

        if db.store_content("test-123", test_content):
            print("✅ Content storage successful")
        else:
            print("❌ Content storage failed")
            return False

        # Test retrieving content
        retrieved = db.get_content("test-123")
        if retrieved and retrieved["title"] == "Test Article":
            print("✅ Content retrieval successful")
        else:
            print("❌ Content retrieval failed")
            return False

        # Test listing content
        content_list = db.list_content(per_page=10)
        if content_list["total"] > 0:
            print("✅ Content listing successful")
        else:
            print("❌ Content listing failed")
            return False

        # Test updating content
        if db.update_content("test-123", {"status": "completed"}):
            print("✅ Content update successful")
        else:
            print("❌ Content update failed")
            return False

        # Test deleting content
        if db.delete_content("test-123"):
            print("✅ Content deletion successful")
        else:
            print("❌ Content deletion failed")
            return False

        # Test pipeline status
        status = db.get_pipeline_status()
        print(f"✅ Pipeline status: {status}")

        print("\n🎉 All database tests passed!")
        return True

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


async def test_models():
    """Test the Pydantic models"""
    print("\nTesting Pydantic models...")

    try:
        # Test ContentItem model
        content_item = ContentItem(
            id="test-model",
            title="Test Model",
            url="https://example.com/model",
            content_type="article",
            status="pending",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        print("✅ ContentItem model creation successful")

        # Test serialization
        content_dict = content_item.model_dump()
        print("✅ Model serialization successful")

        # Test deserialization
        content_item_2 = ContentItem(**content_dict)
        print("✅ Model deserialization successful")

        print("🎉 All model tests passed!")
        return True

    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🧪 Running hn.fm web server tests...\n")

    # Test models first
    models_ok = await test_models()

    # Test database
    db_ok = await test_database()

    if models_ok and db_ok:
        print("\n🎉 All tests passed! The web server should work correctly.")
        print("\nTo start the server:")
        print("1. Make sure Redis is running (docker-compose up redis)")
        print("2. Run: python run_web_server.py")
        print("3. Open: http://localhost:8000")
    else:
        print("\n❌ Some tests failed. Please check the setup.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
