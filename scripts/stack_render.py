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
VALID_TARGETS = {"rules", "sdd", "tdd", "pylib", "skills", "commands"}

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
SKILLS_SUBDIR = "skills"
COMMANDS_SUBDIR = "commands"

DEFAULT_RULES_OUT_DIR = "agent-stack/rules"
DEFAULT_SKILLS_OUT_DIR = "agent-stack/skills"
DEFAULT_COMMANDS_OUT_DIR = "agent-stack/commands"


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


def get_skills_out_config(manifest: dict) -> dict:
    shared = manifest.get("shared") or {}
    skills_out = shared.get("skills_out") or {}
    return {"dir": skills_out.get("dir", DEFAULT_SKILLS_OUT_DIR)}


def get_commands_out_config(manifest: dict) -> dict:
    shared = manifest.get("shared") or {}
    commands_out = shared.get("commands_out") or {}
    return {"dir": commands_out.get("dir", DEFAULT_COMMANDS_OUT_DIR)}


FRONTMATTER_RE = re.compile(r"\A(---\r?\n.*?\r?\n---\r?\n?)", re.DOTALL)


def insert_generated_header_md(body: str, rel: str) -> str:
    """Insert the GENERATED header into a rendered .md file's content.

    If the content starts with a `---` frontmatter block, the header goes
    immediately after it; otherwise the header goes at the very first line.
    """
    header = GENERATED_MD_HEADER.format(rel=rel)
    match = FRONTMATTER_RE.match(body)
    if match:
        frontmatter = match.group(1)
        rest = body[match.end():]
        return frontmatter + header + "\n" + rest
    return header + "\n" + body


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
        # link_map applies only to the rendered body — never to the
        # GENERATED header/frontmatter, which may legitimately contain a
        # substring (e.g. "agent-contracts.md") that a link_map key also
        # matches.
        body = apply_link_map(body, link_map)

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


# --- skills/commands rendering ----------------------------------------------
#
# Unlike sdd/tdd/pylib (whole-directory delete-then-copy), skill/command
# sources are template files rendered at file granularity: .md files go
# through the same optional-block -> slot -> param -> whitespace pipeline as
# rules/*.md, and non-.md files (scripts/*.py, data/*.csv, etc.) are copied
# byte-for-byte. Only files that exist in the shared repo are written or
# overwritten — skill/command directories are never deleted wholesale.
#
# This matters at two levels:
#   - a project may keep its own project-only skill dirs or command files
#     alongside the shared ones (e.g. a project-only command like
#     ue-pie-probe.md with no shared counterpart);
#   - a single skill directory that DOES have a shared counterpart may still
#     mix the shared template file (SKILL.md) with project-owned sibling
#     files that have no shared counterpart at all — e.g. ue-py-run's
#     scripts/ue_python.py, ue-py-evolve's scripts/*.py + tagging.md, or
#     ue-task-retrospective's examples.md. Deleting the whole directory
#     before writing would destroy those every time; only touching files
#     that exist under the matching shared/skills/<name>/ path keeps them
#     intact.


def _iter_source_files(source_dir: Path):
    for source_path in sorted(source_dir.rglob("*")):
        if "__pycache__" in source_path.parts:
            continue
        if source_path.is_dir():
            continue
        yield source_path


def render_one_skill_or_command_file(
    source_path: Path, source_dir: Path, *, shared: dict, rel_prefix: str
) -> bytes:
    """Render a single shared source file's content as bytes ready to write.

    .md files: full render pipeline + GENERATED header (after frontmatter, if
    any). Non-.md files: raw bytes, unchanged.
    """
    rel = source_path.relative_to(source_dir)
    if source_path.suffix == ".md":
        rel_posix = f"{rel_prefix}/{rel.as_posix()}"
        source_text = read_text(source_path)
        body = render_shared_text(source_text, shared, source_name=rel_posix)
        content = insert_generated_header_md(body, rel_posix)
        return content.encode("utf-8")
    return source_path.read_bytes()


def render_skills(shared_repo: Path, project_root: Path, manifest: dict) -> list[str]:
    """Render every shared skills/*/ directory into the project's configured
    skills_out location.

    Only files that have a shared-repo counterpart are written/overwritten —
    each skill directory is never deleted wholesale. A skill directory may
    legitimately mix shared template files (SKILL.md) with project-owned
    sibling files that have no shared counterpart at all (e.g. ue-py-run's
    scripts/ue_python.py, ue-py-evolve's scripts/*.py + tagging.md,
    ue-task-retrospective's examples.md) — those must never be touched or
    deleted by this renderer.

    Returns the list of skill names rendered.
    """
    shared = manifest.get("shared")
    if not shared:
        raise StackRenderError("manifest has no 'shared' node")

    shared_skills_dir = shared_repo / SKILLS_SUBDIR
    if not shared_skills_dir.is_dir():
        raise StackRenderError(f"shared stack has no skills/ directory: {shared_skills_dir}")

    skill_dirs = sorted(p for p in shared_skills_dir.iterdir() if p.is_dir())
    if not skill_dirs:
        raise StackRenderError(f"shared stack skills/ directory is empty: {shared_skills_dir}")

    skills_out = get_skills_out_config(manifest)
    out_root = project_root / Path(skills_out["dir"])

    rendered_names: list[str] = []
    for skill_dir in skill_dirs:
        name = skill_dir.name
        dest_dir = out_root / name
        dest_dir.mkdir(parents=True, exist_ok=True)

        for source_path in _iter_source_files(skill_dir):
            rel = source_path.relative_to(skill_dir)
            dest_path = dest_dir / rel
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            content = render_one_skill_or_command_file(
                source_path, skill_dir, shared=shared, rel_prefix=f"skills/{name}"
            )
            with open(dest_path, "wb") as f:
                f.write(content)

        rendered_names.append(name)

    return rendered_names


def render_commands(shared_repo: Path, project_root: Path, manifest: dict) -> list[str]:
    """Render every shared commands/*.md into the project's configured
    commands_out location. Only files with a shared counterpart are
    overwritten; project-only command files are left alone.

    Returns the list of command names rendered.
    """
    shared = manifest.get("shared")
    if not shared:
        raise StackRenderError("manifest has no 'shared' node")

    shared_commands_dir = shared_repo / COMMANDS_SUBDIR
    if not shared_commands_dir.is_dir():
        raise StackRenderError(f"shared stack has no commands/ directory: {shared_commands_dir}")

    source_paths = sorted(shared_commands_dir.glob("*.md"))
    if not source_paths:
        raise StackRenderError(f"shared stack commands/ directory is empty: {shared_commands_dir}")

    commands_out = get_commands_out_config(manifest)
    out_dir = project_root / Path(commands_out["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered_names: list[str] = []
    for source_path in source_paths:
        name = source_path.stem
        content = render_one_skill_or_command_file(
            source_path, shared_commands_dir, shared=shared, rel_prefix="commands"
        )
        dest_path = out_dir / f"{name}.md"
        with open(dest_path, "wb") as f:
            f.write(content)
        rendered_names.append(name)

    return rendered_names


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
        # See render_rules(): link_map applies only to the rendered body.
        body = apply_link_map(body, link_map)

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

        rel_path = (out_dir_rel / f"{out_name}{out_ext}").as_posix()
        result[rel_path] = content

    return result


def compute_rendered_extra_target(shared_repo: Path, target: str) -> dict[str, bytes]:
    """Compute rendered content for an sdd/tdd/pylib target without writing.

    Returns {relative_out_path (posix, relative to project_root's agent-stack/): raw bytes}.
    Bytes (not str) so the comparison in check_only() exactly matches what
    render_extra_target()/copy_dir_tree() actually write to disk — .py files
    are copied byte-for-byte via shutil.copyfile, so no newline translation
    must happen on either side of the comparison.
    """
    if target == "sdd":
        source_dir, rel_prefix, dest_prefix = shared_repo / SDD_SUBDIR, "sdd", "agent-stack/sdd"
    elif target == "tdd":
        source_dir, rel_prefix, dest_prefix = shared_repo / TDD_SUBDIR, "tdd", "agent-stack/tdd"
    elif target == "pylib":
        source_dir, rel_prefix, dest_prefix = shared_repo / PYLIB_SUBDIR, "pylib", "agent-stack/pylib"
    else:
        raise StackRenderError(f"unknown target: {target}")

    result: dict[str, bytes] = {}
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
            result[dest_rel] = (header + "\n" + body).encode("utf-8")
        else:
            # Byte-for-byte copy target (e.g. .py) — compare raw bytes.
            result[dest_rel] = source_path.read_bytes()

    return result


def compute_rendered_skills(shared_repo: Path, project_root: Path, manifest: dict) -> dict[str, bytes]:
    """Compute rendered content for the skills target without writing.

    Returns {relative_out_path (posix, relative to project_root): raw bytes}.
    """
    shared = manifest.get("shared")
    shared_skills_dir = shared_repo / SKILLS_SUBDIR
    skill_dirs = sorted(p for p in shared_skills_dir.iterdir() if p.is_dir())

    skills_out = get_skills_out_config(manifest)
    out_root_rel = Path(skills_out["dir"])

    result: dict[str, bytes] = {}
    for skill_dir in skill_dirs:
        name = skill_dir.name
        for source_path in _iter_source_files(skill_dir):
            rel = source_path.relative_to(skill_dir)
            dest_rel = (out_root_rel / name / rel).as_posix()
            result[dest_rel] = render_one_skill_or_command_file(
                source_path, skill_dir, shared=shared, rel_prefix=f"skills/{name}"
            )

    return result


def compute_rendered_commands(shared_repo: Path, project_root: Path, manifest: dict) -> dict[str, bytes]:
    """Compute rendered content for the commands target without writing.

    Returns {relative_out_path (posix, relative to project_root): raw bytes}.
    """
    shared = manifest.get("shared")
    shared_commands_dir = shared_repo / COMMANDS_SUBDIR
    source_paths = sorted(shared_commands_dir.glob("*.md"))

    commands_out = get_commands_out_config(manifest)
    out_dir_rel = Path(commands_out["dir"])

    result: dict[str, bytes] = {}
    for source_path in source_paths:
        name = source_path.stem
        dest_rel = (out_dir_rel / f"{name}.md").as_posix()
        result[dest_rel] = render_one_skill_or_command_file(
            source_path, shared_commands_dir, shared=shared, rel_prefix="commands"
        )

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
        for rel_path, expected_bytes in sorted(rendered.items()):
            disk_path = project_root / Path(rel_path)
            if not disk_path.is_file():
                dirty.append(rel_path)
                continue
            actual_bytes = disk_path.read_bytes()
            if actual_bytes == expected_bytes:
                clean.append(rel_path)
            else:
                dirty.append(rel_path)

    if "skills" in targets:
        rendered = compute_rendered_skills(shared_repo, project_root, manifest)
        for rel_path, expected_bytes in sorted(rendered.items()):
            disk_path = project_root / Path(rel_path)
            if not disk_path.is_file():
                dirty.append(rel_path)
                continue
            actual_bytes = disk_path.read_bytes()
            if actual_bytes == expected_bytes:
                clean.append(rel_path)
            else:
                dirty.append(rel_path)

    if "commands" in targets:
        rendered = compute_rendered_commands(shared_repo, project_root, manifest)
        for rel_path, expected_bytes in sorted(rendered.items()):
            disk_path = project_root / Path(rel_path)
            if not disk_path.is_file():
                dirty.append(rel_path)
                continue
            actual_bytes = disk_path.read_bytes()
            if actual_bytes == expected_bytes:
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
    extra_target_tokens: list[str] = []
    try:
        if "rules" in targets:
            rendered_names = render_rules(SHARED_REPO_ROOT, project_root, manifest)
            rules_count = len(rendered_names)
            print(f"Rendered {rules_count} rule(s) into project.")

        for target in targets:
            if target == "rules":
                continue
            if target == "skills":
                rendered = render_skills(SHARED_REPO_ROOT, project_root, manifest)
                print(f"Rendered {len(rendered)} skill(s) into project.")
                extra_target_tokens.append(f"skills={len(rendered)}")
            elif target == "commands":
                rendered = render_commands(SHARED_REPO_ROOT, project_root, manifest)
                print(f"Rendered {len(rendered)} command(s) into project.")
                extra_target_tokens.append(f"commands={len(rendered)}")
            else:
                written = render_extra_target(SHARED_REPO_ROOT, project_root, target)
                print(f"Copied {len(written)} file(s) for target '{target}'.")
                extra_target_tokens.append(target)
    except StackRenderError as exc:
        print(f"ERR: {exc}")
        return 1
    except OSError as exc:
        print(f"ERR: filesystem error: {exc}")
        return 1

    extra_targets_str = ",".join(extra_target_tokens)
    print(
        f"STACK_RENDER_OK project={project_name} rules={rules_count} "
        f"extra_targets={extra_targets_str}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
