#!/usr/bin/env python3
"""Scan commit-candidate files for high-confidence plaintext credentials.

Diagnostics intentionally contain only location and rule ID. Credential
values are never printed. This is a current-tree guard, not a history scan.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES = (
    (
        "private-key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    (
        "github-token",
        re.compile(
            r"(?<![A-Za-z0-9_])(?:"
            r"gh[pousr]_[A-Za-z0-9_]{20,}|"
            r"github_pat_[A-Za-z0-9_]{20,}"
            r")"
        ),
    ),
    (
        "openai-key",
        re.compile(
            r"(?<![A-Za-z0-9_-])(?:"
            r"sk-(?:proj|svcacct)-[A-Za-z0-9_-]{20,}|"
            r"sk-[A-Za-z0-9]{40,}"
            r")"
        ),
    ),
    ("aws-access-key", re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")),
    ("google-api-key", re.compile(r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{35}")),
    (
        "slack-token",
        re.compile(r"(?<![A-Za-z0-9])xox[baprs]-[0-9A-Za-z-]{20,}"),
    ),
    (
        "credential-assignment",
        re.compile(
            r"(?i)\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|GITHUB_TOKEN|"
            r"NOTION_TOKEN|SLACK_TOKEN|AWS_SECRET_ACCESS_KEY|"
            r"DATABASE_PASSWORD|DB_PASSWORD|CLIENT_SECRET)\b"
            r"\s*(?::|=)\s*[\"']?"
            r"(?!(?:\$\{|<|your[-_]|replace|example|test|dummy|"
            r"redacted|changeme|change-me))"
            r"[^\s\"'#]{12,}"
        ),
    ),
)


def git_candidates(root: Path) -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    entries = [
        root / os.fsdecode(raw)
        for raw in result.stdout.split(b"\0")
        if raw
    ]
    if not entries:
        raise RuntimeError("Git enumerated zero commit-candidate paths")
    return entries


def scan_text(text: str) -> list[tuple[int, int, str]]:
    findings: list[tuple[int, int, str]] = []
    for rule_id, pattern in RULES:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            previous_newline = text.rfind("\n", 0, match.start())
            column = match.start() - previous_newline
            findings.append((line, column, rule_id))
    return findings


def read_candidate(path: Path) -> str | None:
    if path.is_symlink():
        return os.readlink(path)
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if b"\0" in raw:
        return None
    return raw.decode("utf-8", errors="replace")


def self_test() -> int:
    samples = {
        "github-token": "gh" + "p_" + ("A" * 36),
        "openai-key": "sk-" + "proj-" + ("A" * 40),
        "aws-access-key": "AKIA" + ("A" * 16),
        "google-api-key": "AIza" + ("A" * 35),
        "slack-token": "xoxb-" + ("A" * 24),
        "private-key": "-----BEGIN " + "PRIVATE KEY-----",
        "credential-assignment": "CLIENT_SECRET=" + ("A" * 24),
    }
    for expected_rule, sample in samples.items():
        actual = {finding[2] for finding in scan_text(sample)}
        if expected_rule not in actual:
            print(
                f"REPOSITORY_SECRET_SCAN_SELF_TEST_FAILED rule={expected_rule}",
                file=sys.stderr,
            )
            return 1
    placeholders = "OPENAI_API_KEY=${OPENAI_API_KEY}\nCLIENT_SECRET=<replace-me>"
    if scan_text(placeholders):
        print(
            "REPOSITORY_SECRET_SCAN_SELF_TEST_FAILED placeholders",
            file=sys.stderr,
        )
        return 1
    print("REPOSITORY_SECRET_SCAN_SELF_TEST_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    root = args.root.resolve()
    findings: list[tuple[str, int, int, str]] = []
    scanned = 0
    try:
        candidates = git_candidates(root)
        for path in candidates:
            text = read_candidate(path)
            if text is None:
                continue
            scanned += 1
            relative = path.relative_to(root).as_posix()
            findings.extend(
                (relative, line, column, rule_id)
                for line, column, rule_id in scan_text(text)
            )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"REPOSITORY_SECRET_SCAN_ERROR {type(exc).__name__}", file=sys.stderr)
        return 2

    if scanned == 0:
        print("REPOSITORY_SECRET_SCAN_ERROR zero text files scanned", file=sys.stderr)
        return 2
    if findings:
        for relative, line, column, rule_id in findings:
            print(f"{relative}:{line}:{column} [{rule_id}]", file=sys.stderr)
        print(
            f"REPOSITORY_SECRET_SCAN_FAILED findings={len(findings)} "
            "(values redacted)",
            file=sys.stderr,
        )
        return 1
    print(f"REPOSITORY_SECRET_SCAN_OK files={scanned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
