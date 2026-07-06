"""Template lint for agent-stack-shared.

Mechanizes the checkable subset of the Template Authoring Rules (README):
1. OPTIONAL block markers are balanced and non-crossing per file.
2. Placeholder <-> MANIFEST-SCHEMA.md consistency, both directions:
   every {{KEY}} / {{SLOT:KEY}} / OPTIONAL:KEY used in a template is documented
   in the schema, and every ALL-CAPS key documented in the schema is used by
   some template (whitelist below for intentional exceptions).
3. Render smoke: every manifest under examples/ renders fully into a temp
   directory with zero leftover placeholders (stack_render hard-errors on those).

No third-party dependencies. Exit 0 with a TEMPLATE_LINT_OK token, exit 1 with
per-violation lines otherwise.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIRS = [ROOT / "rules", ROOT / "skills", ROOT / "commands"]
SCHEMA = ROOT / "MANIFEST-SCHEMA.md"
EXAMPLES = ROOT / "examples"
RENDERER = ROOT / "scripts" / "stack_render.py"

PARAM_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
SLOT_RE = re.compile(r"\{\{SLOT:([A-Z][A-Z0-9_]*)\}\}")
OPT_BEGIN_RE = re.compile(r"<!--\s*BEGIN OPTIONAL:([A-Z][A-Z0-9_]*)\s*-->")
OPT_END_RE = re.compile(r"<!--\s*END OPTIONAL:([A-Z][A-Z0-9_]*)\s*-->")
SCHEMA_KEY_RE = re.compile(r"`([A-Z][A-Z0-9_]*)`")

# Documented in the schema but legitimately absent from template text.
SCHEMA_ONLY_WHITELIST = {
    "KEY",  # syntax illustrations in the schema's own prose
}
# Used by templates but resolved outside the params/slots/optional tables
# (none today; add here with a reason if one appears).
TEMPLATE_ONLY_WHITELIST: set[str] = set()


def iter_template_files() -> list[Path]:
    files: list[Path] = []
    for d in TEMPLATE_DIRS:
        if d.is_dir():
            files.extend(sorted(d.rglob("*.md")))
    return files


def check_optional_balance(path: Path, text: str, errors: list[str]) -> None:
    stack: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        b = OPT_BEGIN_RE.search(line)
        e = OPT_END_RE.search(line)
        if b:
            stack.append(b.group(1))
        if e:
            if not stack:
                errors.append(f"{path.relative_to(ROOT)}:{i}: END OPTIONAL:{e.group(1)} without BEGIN")
            elif stack[-1] != e.group(1):
                errors.append(
                    f"{path.relative_to(ROOT)}:{i}: crossing OPTIONAL blocks "
                    f"(END {e.group(1)} while inside {stack[-1]})"
                )
                stack.pop()
            else:
                stack.pop()
    for leftover in stack:
        errors.append(f"{path.relative_to(ROOT)}: BEGIN OPTIONAL:{leftover} never closed")


def collect_template_keys(files: list[Path], errors: list[str]) -> set[str]:
    keys: set[str] = set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        check_optional_balance(path, text, errors)
        keys.update(SLOT_RE.findall(text))
        keys.update(OPT_BEGIN_RE.findall(text))
        # Params: everything {{KEY}} that is not a SLOT: form.
        for m in PARAM_RE.findall(text):
            keys.add(m)
    return keys


def collect_schema_keys() -> set[str]:
    """Keys are what the schema *documents*: backticked ALL-CAPS tokens in the
    FIRST column of a table row. Mentions in description columns (e.g. history
    notes about removed keys) do not count."""
    keys: set[str] = set()
    for line in SCHEMA.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        first_col = line[1:].split("|", 1)[0]
        keys.update(SCHEMA_KEY_RE.findall(first_col))
    return keys


def render_smoke(errors: list[str]) -> int:
    count = 0
    if not EXAMPLES.is_dir():
        errors.append("examples/ directory missing (render smoke has nothing to run)")
        return 0
    for manifest in sorted(EXAMPLES.glob("*.json")):
        count += 1
        with tempfile.TemporaryDirectory(prefix="stack-lint-") as tmp:
            result = subprocess.run(
                [sys.executable, str(RENDERER), "--project", tmp, "--manifest", str(manifest)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append(
                    f"render smoke failed for {manifest.name}:\n{result.stdout}\n{result.stderr}"
                )
    return count


def main() -> int:
    errors: list[str] = []
    files = iter_template_files()
    template_keys = collect_template_keys(files, errors)
    schema_keys = collect_schema_keys()

    for key in sorted(template_keys - schema_keys - TEMPLATE_ONLY_WHITELIST):
        errors.append(f"placeholder {key} used in templates but not documented in MANIFEST-SCHEMA.md")
    for key in sorted(schema_keys - template_keys - SCHEMA_ONLY_WHITELIST):
        errors.append(f"schema documents {key} but no template uses it")

    examples = render_smoke(errors)

    if errors:
        for e in errors:
            print(f"LINT: {e}")
        print(f"TEMPLATE_LINT_FAIL violations={len(errors)}")
        return 1

    print(f"TEMPLATE_LINT_OK templates={len(files)} keys={len(template_keys)} examples={examples}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
