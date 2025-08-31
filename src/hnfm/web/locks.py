"""Redis-based service locking for external service concurrency control"""

import time
import logging
from contextlib import contextmanager
from typing import Optional
import redis

logger = logging.getLogger(__name__)


class ServiceLockManager:
    """Manages Redis-based locks for external service concurrency control"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)

    @contextmanager
    def service_lock(self, service_name: str, lock_timeout: int = 300):
        """
        Redis-based lock for external services to ensure single concurrency

        Args:
            service_name: Service identifier (tts, asr, vision, firecrawl, llm)
            lock_timeout: Lock timeout in seconds (default: 5 minutes)
        """
        lock_key = f"hnfm:lock:{service_name}"
        lock_value = f"locked_at_{int(time.time())}"

        try:
            # Attempt to acquire lock
            acquired = self.redis_client.set(
                lock_key, lock_value, ex=lock_timeout, nx=True
            )

            if not acquired:
                # Check if lock is stale (expired but not cleaned up)
                current_lock = self.redis_client.get(lock_key)
                if current_lock:
                    raise RuntimeError(
                        f"Service {service_name} is currently busy (lock: {current_lock})"
                    )
                else:
                    # Lock was expired, try to acquire again
                    acquired = self.redis_client.set(
                        lock_key, lock_value, ex=lock_timeout, nx=True
                    )
                    if not acquired:
                        raise RuntimeError(f"Service {service_name} is currently busy")

            self.logger.info(
                f"Acquired lock for {service_name} (timeout: {lock_timeout}s)"
            )
            yield

        except Exception as e:
            self.logger.error(f"Error in service lock for {service_name}: {e}")
            raise
        finally:
            # Release lock if we still own it
            try:
                if self.redis_client.get(lock_key) == lock_value:
                    self.redis_client.delete(lock_key)
                    self.logger.info(f"Released lock for {service_name}")
                else:
                    self.logger.warning(
                        f"Lock for {service_name} was already released or taken by another process"
                    )
            except Exception as e:
                self.logger.error(f"Error releasing lock for {service_name}: {e}")

    def is_service_locked(self, service_name: str) -> bool:
        """Check if a service is currently locked"""
        lock_key = f"hnfm:lock:{service_name}"
        return bool(self.redis_client.exists(lock_key))

    def get_lock_info(self, service_name: str) -> Optional[dict]:
        """Get information about a service lock"""
        lock_key = f"hnfm:lock:{service_name}"
        lock_value = self.redis_client.get(lock_key)

        if lock_value:
            try:
                # Parse the lock value to extract timestamp
                if lock_value.startswith("locked_at_"):
                    lock_time = int(lock_value.split("_")[-1])
                    ttl = self.redis_client.ttl(lock_key)
                    return {
                        "locked_at": lock_time,
                        "ttl": ttl,
                        "lock_value": lock_value,
                    }
            except (ValueError, IndexError):
                pass

        return None

    def force_release_lock(self, service_name: str) -> bool:
        """Force release a service lock (use with caution)"""
        lock_key = f"hnfm:lock:{service_name}"
        try:
            result = self.redis_client.delete(lock_key)
            if result:
                self.logger.warning(f"Force released lock for {service_name}")
            return bool(result)
        except Exception as e:
            self.logger.error(f"Error force releasing lock for {service_name}: {e}")
            return False
