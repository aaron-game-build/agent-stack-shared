"""Knowledge-base lifecycle checks (UE-light, portable across consuming projects).

Layering contract (mirrors ``ue_probe``/``ue_runtime`` §pylib layering):

- This package never imports ``unreal`` and performs no project-specific
  branching; it audits any markdown knowledge-base tree passed in as a
  ``kb_root`` path.
- This ``__init__`` deliberately imports nothing, so unittest discovery and
  other non-editor tooling can traverse the package cheaply. Import the
  implementation explicitly: ``from kb_lifecycle import checks, frontmatter``.
- Boundary: no project names, project paths, or game-content asset paths may
  appear in this package (enforced by ``tests/test_kb_lifecycle.py``
  BoundaryTests).

Entry point: ``python -m kb_lifecycle --kb-root <path>`` (see ``cli.py``).
"""
