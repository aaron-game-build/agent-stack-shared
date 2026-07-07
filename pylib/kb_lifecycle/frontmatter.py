"""Self-contained YAML-lite frontmatter parser for knowledge-base markdown.

No third-party dependencies (no PyYAML). Understands exactly the subset of
YAML that KB entries actually use, observed across consuming projects:

- The file starts with a ``---`` line, and frontmatter runs to the next
  ``---`` line.
- ``key: scalar`` pairs (scalar is used verbatim, quotes are stripped).
- ``key:`` followed by one or more ``  - item`` lines becomes a list value.
- Blank lines and ``#`` comment lines are ignored.

Anything else (nested mappings, flow sequences, multi-document files, missing
closing ``---``) is treated as unsupported and parsing returns ``None`` so
callers can record a parse-failure issue instead of guessing.
"""

from __future__ import annotations

FRONTMATTER_DELIMITER = "---"


def parse_frontmatter(text):
    """Parse leading YAML-lite frontmatter from ``text``.

    Returns a ``dict`` of parsed keys on success, or ``None`` if the file has
    no frontmatter block or the block could not be parsed.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        return None

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONTMATTER_DELIMITER:
            end_index = index
            break
    if end_index is None:
        return None

    body_lines = lines[1:end_index]
    return _parse_body(body_lines)


def _parse_body(body_lines):
    data = {}
    current_key = None
    current_list = None

    for raw_line in body_lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            if current_key is None or current_list is None:
                return None
            current_list.append(_strip_scalar(stripped[2:].strip()))
            continue

        if ":" not in line:
            return None

        if line[:1].isspace():
            # Indented "key: value" without a leading "- " is not part of
            # the supported subset.
            return None

        key, _, value = line.partition(":")
        key = key.strip()
        if not key:
            return None

        value = value.strip()
        if value == "":
            # Start of a list value (or an empty scalar with no list).
            current_key = key
            current_list = []
            data[key] = current_list
        else:
            current_key = None
            current_list = None
            data[key] = _strip_scalar(value)

    return data


def _strip_scalar(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value
