import asyncio
import os
import tempfile
import time
import pytest
from backend.main import review_single_file_async, CONCURRENCY_SEMAPHORE
from backend.reviews.cache import review_cache


@pytest.mark.anyio
async def test_concurrent_review_execution_and_caching():
    review_cache.clear()

    # Create temporary directory with 3 Python files
    with tempfile.TemporaryDirectory() as temp_dir:
        files = ["file1.py", "file2.py", "file3.py"]
        for f in files:
            path = os.path.join(temp_dir, f)
            with open(path, "w", encoding="utf-8") as fp:
                fp.write(f"# Content for {f}\ndef test_{f[:5]}():\n    val = 1 + 1\n    return val\n")

        # First pass: Concurrent execution across all 3 files
        start_time = time.time()
        tasks = [
            review_single_file_async(f, temp_dir, None, CONCURRENCY_SEMAPHORE)
            for f in files
        ]
        results = await asyncio.gather(*tasks)
        first_pass_duration = time.time() - start_time

        assert len(results) == 3
        for r in results:
            assert r.error is None
            assert r.file in files

        assert review_cache.size() == 3

        # Second pass: In-memory cache hit should be virtually instantaneous (< 0.05s)
        cache_start = time.time()
        cached_tasks = [
            review_single_file_async(f, temp_dir, None, CONCURRENCY_SEMAPHORE)
            for f in files
        ]
        cached_results = await asyncio.gather(*cached_tasks)
        cache_duration = time.time() - cache_start

        assert len(cached_results) == 3
        assert cache_duration < 0.1  # Sub-100ms for all 3 cached files


@pytest.mark.anyio
async def test_error_handling_nonexistent_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        res = await review_single_file_async(
            "nonexistent.py", temp_dir, None, CONCURRENCY_SEMAPHORE
        )
        assert res.error is not None
        assert "File not found" in res.error
        assert len(res.issues) == 0


if __name__ == "__main__":
    asyncio.run(test_concurrent_review_execution_and_caching())
    asyncio.run(test_error_handling_nonexistent_file())
    print("All concurrency & caching tests passed successfully!")
