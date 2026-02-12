"""Performance benchmark: generate sample files and time Rust load_all() and search()."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

try:
    from buvis.pybase.zettel._core import load_all, search

    HAS_RUST = True
except ImportError:
    HAS_RUST = False

pytestmark = pytest.mark.skipif(not HAS_RUST, reason="Rust _core not available")

SAMPLE_COUNT = 5000
MAX_TIME_SECONDS = 1.0  # generous limit for CI


def _generate_sample_files(directory: Path, count: int) -> None:
    """Generate sample markdown files with front matter."""
    for i in range(count):
        ts = f"2024{(i % 12 + 1):02d}{(i % 28 + 1):02d}{(i % 24):02d}{(i % 60):02d}00"
        filename = f"{ts} Sample note {i}.md"
        content = f"""---
id: {i}
title: Sample note {i}
date: 2024-{(i % 12 + 1):02d}-{(i % 28 + 1):02d} {(i % 24):02d}:{(i % 60):02d}:00 +00:00
type: note
tags:
  - sample
  - benchmark
  - tag-{i % 50}
publish: {"true" if i % 3 == 0 else "false"}
processed: false
---

## Content

This is sample note number {i}. It contains some body text
to make the file more realistic for parsing benchmarks.

## Details

Additional section with more content for note {i}.
"""
        (directory / filename).write_text(content)


class TestLoadAllPerformance:
    def test_load_5000_files_under_threshold(self, tmp_path):
        _generate_sample_files(tmp_path, SAMPLE_COUNT)

        # Warm up (first call compiles regexes etc)
        load_all(str(tmp_path))

        # Timed run
        start = time.perf_counter()
        results = load_all(str(tmp_path))
        elapsed = time.perf_counter() - start

        assert len(results) == SAMPLE_COUNT
        print(f"\nload_all({SAMPLE_COUNT} files): {elapsed:.3f}s")
        assert elapsed < MAX_TIME_SECONDS, f"load_all took {elapsed:.3f}s, exceeds {MAX_TIME_SECONDS}s"


class TestSearchPerformance:
    def test_search_returns_matches(self, tmp_path):
        _generate_sample_files(tmp_path, 100)
        results = search(str(tmp_path), "sample")
        assert len(results) == 100  # all files contain "sample"

    def test_search_no_matches(self, tmp_path):
        _generate_sample_files(tmp_path, 100)
        results = search(str(tmp_path), "nonexistent-xyzzy")
        assert len(results) == 0

    def test_search_case_insensitive(self, tmp_path):
        _generate_sample_files(tmp_path, 10)
        lower = search(str(tmp_path), "sample")
        upper = search(str(tmp_path), "SAMPLE")
        assert len(lower) == len(upper)

    def test_search_5000_files_under_threshold(self, tmp_path):
        _generate_sample_files(tmp_path, SAMPLE_COUNT)

        # Warm up
        search(str(tmp_path), "benchmark")

        start = time.perf_counter()
        results = search(str(tmp_path), "benchmark")
        elapsed = time.perf_counter() - start

        assert len(results) == SAMPLE_COUNT
        print(f"\nsearch({SAMPLE_COUNT} files): {elapsed:.3f}s")
        assert elapsed < MAX_TIME_SECONDS, f"search took {elapsed:.3f}s, exceeds {MAX_TIME_SECONDS}s"
