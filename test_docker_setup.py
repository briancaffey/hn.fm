#!/usr/bin/env python3
"""Test script to verify Docker setup is working correctly"""

import requests
import time
import sys
import os

def test_redis_connection():
    """Test Redis connection"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def test_web_server():
    """Test web server health endpoint"""
    try:
        response = requests.get('http://localhost:8000/health', timeout=10)
        if response.status_code == 200:
            print("✅ Web server health check successful")
            return True
        else:
            print(f"❌ Web server health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Web server connection failed: {e}")
        return False

def test_celery_worker():
    """Test Celery worker status"""
    try:
        response = requests.get('http://localhost:5555/api/workers', timeout=10)
        if response.status_code == 200:
            workers = response.json()
            if workers:
                print("✅ Celery worker is running")
                return True
            else:
                print("❌ No Celery workers found")
                return False
        else:
            print(f"❌ Celery worker check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Celery worker check failed: {e}")
        return False

def test_flower_monitoring():
    """Test Flower monitoring interface"""
    try:
        response = requests.get('http://localhost:5555/', timeout=10)
        if response.status_code == 200:
            print("✅ Flower monitoring is accessible")
            return True
        else:
            print(f"❌ Flower monitoring check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Flower monitoring check failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🐳 Testing Docker setup for hn.fm...")
    print("=" * 50)

    # Wait a bit for services to start
    print("⏳ Waiting for services to start...")
    time.sleep(5)

    tests = [
        ("Redis Connection", test_redis_connection),
        ("Web Server", test_web_server),
        ("Celery Worker", test_celery_worker),
        ("Flower Monitoring", test_flower_monitoring),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        result = test_func()
        results.append((test_name, result))

    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Docker setup is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check service logs and configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
