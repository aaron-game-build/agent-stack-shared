"""
Static boundary checks for the portable runtime package.

The runtime may describe UE tasks, but it must not directly depend on Unreal,
project bindings, or repository-specific paths. Project-specific knowledge
belongs in a project registry package.

Project-specific markers are **caller-supplied** (manifest-driven): each
consuming project passes its own forbidden text markers (project names,
absolute repo paths, game-content roots) and registry package roots — via
``.ue-py-config.json`` ``task_runtime.boundary`` when going through
``TaskService.boundary_report()``. Only the ``unreal`` import ban is a
built-in invariant (this package must stay UE-light).
"""

import ast
from dataclasses import dataclass
from pathlib import Path


BOUNDARY_SCHEMA_VERSION = "ue-runtime-boundary/v1"

DEFAULT_FORBIDDEN_IMPORT_ROOTS = ("unreal",)


@dataclass(frozen=True)
class BoundaryIssue:
    code: str
    message: str
    path: str
    line: int = 0
    severity: str = "error"

    def as_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "line": self.line,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class BoundaryReport:
    ok: bool
    checked_files: int
    issues: tuple

    @property
    def issue_count(self):
        return len(self.issues)

    def as_dict(self):
        return {
            "schema_version": BOUNDARY_SCHEMA_VERSION,
            "ok": self.ok,
            "checked_files": self.checked_files,
            "issue_count": self.issue_count,
            "issues": [issue.as_dict() for issue in self.issues],
        }


def check_runtime_boundary(
    runtime_root=None,
    forbidden_text_markers=(),
    extra_forbidden_import_roots=(),
):
    root = Path(runtime_root or Path(__file__).resolve().parent)
    import_roots = tuple(
        dict.fromkeys((*DEFAULT_FORBIDDEN_IMPORT_ROOTS, *tuple(extra_forbidden_import_roots)))
    )
    text_markers = tuple(forbidden_text_markers)
    issues = []
    files = sorted(path for path in root.glob("*.py") if path.is_file())
    for path in files:
        rel_path = path.name
        text = path.read_text(encoding="utf-8")
        issues.extend(_text_marker_issues(text, rel_path, text_markers))
        issues.extend(_import_issues(text, rel_path, import_roots))
    issue_tuple = tuple(issues)
    return BoundaryReport(ok=not issue_tuple, checked_files=len(files), issues=issue_tuple)


def _text_marker_issues(text, rel_path, text_markers):
    issues = []
    for marker in text_markers:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if marker in line:
                issues.append(BoundaryIssue(
                    code="forbidden_project_marker",
                    message="%s contains project-specific marker %r" % (rel_path, marker),
                    path=rel_path,
                    line=line_number,
                ))
    return issues


def _import_issues(text, rel_path, import_roots):
    issues = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [
            BoundaryIssue(
                code="syntax_error",
                message="%s failed to parse: %s" % (rel_path, exc),
                path=rel_path,
                line=exc.lineno or 0,
            )
        ]

    for node in ast.walk(tree):
        root_name = None
        line_number = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", 1)[0]
                if root_name in import_roots:
                    issues.append(_import_issue(rel_path, root_name, line_number))
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_name = node.module.split(".", 1)[0]
            if root_name in import_roots:
                issues.append(_import_issue(rel_path, root_name, line_number))
    return issues


def _import_issue(rel_path, root_name, line_number):
    return BoundaryIssue(
        code="forbidden_runtime_import",
        message="%s imports forbidden project/runtime dependency %r" % (rel_path, root_name),
        path=rel_path,
        line=line_number,
    )
