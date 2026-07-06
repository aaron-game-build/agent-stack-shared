#!/usr/bin/env python3
"""
Shared agent-stack renderer.

Reads a consuming project's agent-stack/manifest.json "shared" node and renders
this shared repo's rules/sdd/tdd/pylib content into that project's agent-stack/
tree. This is the single source of truth for the render pipeline; consuming
projects should invoke this script (via subprocess) rather than reimplementing
the pipeline locally.

Usage:
  python stack_render.py --project <project_root> [--manifest <path>] [--check-only]

Exit codes:
  0  success (or, with --check-only, everything already matches the render)
  1  error (missing manifest/config, missing shared source, render error,
     or --check-only found dirty files)

No third-party dependencies. Python 3.10+.
"""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_REPO_ROOT = SCRIPT_DIR.parent

DEFAULT_TARGETS = ["rules"]
VALID_TARGETS = {"rules", "sdd", "tdd", "pylib"}

PULL_GENERATED_HEADER = (
    "<!-- GENERATED from agent-stack-shared/rules/{name}.md via stack_render.py --pull; "
    "edit the shared repo, not this file -->\n"
)

GENERATED_MD_HEADER = (
    "<!-- GENERATED from agent-stack-shared/{rel} via stack_render.py --pull; "
    "edit the shared repo, not this file -->\n"
)

MDC_GENERATED_COMMENT = (
    "<!-- GENERATED from agent-stack-shared/rules/{name}.md via stack_render.py --pull; "
    "edit the shared repo, not this file -->\n"
)

RULES_SUBDIR = "rules"
SDD_SUBDIR = "sdd"
TDD_SUBDIR = "tdd"
PYLIB_SUBDIR = "pylib"

DEFAULT_RULES_OUT_DIR = "agent-stack/rules"


class StackRenderError(RuntimeError):
    """Raised for any rendering/config problem; caller prints and exits 1."""


# --- generic file IO -------------------------------------------------------


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def load_json(path: Path) -> dict:
    return json.loads(read_text(path))


# --- render pipeline: optional blocks -> slots -> params -> whitespace -----

import re

OPTIONAL_BLOCK_RE = re.compile(
    r"<!-- BEGIN OPTIONAL:([A-Za-z0-9_]+) -->\r?\n?(.*?)<!-- END OPTIONAL:\1 -->\r?\n?",
    re.DOTALL,
)
SLOT_RE = re.compile(r"\{\{SLOT:([A-Za-z0-9_]+)\}\}")
PARAM_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")


def render_optional_blocks(text: str, optional: dict, *, source_name: str) -> str:
    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        inner = match.group(2)
        if key not in optional:
            return ""
        return inner

    return OPTIONAL_BLOCK_RE.sub(_sub, text)


def render_slots(text: str, slots: dict, *, source_name: str) -> str:
    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key not in slots:
            raise StackRenderError(f"{source_name}: missing slot value for {{{{SLOT:{key}}}}}")
        return slots[key]

    return SLOT_RE.sub(_sub, text)


def render_params(text: str, params: dict, optional: dict, *, source_name: str) -> str:
    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key in params:
            return params[key]
        if key in optional:
            return optional[key]
        raise StackRenderError(f"{source_name}: missing param value for {{{{{key}}}}}")

    return PARAM_RE.sub(_sub, text)


def tidy_whitespace(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    tidied: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        tidied.append(line)
    return "\n".join(tidied) + "\n"


def render_shared_text(source_text: str, shared: dict, *, source_name: str) -> str:
    """Render one shared source file's raw text through the standard pipeline:
    optional-block -> slot -> param -> whitespace cleanup.

    Raises StackRenderError if any {{ survives rendering.
    """
    params = shared.get("params", {})
    slots = shared.get("slots", {})
    optional = shared.get("optional", {})

    text = render_optional_blocks(source_text, optional, source_name=source_name)
    text = render_slots(text, slots, source_name=source_name)
    text = render_params(text, params, optional, source_name=source_name)
    text = tidy_whitespace(text)

    if "{{" in text:
        raise StackRenderError(f"{source_name}: leftover {{{{ after rendering")

    return text


# --- rules_out config -------------------------------------------------------


def get_rules_out_config(manifest: dict) -> dict:
    shared = manifest.get("shared") or {}
    rules_out = shared.get("rules_out") or {}
    out_dir = rules_out.get("dir", DEFAULT_RULES_OUT_DIR)
    out_format = rules_out.get("format", "md")
    if out_format not in ("md", "mdc"):
        raise StackRenderError(
            f"manifest shared.rules_out.format must be 'md' or 'mdc', got: {out_format!r}"
        )
    name_map = rules_out.get("name_map", {})
    frontmatter = rules_out.get("frontmatter", {})
    link_map = rules_out.get("link_map", {})
    return {
        "dir": out_dir,
        "format": out_format,
        "name_map": name_map,
        "frontmatter": frontmatter,
        "link_map": link_map,
    }


def apply_link_map(text: str, link_map: dict) -> str:
    for literal_from, literal_to in link_map.items():
        text = text.replace(literal_from, literal_to)
    return text


def build_mdc_frontmatter(name: str, frontmatter_cfg: dict) -> str:
    entry = frontmatter_cfg.get(name)
    if entry is None:
        raise StackRenderError(
            f"rules_out.format=mdc requires rules_out.frontmatter['{name}'] "
            f"(description/alwaysApply/globs) in manifest"
        )
    description = entry.get("description", name)
    always_apply = entry.get("alwaysApply", False)
    globs = entry.get("globs", "")

    lines = ["---", f"description: {description}", f"alwaysApply: {'true' if always_apply else 'false'}"]
    if globs:
        lines.append(f"globs: {globs}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def render_rules(shared_repo: Path, project_root: Path, manifest: dict) -> list[str]:
    """Render every shared rules/*.md into the project's configured rules_out
    location. Returns the list of rule stems (source names, without .md)
    rendered — used for the rules=<n> count.
    """
    shared = manifest.get("shared")
    if not shared:
        raise StackRenderError("manifest has no 'shared' node")

    shared_rules_dir = shared_repo / RULES_SUBDIR
    if not shared_rules_dir.is_dir():
        raise StackRenderError(f"shared stack has no rules/ directory: {shared_rules_dir}")

    source_paths = sorted(shared_rules_dir.glob("*.md"))
    if not source_paths:
        raise StackRenderError(f"shared stack rules/ directory is empty: {shared_rules_dir}")

    rules_out = get_rules_out_config(manifest)
    out_dir = project_root / Path(rules_out["dir"])
    out_format = rules_out["format"]
    name_map = rules_out["name_map"]
    frontmatter_cfg = rules_out["frontmatter"]
    link_map = rules_out["link_map"]

    rendered_names: list[str] = []
    for source_path in source_paths:
        name = source_path.stem
        source_text = read_text(source_path)
        body = render_shared_text(source_text, shared, source_name=f"rules/{name}.md")

        out_name = name_map.get(name, name)

        if out_format == "mdc":
            header_comment = MDC_GENERATED_COMMENT.format(name=name)
            frontmatter = build_mdc_frontmatter(name, frontmatter_cfg)
            content = frontmatter + header_comment + "\n" + body
            out_ext = ".mdc"
        else:
            header_comment = PULL_GENERATED_HEADER.format(name=name)
            content = header_comment + "\n" + body
            out_ext = ".md"

        content = apply_link_map(content, link_map)

        out_path = out_dir / f"{out_name}{out_ext}"
        write_text(out_path, content)
        rendered_names.append(name)

    return rendered_names


# --- sdd/tdd/pylib directory copy ------------------------------------------


def copy_dir_tree(source_dir: Path, dest_dir: Path, *, add_md_header: bool, rel_prefix: str) -> list[str]:
    """Delete dest_dir, then copy source_dir into it verbatim, skipping
    __pycache__. .md files get a GENERATED header line prepended; .py files
    are copied byte-for-byte with no header.

    Returns list of dest-relative paths written (posix style).
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for source_path in sorted(source_dir.rglob("*")):
        if "__pycache__" in source_path.parts:
            continue
        rel = source_path.relative_to(source_dir)
        dest_path = dest_dir / rel
        if source_path.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix == ".md":
            rel_posix = f"{rel_prefix}/{rel.as_posix()}"
            header = GENERATED_MD_HEADER.format(rel=rel_posix)
            body = read_text(source_path)
            write_text(dest_path, header + "\n" + body)
        else:
            # Byte-for-byte copy (e.g. .py) — no header, no re-encoding.
            shutil.copyfile(source_path, dest_path)
        written.append(dest_path.as_posix())

    return written


def render_extra_target(shared_repo: Path, project_root: Path, target: str) -> list[str]:
    if target == "sdd":
        return copy_dir_tree(
            shared_repo / SDD_SUBDIR,
            project_root / "agent-stack" / "sdd",
            add_md_header=True,
            rel_prefix="sdd",
        )
    if target == "tdd":
        return copy_dir_tree(
            shared_repo / TDD_SUBDIR,
            project_root / "agent-stack" / "tdd",
            add_md_header=True,
            rel_prefix="tdd",
        )
    if target == "pylib":
        return copy_dir_tree(
            shared_repo / PYLIB_SUBDIR,
            project_root / "agent-stack" / "pylib",
            add_md_header=True,
            rel_prefix="pylib",
        )
    raise StackRenderError(f"unknown target: {target}")


# --- check-only comparison ---------------------------------------------------


def compute_rendered_rules(shared_repo: Path, project_root: Path, manifest: dict) -> dict[str, str]:
    """Compute the rendered content for every rule without writing to disk.
    Returns {relative_out_path (posix, relative to project_root): content}.
    """
    shared = manifest.get("shared")
    shared_rules_dir = shared_repo / RULES_SUBDIR
    source_paths = sorted(shared_rules_dir.glob("*.md"))

    rules_out = get_rules_out_config(manifest)
    out_dir_rel = Path(rules_out["dir"])
    out_format = rules_out["format"]
    name_map = rules_out["name_map"]
    frontmatter_cfg = rules_out["frontmatter"]
    link_map = rules_out["link_map"]

    result: dict[str, str] = {}
    for source_path in source_paths:
        name = source_path.stem
        source_text = read_text(source_path)
        body = render_shared_text(source_text, shared, source_name=f"rules/{name}.md")

        out_name = name_map.get(name, name)
        if out_format == "mdc":
            header_comment = MDC_GENERATED_COMMENT.format(name=name)
            frontmatter = build_mdc_frontmatter(name, frontmatter_cfg)
            content = frontmatter + header_comment + "\n" + body
            out_ext = ".mdc"
        else:
            header_comment = PULL_GENERATED_HEADER.format(name=name)
            content = header_comment + "\n" + body
            out_ext = ".md"

        content = apply_link_map(content, link_map)
        rel_path = (out_dir_rel / f"{out_name}{out_ext}").as_posix()
        result[rel_path] = content

    return result


def compute_rendered_extra_target(shared_repo: Path, target: str) -> dict[str, str]:
    """Compute rendered content for an sdd/tdd/pylib target without writing.
    Returns {relative_out_path (posix, relative to project_root's agent-stack/): content}.
    """
    if target == "sdd":
        source_dir, rel_prefix, dest_prefix = shared_repo / SDD_SUBDIR, "sdd", "agent-stack/sdd"
    elif target == "tdd":
        source_dir, rel_prefix, dest_prefix = shared_repo / TDD_SUBDIR, "tdd", "agent-stack/tdd"
    elif target == "pylib":
        source_dir, rel_prefix, dest_prefix = shared_repo / PYLIB_SUBDIR, "pylib", "agent-stack/pylib"
    else:
        raise StackRenderError(f"unknown target: {target}")

    result: dict[str, str] = {}
    for source_path in sorted(source_dir.rglob("*")):
        if "__pycache__" in source_path.parts:
            continue
        if source_path.is_dir():
            continue
        rel = source_path.relative_to(source_dir)
        dest_rel = f"{dest_prefix}/{rel.as_posix()}"

        if source_path.suffix == ".md":
            rel_posix = f"{rel_prefix}/{rel.as_posix()}"
            header = GENERATED_MD_HEADER.format(rel=rel_posix)
            body = read_text(source_path)
            result[dest_rel] = header + "\n" + body
        else:
            # Binary-safe: read raw bytes, decode as utf-8 for dict value; the
            # actual on-disk comparison for non-md files is done in bytes by
            # the caller when needed. For .py files we assume utf-8 text.
            result[dest_rel] = source_path.read_bytes().decode("utf-8")

    return result


def check_only(shared_repo: Path, project_root: Path, manifest: dict, targets: list[str]) -> int:
    """Render everything in-memory, compare against what's on disk, print
    clean/dirty lists. Returns 0 if all clean, 1 if anything is dirty.
    """
    clean: list[str] = []
    dirty: list[str] = []

    if "rules" in targets:
        rendered = compute_rendered_rules(shared_repo, project_root, manifest)
        for rel_path, expected in sorted(rendered.items()):
            disk_path = project_root / Path(rel_path)
            if not disk_path.is_file():
                dirty.append(rel_path)
                continue
            actual = read_text(disk_path)
            if actual == expected:
                clean.append(rel_path)
            else:
                dirty.append(rel_path)

    for target in ("sdd", "tdd", "pylib"):
        if target not in targets:
            continue
        rendered = compute_rendered_extra_target(shared_repo, target)
        for rel_path, expected in sorted(rendered.items()):
            disk_path = project_root / Path(rel_path)
            if not disk_path.is_file():
                dirty.append(rel_path)
                continue
            try:
                actual = read_text(disk_path)
            except UnicodeDecodeError:
                actual_bytes = disk_path.read_bytes()
                expected_bytes = expected.encode("utf-8")
                if actual_bytes == expected_bytes:
                    clean.append(rel_path)
                else:
                    dirty.append(rel_path)
                continue
            if actual == expected:
                clean.append(rel_path)
            else:
                dirty.append(rel_path)

    print("=== stack_render --check-only ===")
    print(f"Clean: {len(clean)}")
    for path in clean:
        print(f"  CLEAN {path}")
    print(f"Dirty: {len(dirty)}")
    for path in dirty:
        print(f"  DIRTY {path}")

    if dirty:
        return 1
    return 0


# --- main --------------------------------------------------------------------


def resolve_manifest_path(project_root: Path, manifest_arg: str | None) -> Path:
    if manifest_arg:
        return Path(manifest_arg)
    return project_root / "agent-stack" / "manifest.json"


def parse_targets(manifest: dict) -> list[str]:
    shared = manifest.get("shared") or {}
    targets = shared.get("targets", DEFAULT_TARGETS)
    if not isinstance(targets, list) or not targets:
        raise StackRenderError("manifest shared.targets must be a non-empty list")
    for t in targets:
        if t not in VALID_TARGETS:
            raise StackRenderError(
                f"manifest shared.targets contains invalid target {t!r}; "
                f"valid targets: {sorted(VALID_TARGETS)}"
            )
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shared agent-stack renderer")
    parser.add_argument("--project", required=True, help="Path to the consuming project root")
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to the project's manifest.json (default: <project>/agent-stack/manifest.json)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Render in-memory and diff against disk; do not write. Exit 1 if dirty.",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    manifest_path = resolve_manifest_path(project_root, args.manifest)

    if not manifest_path.is_file():
        print(f"ERR: manifest not found: {manifest_path}")
        return 1

    try:
        manifest = load_json(manifest_path)
    except json.JSONDecodeError as exc:
        print(f"ERR: {manifest_path}: invalid JSON: {exc}")
        return 1

    shared = manifest.get("shared")
    if not shared:
        print(f"ERR: {manifest_path}: no 'shared' node")
        return 1

    try:
        targets = parse_targets(manifest)
    except StackRenderError as exc:
        print(f"ERR: {exc}")
        return 1

    project_name = project_root.name

    if args.check_only:
        try:
            exit_code = check_only(SHARED_REPO_ROOT, project_root, manifest, targets)
        except StackRenderError as exc:
            print(f"ERR: {exc}")
            return 1
        return exit_code

    rules_count = 0
    try:
        if "rules" in targets:
            rendered_names = render_rules(SHARED_REPO_ROOT, project_root, manifest)
            rules_count = len(rendered_names)
            print(f"Rendered {rules_count} rule(s) into project.")

        extra_targets = [t for t in targets if t != "rules"]
        for target in extra_targets:
            written = render_extra_target(SHARED_REPO_ROOT, project_root, target)
            print(f"Copied {len(written)} file(s) for target '{target}'.")
    except StackRenderError as exc:
        print(f"ERR: {exc}")
        return 1
    except OSError as exc:
        print(f"ERR: filesystem error: {exc}")
        return 1

    extra_targets_str = ",".join(t for t in targets if t != "rules")
    print(
        f"STACK_RENDER_OK project={project_name} rules={rules_count} "
        f"extra_targets={extra_targets_str}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
