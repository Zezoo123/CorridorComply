"""
Pytest configuration and fixtures.
"""
import pytest


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow integration tests that download real data"
    )
