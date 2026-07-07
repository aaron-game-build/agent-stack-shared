"""Repo-wide sensitive-marker scan.

Walks the repository tree (rooted two levels above this script:
``agent-stack-shared/``) and flags text files that contain a real,
machine-specific marker (a contributor's local username or an absolute
local drive/profile path) that should never land in a public shared repo.

This is a sensitivity-layer check, not a project-identity check: project
names such as "Oathboard" are expected throughout the repo (docs, example
manifests, retrospectives) and are intentionally NOT forbidden here. Only
markers that leak a real machine/user identity are banned:

- the maintainer's real local username
- the real local projects drive path (forward- and back-slash forms)
- the local user-profile root (forward- and back-slash forms)

Every marker below is built via string concatenation so this script's own
source never contains the literal token (which would otherwise flag
itself on every run).

Exit 0 with ``FORBIDDEN_MARKER_CHECK_OK files=N`` when clean, exit 1 with one
``file:line: marker`` line per hit otherwise.

``--selftest`` builds a temporary fixture file containing a marker and
verifies detection works, independent of the real repo's current state.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

SKIP_DIR_NAMES = {".git", "__pycache__", ".pytest_cache"}

REPO_ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()


def _build_forbidden_markers():
    """Construct sensitive markers via concatenation (self-exempting by design)."""
    username = "jz" + "d94"
    drive_forward = "G" + ":" + "/" + "UEProjects"
    drive_back = "G" + ":" + "\\" + "UEProjects"
    users_forward = "C" + ":" + "/" + "Users"
    users_back = "C" + ":" + "\\" + "Users"
    return (username, drive_forward, drive_back, users_forward, users_back)


FORBIDDEN_MARKERS = _build_forbidden_markers()


def _iter_text_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for filename in filenames:
            path = Path(dirpath) / filename
            yield path


def _read_text_or_none(path):
    try:
        raw = path.read_bytes()
    except (OSError, PermissionError):
        return None
    if b"\x00" in raw:
        return None  # binary file, skip
    return raw.decode("utf-8", errors="replace")


def scan_repo(root, markers=FORBIDDEN_MARKERS):
    """Scan ``root`` for forbidden markers.

    Returns ``(hits, file_count)`` where ``hits`` is a list of
    ``(rel_path, line_number, marker)`` tuples and ``file_count`` is the
    number of text files actually scanned.
    """
    hits = []
    file_count = 0
    root = Path(root).resolve()

    for path in _iter_text_files(root):
        resolved = path.resolve()
        if resolved == SELF_PATH:
            continue
        text = _read_text_or_none(path)
        if text is None:
            continue
        file_count += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            for marker in markers:
                if marker in line:
                    hits.append((str(path.relative_to(root)).replace(os.sep, "/"), line_number, marker))

    return hits, file_count


def run_check(root):
    hits, file_count = scan_repo(root)
    if hits:
        for rel_path, line_number, marker in hits:
            print("%s:%d: %s" % (rel_path, line_number, marker))
        return 1
    print("FORBIDDEN_MARKER_CHECK_OK files=%d" % file_count)
    return 0


def run_selftest():
    markers = _build_forbidden_markers()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        fixture = tmp_root / "fixture.txt"
        fixture.write_text(
            "line one is clean\n"
            "line two mentions %s\n"
            "line three mentions %s\n" % (markers[0], markers[1]),
            encoding="utf-8",
        )
        clean_file = tmp_root / "clean.txt"
        clean_file.write_text("nothing sensitive here\n", encoding="utf-8")

        hits, file_count = scan_repo(tmp_root, markers=markers)

        assert file_count == 2, "expected 2 scanned files, got %d" % file_count
        assert len(hits) == 2, "expected 2 hits, got %d: %r" % (len(hits), hits)
        hit_markers = {marker for _, _, marker in hits}
        assert hit_markers == {markers[0], markers[1]}, "unexpected markers: %r" % hit_markers

    print("FORBIDDEN_MARKER_SELFTEST_OK")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Repo-wide sensitive marker scan")
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root to scan (defaults to the repo containing this script)")
    parser.add_argument("--selftest", action="store_true", help="Run the self-test fixture instead of scanning the repo")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.selftest:
        return run_selftest()
    return run_check(args.root)


if __name__ == "__main__":
    sys.exit(main())
