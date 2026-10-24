import pytest
from backend.reviews.cache import ReviewCache


def test_cache_set_and_get():
    cache = ReviewCache(max_size=10, ttl_seconds=60)
    file_path = "src/auth.py"
    content = "def test(): pass"
    issues = [{"line": 1, "message": "test issue", "severity": "low"}]

    cache.set(file_path, content, "pep8", issues)
    cached = cache.get(file_path, content, "pep8")

    assert cached is not None
    assert len(cached) == 1
    assert cached[0]["message"] == "test issue"


def test_cache_miss_on_content_change():
    cache = ReviewCache(max_size=10, ttl_seconds=60)
    file_path = "src/auth.py"
    content1 = "def test(): pass"
    content2 = "def test(): return True"
    issues = [{"line": 1, "message": "issue 1"}]

    cache.set(file_path, content1, None, issues)

    # Modified content should miss cache
    assert cache.get(file_path, content2, None) is None
    # Original content should hit cache
    assert cache.get(file_path, content1, None) is not None


def test_cache_miss_on_ruleset_change():
    cache = ReviewCache(max_size=10, ttl_seconds=60)
    file_path = "src/auth.py"
    content = "def test(): pass"
    issues = [{"line": 1, "message": "issue 1"}]

    cache.set(file_path, content, "pep8", issues)

    # Different ruleset should miss cache
    assert cache.get(file_path, content, "owasp-top-10") is None
    assert cache.get(file_path, content, "pep8") is not None


def test_lru_eviction():
    cache = ReviewCache(max_size=2, ttl_seconds=60)

    cache.set("file1.py", "c1", None, [{"id": 1}])
    cache.set("file2.py", "c2", None, [{"id": 2}])
    assert cache.size() == 2

    # Adding third file should evict file1.py (oldest LRU)
    cache.set("file3.py", "c3", None, [{"id": 3}])
    assert cache.size() == 2
    assert cache.get("file1.py", "c1", None) is None
    assert cache.get("file2.py", "c2", None) is not None
    assert cache.get("file3.py", "c3", None) is not None


if __name__ == "__main__":
    test_cache_set_and_get()
    test_cache_miss_on_content_change()
    test_cache_miss_on_ruleset_change()
    test_lru_eviction()
    print("All cache tests passed!")
