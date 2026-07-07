"""Editor-only probe/audit base helpers shared across UE projects.

Layering contract (see README §pylib layering):

- This package is **editor-only**: ``ue_probe.base`` imports ``unreal`` at
  module level and is meant to run inside the UE Editor Python environment
  (Remote Execution / -f scripts). Do not import it from UE-light code.
- This ``__init__`` deliberately imports nothing, so that unittest discovery
  and non-editor tooling can traverse the package without pulling ``unreal``.
  Import the implementation explicitly: ``from ue_probe import base``.
- Boundary: no project names, project paths, or game-content asset paths may
  appear in this package (enforced by ``tests/test_ue_probe.py`` BoundaryTests). Project bindings (fail-token prefixes, Saved/
  subdirectory names, project subsystem wrappers) live in each project's own
  ``*_ops/probe_common.py`` thin layer.
"""
