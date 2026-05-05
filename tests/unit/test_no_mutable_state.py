"""AST guard: domain modules must not have module-level mutable state."""

import ast
from pathlib import Path

import pytest

DOMAIN_ROOT = Path(__file__).parent.parent.parent / "src" / "poe2_rpc" / "domain"

ALLOWED_NODE_TYPES = (
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ImportFrom,
    ast.Import,
    ast.If,  # allow if TYPE_CHECKING guards
)


def _is_final_annotation(annotation: ast.expr | None) -> bool:
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name) and annotation.id == "Final":
        return True
    if isinstance(annotation, ast.Subscript):
        val = annotation.value
        if isinstance(val, ast.Name) and val.id == "Final":
            return True
        if isinstance(val, ast.Attribute) and val.attr == "Final":
            return True
    return False


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def collect_violations(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []

    for node in tree.body:
        if isinstance(node, ALLOWED_NODE_TYPES):
            continue
        if _is_docstring(node):
            continue
        if isinstance(node, ast.AnnAssign):
            if _is_final_annotation(node.annotation):
                continue
            violations.append(
                f"{path.name}:{node.lineno} — annotated assignment without Final[...]"
            )
        elif isinstance(node, ast.Assign):
            violations.append(f"{path.name}:{node.lineno} — bare module-level assignment")

    return violations


def test_domain_modules_have_no_mutable_state() -> None:
    if not DOMAIN_ROOT.exists():
        pytest.skip("domain package not yet created")

    domain_files = list(DOMAIN_ROOT.rglob("*.py"))
    assert domain_files, "No domain .py files found — check DOMAIN_ROOT path"

    all_violations: list[str] = []
    for path in sorted(domain_files):
        all_violations.extend(collect_violations(path))

    assert not all_violations, "Module-level mutable state found in domain:\n" + "\n".join(
        all_violations
    )
