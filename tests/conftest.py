"""
Shared fixtures and helpers for the wiki-explorer test suite.

Provides: MOCK_ARTICLE constant, make_mock_response helper,
          mock_article fixture, and path setup.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MOCK_ARTICLE = {
    "title": "Black hole",
    "summary": "A black hole is a region of spacetime where gravity is so strong that nothing can escape.",
    "categories": ["Astrophysics", "General relativity"],
    "links": ["Albert Einstein", "General relativity", "Gravitational collapse"],
}


def make_mock_response(json_data, status_code=200, ok=True):
    """Return a MagicMock that behaves like an httpx/requests Response."""
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.ok = ok
    mock.raise_for_status = MagicMock()
    return mock


def make_error_response(exception, status_code=500):
    """Return a MagicMock response whose raise_for_status() raises exception."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.ok = False
    mock.raise_for_status.side_effect = exception
    return mock


@pytest.fixture
def mock_article():
    """Provide a fresh copy of MOCK_ARTICLE for each test."""
    return MOCK_ARTICLE.copy()
