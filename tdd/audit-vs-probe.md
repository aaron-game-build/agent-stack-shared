# Audit vs Probe (L3 vs L4)

## Summary

| | Audit (L3) | Probe (L4) |
|---|---|---|
| Editor state | Loaded; **no PIE** | **PIE Play active** (not Simulate-only) |
| Proves | Assets, CDO wiring, INI, registry rows exist | Runtime behavior, grants, UI submission, facades |
| Does not prove | Button works, GE applies, animation plays | Human clarity, fun, drama |
| Typical location | `Content/Python/audits/` | `Content/Python/probes/` |
| Token | `AUDIT_*_OK` | `PROBE_*_OK` |

## Decision Rule

Ask: **Does this check need the game ticking with a possessed pawn?**

- **No** → audit (load asset, inspect CDO, parse INI, static registry).
- **Yes** → probe (PIE, console, BlueprintCallable facade, HUD VM).

## Common Mistakes

1. **Audit green → claim playable** — configuration exists ≠ runtime works.
2. **Probe with forced immunity → claim natural play** — use ForcedResult evidence type only.
3. **Stale PIE after C++ rebuild** — old session runs old DLL; restart Editor and Play again.
4. **Single probe green → session green** — orchestrators must chain probes; human L4 still required for feel.

## Assertion Selection (Short)

1. Prefer shared L3 checks before duplicating in probes.
2. Prefer project facade / BlueprintCallable over raw subsystem access.
3. Prefer reading ViewModel or saved probe JSON over fragile actor iteration.
4. Montage / animation may need multi-tick sidecar calls — document in probe header.

## Aggregator

Run all L3 audits in one pass so every failure surfaces:

```python
from audit_runner import run_audit_modules
run_audit_modules(modules, content_python_dir, ok_token="RUN_CORE_AUDITS_OK")
```

See `pylib/sdd_tdd/audit_runner.py`.
