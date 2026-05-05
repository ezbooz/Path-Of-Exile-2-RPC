"""Conformance tests: RegexLogParser must satisfy the LogParser Protocol."""

from __future__ import annotations

from poe2_rpc.domain.ports import LogParser
from poe2_rpc.infrastructure.parsing import RegexLogParser


def test_regex_log_parser_satisfies_protocol() -> None:
    assert isinstance(RegexLogParser(), LogParser)


def test_incomplete_parser_fails_protocol_check() -> None:
    """A parser missing one of the four parse_* methods is rejected at runtime."""

    class IncompleteParser:
        @staticmethod
        def parse_level(line: str) -> None:
            return None

        @staticmethod
        def parse_instance(line: str) -> None:
            return None

        @staticmethod
        def parse_local_area_entered(line: str) -> None:
            return None

        # Intentionally missing parse_party_joined

    assert not isinstance(IncompleteParser(), LogParser)
