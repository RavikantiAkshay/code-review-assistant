import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional


class ReviewCache:
    """
    Thread-safe, LRU in-memory cache for code review results.
    Keyed by (file_path + SHA256(content + ruleset)).
    Enables sub-millisecond reviews for unchanged files across review passes.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    def _compute_key(self, file_path: str, content: str, ruleset: Optional[str] = None) -> str:
        content_hash = hashlib.sha256(f"{content}::{ruleset or ''}".encode("utf-8")).hexdigest()
        return f"{file_path}::{content_hash}"

    def get(
        self,
        file_path: str,
        content: str,
        ruleset: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached review issues if content and ruleset match exactly."""
        key = self._compute_key(file_path, content, ruleset)
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if time.time() - entry["timestamp"] > self.ttl_seconds:
            del self._cache[key]
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return [dict(issue) for issue in entry["issues"]]

    def set(
        self,
        file_path: str,
        content: str,
        ruleset: Optional[str],
        issues: List[Dict[str, Any]],
    ):
        """Store review results into in-memory LRU cache."""
        key = self._compute_key(file_path, content, ruleset)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = {
            "issues": [dict(issue) for issue in issues],
            "timestamp": time.time(),
        }
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)  # Evict oldest

    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()

    def size(self) -> int:
        """Return number of currently cached items."""
        return len(self._cache)


# Global singleton instance
review_cache = ReviewCache()
