"""Template lint for agent-stack-shared.

Mechanizes the checkable subset of the Template Authoring Rules (README):
1. OPTIONAL block markers are balanced and non-crossing per file.
2. Placeholder <-> MANIFEST-SCHEMA.md consistency, both directions:
   every {{KEY}} / {{SLOT:KEY}} / OPTIONAL:KEY used in a template is documented
   in the schema, and every ALL-CAPS key documented in the schema is used by
   some template (whitelist below for intentional exceptions).
3. Render smoke: every manifest under examples/ is rendered fully IN MEMORY
   (rules + skills + commands + sdd/tdd/pylib + adapter wrappers if the
   manifest configures them) with an explicit zero-leftover-placeholder
   assertion. Nothing is written to disk.

No third-party dependencies. Exit 0 with a TEMPLATE_LINT_OK token, exit 1 with
per-violation lines otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIRS = [ROOT / "rules", ROOT / "skills", ROOT / "commands"]
SCHEMA = ROOT / "MANIFEST-SCHEMA.md"
EXAMPLES = ROOT / "examples"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stack_render  # noqa: E402

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
    """BEGIN/END must pair up with no nesting and no crossing. Nesting is
    rejected outright (not just crossing): the renderer's non-greedy
    `BEGIN:K ... END:K` regex does not understand block structure, so a
    nested block either loses its content silently (outer key omitted) or
    leaves stray markers (outer key kept)."""
    rel = path.relative_to(ROOT)
    open_key: str | None = None
    open_line = 0
    for i, line in enumerate(text.splitlines(), 1):
        b = OPT_BEGIN_RE.search(line)
        e = OPT_END_RE.search(line)
        if b:
            if open_key is not None:
                errors.append(
                    f"{rel}:{i}: BEGIN OPTIONAL:{b.group(1)} while OPTIONAL:{open_key} "
                    f"(line {open_line}) is still open — blocks must not nest or cross"
                )
            open_key = b.group(1)
            open_line = i
        if e:
            if open_key is None:
                errors.append(f"{rel}:{i}: END OPTIONAL:{e.group(1)} without BEGIN")
            elif open_key != e.group(1):
                errors.append(
                    f"{rel}:{i}: crossing OPTIONAL blocks "
                    f"(END {e.group(1)} while inside {open_key})"
                )
                open_key = None
            else:
                open_key = None
    if open_key is not None:
        errors.append(f"{rel}: BEGIN OPTIONAL:{open_key} (line {open_line}) never closed")


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
    """Render every example manifest fully in memory via stack_render's
    compute_* functions — no subprocess, nothing written to disk — and assert
    zero leftover `{{` in every rendered .md."""
    count = 0
    if not EXAMPLES.is_dir():
        errors.append("examples/ directory missing (render smoke has nothing to run)")
        return 0
    fake_project_root = ROOT / "_lint_smoke_project"  # path is never written to
    for manifest_path in sorted(EXAMPLES.glob("*.json")):
        count += 1
        name = manifest_path.name
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: invalid JSON: {exc}")
            continue
        if not manifest.get("shared"):
            errors.append(f"{name}: no 'shared' node")
            continue

        rendered: dict[str, object] = {}
        try:
            targets = stack_render.parse_targets(manifest)
            if "rules" in targets:
                rendered.update(
                    stack_render.compute_rendered_rules(ROOT, fake_project_root, manifest)
                )
            if "skills" in targets:
                rendered.update(
                    stack_render.compute_rendered_skills(ROOT, fake_project_root, manifest)
                )
            if "commands" in targets:
                rendered.update(
                    stack_render.compute_rendered_commands(ROOT, fake_project_root, manifest)
                )
            for target in ("sdd", "tdd", "pylib"):
                if target in targets:
                    rendered.update(stack_render.compute_rendered_extra_target(ROOT, target))
            adapters_cfg = stack_render.get_adapters_config(manifest)
            if adapters_cfg is not None:
                rendered.update(
                    stack_render.compute_adapter_wrappers(fake_project_root, manifest, adapters_cfg)
                )
        except stack_render.StackRenderError as exc:
            errors.append(f"render smoke failed for {name}: {exc}")
            continue

        if not rendered:
            errors.append(f"{name}: rendered zero files — targets misconfigured?")
            continue

        for out_path, content in sorted(rendered.items()):
            if isinstance(content, bytes):
                if not out_path.endswith(".md"):
                    continue  # byte-copied asset (scripts, csv, ...), no placeholders expected
                text = content.decode("utf-8", "replace")
            else:
                text = content
            if "{{" in text:
                errors.append(f"{name}: leftover '{{{{' in rendered {out_path}")
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
