"""AST guard: domain modules must not import from application, infrastructure, or cli layers."""

import ast
from pathlib import Path

import pytest

DOMAIN_ROOT = Path(__file__).parent.parent.parent / "src" / "poe2_rpc" / "domain"

FORBIDDEN_PREFIXES = (
    "poe2_rpc.application",
    "poe2_rpc.infrastructure",
    "poe2_rpc.cli",
)


def collect_forbidden_imports(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for prefix in FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    violations.append(
                        f"{path.name}:{node.lineno} — forbidden import from '{module}'"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in FORBIDDEN_PREFIXES:
                    if alias.name == prefix or alias.name.startswith(prefix + "."):
                        violations.append(
                            f"{path.name}:{node.lineno} — forbidden import of '{alias.name}'"
                        )

    return violations


def test_domain_modules_do_not_import_outer_layers() -> None:
    if not DOMAIN_ROOT.exists():
        pytest.skip("domain package not yet created")

    domain_files = list(DOMAIN_ROOT.rglob("*.py"))
    assert domain_files, "No domain .py files found — check DOMAIN_ROOT path"

    all_violations: list[str] = []
    for path in sorted(domain_files):
        all_violations.extend(collect_forbidden_imports(path))

    assert not all_violations, "Domain modules import from outer layers:\n" + "\n".join(
        all_violations
    )
