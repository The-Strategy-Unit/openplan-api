import ast
from pathlib import Path


def decorator_name(node: ast.expr) -> str | None:
    """Return the name of a decorator, including called decorators."""
    if isinstance(node, ast.Call):
        node = node.func

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return node.attr

    return None


def find_unhandled_routes(root: Path) -> list[tuple[Path, int, str]]:
    """Find Azure Functions routes missing @handle_route_errors."""
    violations = []

    for path in root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError, UnicodeDecodeError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            decorators = [decorator_name(d) for d in node.decorator_list]

            is_route = "route" in decorators
            handles_errors = "handle_route_errors" in decorators

            if is_route and not handles_errors:
                violations.append((path, node.lineno, node.name))

    return violations


def test_all_routes_handle_errors():
    violations = find_unhandled_routes(Path("src/openplan"))

    assert not violations, "\n".join(
        f"{path}:{line}: {name} is missing @handle_route_errors"
        for path, line, name in violations
    )
