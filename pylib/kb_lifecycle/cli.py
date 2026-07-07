"""Command-line interface for kb_lifecycle.

Usage:
    python -m kb_lifecycle --kb-root <path> [--stale-days 180] [--strict]
        [--json] [--today YYYY-MM-DD] [--jaccard 0.5]

Exit code is 1 when any ERROR-severity issue is found, 0 otherwise (WARNING
issues do not affect exit code). ASCII-only output, relative (posix) paths,
"-" separators.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from kb_lifecycle.checks import run_all_checks
from kb_lifecycle.frontmatter import parse_frontmatter

CHECK_ORDER = ("metadata", "stale", "deprecated_ref", "merge_candidate", "orphan")


def build_parser():
    parser = argparse.ArgumentParser(description="Knowledge-base lifecycle checks")
    parser.add_argument("--kb-root", required=True, help="Path to the knowledge-base root directory")
    parser.add_argument("--stale-days", type=int, default=180, help="Days since 'updated' before an active entry is flagged stale")
    parser.add_argument("--strict", action="store_true", help="Treat missing status/updated as errors instead of warnings")
    parser.add_argument("--json", action="store_true", help="Emit a structured JSON report")
    parser.add_argument("--today", help="Reference date (YYYY-MM-DD) for stale checks; defaults to the current date")
    parser.add_argument("--jaccard", type=float, default=0.5, help="Tag-overlap Jaccard threshold for merge_candidate")
    return parser


def _parse_today(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _group_issues(issues):
    groups = {name: [] for name in CHECK_ORDER}
    for issue in issues:
        groups.setdefault(issue.check, []).append(issue)
    return groups


def _print_report(entries, issues):
    groups = _group_issues(issues)
    for check_name in CHECK_ORDER:
        group_issues = groups.get(check_name, [])
        if not group_issues:
            continue
        print("-- %s --" % check_name)
        for issue in group_issues:
            print("%s %s: %s - %s" % (issue.severity.upper(), check_name, issue.path, issue.message))

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")

    if not issues:
        print("KB_LIFECYCLE_OK entries=%d" % len(entries))
    else:
        print(
            "KB_LIFECYCLE_ISSUES entries=%d errors=%d warnings=%d"
            % (len(entries), error_count, warning_count)
        )

    return error_count


def main(argv=None):
    args = build_parser().parse_args(argv)
    kb_root = Path(args.kb_root).resolve()

    if not kb_root.is_dir():
        print("ERROR: --kb-root is not a directory: %s" % kb_root, file=sys.stderr)
        return 1

    today = _parse_today(args.today)

    entries, issues = run_all_checks(
        kb_root,
        parse_frontmatter,
        stale_days=args.stale_days,
        strict=args.strict,
        today=today,
        jaccard_threshold=args.jaccard,
    )

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")

    if args.json:
        report = {
            "kb_root": kb_root.as_posix(),
            "entry_count": len(entries),
            "error_count": error_count,
            "warning_count": warning_count,
            "issues": [issue.as_dict() for issue in issues],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if error_count else 0

    _print_report(entries, issues)
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
