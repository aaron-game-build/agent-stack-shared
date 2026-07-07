"""Pure functions that audit a knowledge-base tree for lifecycle hygiene.

An "entry" is any ``*.md`` file (recursively) under ``kb_root`` whose
frontmatter parses and whose ``kb_type`` is ``concept`` or ``module``. Files
without frontmatter, or with a different ``kb_type``, are not entries but may
still act as referrers (top-level index docs) for the ``orphan`` and
``deprecated_ref`` checks.

Every check is a pure function: ``kb_root`` (a ``Path``) plus scalar
parameters in, a list of :class:`Issue` out. Nothing here touches ``unreal``
or performs any network/process I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

VALID_STATUS_VALUES = ("active", "deprecated")

DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class Issue:
    check: str
    severity: str  # "error" | "warning"
    path: str
    message: str

    def as_dict(self):
        return {
            "check": self.check,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class Entry:
    rel_path: str
    frontmatter: dict
    kb_type: str
    status: str | None
    updated: str | None
    tags: tuple
    related: tuple

    @property
    def basename(self):
        return self.rel_path.rsplit("/", 1)[-1]


def _to_posix(path, kb_root):
    return path.relative_to(kb_root).as_posix()


def _collect_markdown_files(kb_root):
    return sorted(
        path for path in kb_root.rglob("*.md") if path.is_file()
    )


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def load_entries(kb_root, frontmatter_parser):
    """Parse every markdown file under ``kb_root``.

    Returns ``(entries, all_docs, parse_issues)`` where:
    - ``entries`` is the list of :class:`Entry` (kb_type concept/module).
    - ``all_docs`` maps rel_path -> parsed frontmatter dict (or ``None``) for
      every ``*.md`` file, including non-entries, used for reference scans.
    - ``parse_issues`` lists files whose leading ``---`` block failed to
      parse (only reported when the file otherwise looks like it intends to
      have frontmatter, i.e. starts with a ``---`` line).
    """
    entries = []
    all_docs = {}
    parse_issues = []

    for path in _collect_markdown_files(kb_root):
        rel_path = _to_posix(path, kb_root)
        text = path.read_text(encoding="utf-8")
        frontmatter = frontmatter_parser(text)
        all_docs[rel_path] = frontmatter

        if frontmatter is None:
            first_line = text.splitlines()[0].strip() if text.splitlines() else ""
            if first_line == "---":
                parse_issues.append(
                    Issue(
                        check="metadata",
                        severity="error",
                        path=rel_path,
                        message="frontmatter block starts but could not be parsed",
                    )
                )
            continue

        kb_type = frontmatter.get("kb_type")
        if kb_type not in ("concept", "module"):
            continue

        status = frontmatter.get("status")
        updated = frontmatter.get("updated")
        tags = tuple(_as_list(frontmatter.get("tags")))
        related = tuple(
            _as_list(frontmatter.get("related_concepts"))
            + _as_list(frontmatter.get("related_modules"))
            + _as_list(frontmatter.get("related"))
        )
        entries.append(
            Entry(
                rel_path=rel_path,
                frontmatter=frontmatter,
                kb_type=kb_type,
                status=status if isinstance(status, str) else None,
                updated=updated if isinstance(updated, str) else None,
                tags=tags,
                related=related,
            )
        )

    return entries, all_docs, parse_issues


def _valid_date(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError:
        return None


def check_metadata(entries, strict=False):
    issues = []
    severity_for_missing = "error" if strict else "warning"

    for entry in entries:
        if entry.status is None:
            issues.append(
                Issue(
                    check="metadata",
                    severity=severity_for_missing,
                    path=entry.rel_path,
                    message="missing status field",
                )
            )
        elif entry.status not in VALID_STATUS_VALUES:
            issues.append(
                Issue(
                    check="metadata",
                    severity="error",
                    path=entry.rel_path,
                    message="invalid status value %r (expected one of %s)"
                    % (entry.status, ", ".join(VALID_STATUS_VALUES)),
                )
            )

        if entry.updated is None:
            issues.append(
                Issue(
                    check="metadata",
                    severity=severity_for_missing,
                    path=entry.rel_path,
                    message="missing updated field",
                )
            )
        elif _valid_date(entry.updated) is None:
            issues.append(
                Issue(
                    check="metadata",
                    severity="error",
                    path=entry.rel_path,
                    message="invalid updated date %r (expected YYYY-MM-DD)" % (entry.updated,),
                )
            )

    return issues


def check_stale(entries, stale_days=180, today=None):
    reference_day = today or date.today()
    issues = []

    for entry in entries:
        if entry.status != "active":
            continue
        parsed = _valid_date(entry.updated)
        if parsed is None:
            continue
        age_days = (reference_day - parsed).days
        if age_days > stale_days:
            issues.append(
                Issue(
                    check="stale",
                    severity="warning",
                    path=entry.rel_path,
                    message="active entry not updated in %d days (retirement candidate, updated=%s)"
                    % (age_days, entry.updated),
                )
            )

    return issues


def _doc_references_target(text, frontmatter, target_rel_path, target_basename):
    # Markdown link syntax "](...basename)" or a bare mention of the
    # filename (index docs often use bare filenames instead of full links).
    if "](%s)" % target_basename in text or "/%s)" % target_basename in text:
        return True
    if target_basename in text:
        return True
    if frontmatter:
        related_values = (
            _as_list(frontmatter.get("related_concepts"))
            + _as_list(frontmatter.get("related_modules"))
            + _as_list(frontmatter.get("related"))
        )
        for value in related_values:
            if target_basename in value or target_rel_path in value:
                return True
    return False


def _build_reference_index(kb_root, all_docs):
    """Map target rel_path -> set of referrer rel_paths, scanning raw text once."""
    texts = {}
    for rel_path in all_docs:
        texts[rel_path] = (kb_root / rel_path).read_text(encoding="utf-8")

    index = {rel_path: set() for rel_path in all_docs}
    for referrer_path, referrer_text in texts.items():
        for target_path in all_docs:
            if target_path == referrer_path:
                continue
            target_basename = target_path.rsplit("/", 1)[-1]
            if _doc_references_target(
                referrer_text,
                all_docs[referrer_path],
                target_path,
                target_basename,
            ):
                index[target_path].add(referrer_path)
    return index


def check_deprecated_ref(kb_root, entries, all_docs, reference_index=None):
    issues = []
    active_paths = {entry.rel_path for entry in entries if entry.status == "active"}
    top_level_docs = {
        rel_path for rel_path in all_docs if "/" not in rel_path
    }

    index = reference_index or _build_reference_index(kb_root, all_docs)

    for entry in entries:
        if entry.status != "deprecated":
            continue
        referrers = index.get(entry.rel_path, set())
        blocking_referrers = sorted(
            referrer
            for referrer in referrers
            if referrer in active_paths or referrer in top_level_docs
        )
        if blocking_referrers:
            issues.append(
                Issue(
                    check="deprecated_ref",
                    severity="warning",
                    path=entry.rel_path,
                    message="deprecated entry still referenced by: %s"
                    % ", ".join(blocking_referrers),
                )
            )

    return issues


def _tag_jaccard(tags_a, tags_b):
    set_a, set_b = set(tags_a), set(tags_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


def check_merge_candidate(entries, jaccard_threshold=0.5):
    issues = []
    seen_pairs = set()

    for i, entry_a in enumerate(entries):
        for entry_b in entries[i + 1 :]:
            pair_key = tuple(sorted((entry_a.rel_path, entry_b.rel_path)))
            if pair_key in seen_pairs:
                continue

            score = _tag_jaccard(entry_a.tags, entry_b.tags)
            same_basename = entry_a.basename == entry_b.basename and (
                entry_a.rel_path.rsplit("/", 1)[0] != entry_b.rel_path.rsplit("/", 1)[0]
            )

            if score >= jaccard_threshold or same_basename:
                seen_pairs.add(pair_key)
                reason_parts = []
                if score >= jaccard_threshold:
                    reason_parts.append("tag overlap %.2f" % score)
                if same_basename:
                    reason_parts.append("same filename in different subdirectories")
                issues.append(
                    Issue(
                        check="merge_candidate",
                        severity="warning",
                        path=pair_key[0],
                        message="possible merge with %s (%s)"
                        % (pair_key[1], "; ".join(reason_parts)),
                    )
                )

    return issues


def check_orphan(kb_root, entries, all_docs, reference_index=None):
    issues = []
    index = reference_index or _build_reference_index(kb_root, all_docs)

    for entry in entries:
        referrers = index.get(entry.rel_path, set())
        if not referrers:
            issues.append(
                Issue(
                    check="orphan",
                    severity="warning",
                    path=entry.rel_path,
                    message="not referenced by any top-level doc, tag-index, or other entry",
                )
            )

    return issues


def run_all_checks(kb_root, frontmatter_parser, stale_days=180, strict=False, today=None, jaccard_threshold=0.5):
    entries, all_docs, parse_issues = load_entries(kb_root, frontmatter_parser)
    reference_index = _build_reference_index(kb_root, all_docs)

    issues = list(parse_issues)
    issues.extend(check_metadata(entries, strict=strict))
    issues.extend(check_stale(entries, stale_days=stale_days, today=today))
    issues.extend(check_deprecated_ref(kb_root, entries, all_docs, reference_index=reference_index))
    issues.extend(check_merge_candidate(entries, jaccard_threshold=jaccard_threshold))
    issues.extend(check_orphan(kb_root, entries, all_docs, reference_index=reference_index))

    return entries, issues
