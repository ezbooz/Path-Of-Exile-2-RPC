"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_log_line_level() -> str:
    """Sample Client.txt line that matches regex_level (verbatim contract)."""
    return (
        "2024/01/01 12:00:00 12345 cffb0734 [INFO Client 9876] : Foo (Witchhunter) is now level 42"
    )


@pytest.fixture
def sample_log_line_instance() -> str:
    """Sample Client.txt line that matches regex_instance (verbatim contract)."""
    return (
        "2024/01/01 12:00:00 12345 cffb0734 [DEBUG Client 9876] "
        'Generating level 5 area "G1_4_Brambleghast" with seed 12345'
    )
