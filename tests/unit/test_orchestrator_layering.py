"""AST guard: orchestrator must not import from poe2_rpc.infrastructure.*"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ORCHESTRATOR_PATH = (
    Path(__file__).parent.parent.parent / "src" / "poe2_rpc" / "application" / "orchestrator.py"
)

FORBIDDEN_PREFIX = "poe2_rpc.infrastructure"


def _collect_forbidden(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == FORBIDDEN_PREFIX or module.startswith(FORBIDDEN_PREFIX + "."):
                violations.append(f"line {node.lineno}: forbidden 'from {module} import ...'")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == FORBIDDEN_PREFIX or alias.name.startswith(FORBIDDEN_PREFIX + "."):
                    violations.append(f"line {node.lineno}: forbidden 'import {alias.name}'")
    return violations


def test_orchestrator_has_no_infrastructure_imports() -> None:
    if not ORCHESTRATOR_PATH.exists():
        pytest.fail(f"orchestrator.py not found at {ORCHESTRATOR_PATH}")

    violations = _collect_forbidden(ORCHESTRATOR_PATH)
    assert not violations, (
        "orchestrator.py imports from poe2_rpc.infrastructure (Principle 4 violation):\n"
        + "\n".join(violations)
    )
