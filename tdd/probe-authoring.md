# Probe Authoring Standards (R1–R5)

All probes under `Content/Python/probes/` must satisfy these rules. **No grandfather
allowlist** — new projects start clean.

## R1 — Naming

- File stem must start with `probe_` or `run_`.
- Do not add new `_*.py`, `diagnose_*.py`, or `dump_*.py` probes.

## R2 — Stable Token

- Assign or print at least one stable success token: `PREFIX_OK` or `PREFIX_BLOCKED`.
- Pattern: `[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_(?:OK|BLOCKED)`.
- Failures use `{PREFIX}_FAILED` via shared `fail_probe()` helper.

## R3 — Entry Point

- Define `def main():` (no required args for hygiene check).
- Include `if __name__ == "__main__":` guard calling `main()`.

## R4 — Registration (Optional Per Project)

- When the project has a task registry or static gate file list, every probe stem must appear there.
- Pass `registered_stems` to `probe_hygiene.check()`; omit to skip R4.

## R5 — No Hardcoded Targets

- Map paths (`/Game/...`), script class paths (`/Script/...`), and console command literals
  must come from `probe_targets.py` (or project equivalent), not inline strings.
- Exception: probe-specific result JSON filenames may be constants if centralized in `probe_targets`.

## Orchestrator vs Tick Probe

`pitfall:PIEAsyncProbeNotSyncChainable`

| Type | `main()` behavior | Session chaining |
|---|---|---|
| Sync `probe_*.py` | Runs to completion in one call | Safe via `run_probe_module()` |
| Tick `run_*_in_editor.py` | Registers Slate tick; returns immediately | **Not** safe to sync-chain; run separately, then validate JSON |

Session orchestrators should:

1. Run sync preflight probes (remote settings, editor config).
2. Require active PIE before runtime smoke probes.
3. Read `Saved/Automation/.../*.json` from prior tick probes instead of invoking them inline.

Project example: Oathboard `Docs/agent-knowledge/concepts/pie-async-probe-orchestration.md` (in the consuming project, not this repo).

## Orchestrator Budget

- `run_*` session orchestrators should stay ≤300 lines; delegate to `probe_*` modules via
  `run_probe_module()` or shared `pie` helpers.

## Hygiene Check

```bash
python Content/Python/<project>_project/validate_probe_hygiene.py
```

Framework implementation: `agent-stack/pylib/sdd_tdd/probe_hygiene.py`.

## Authoring Checklist

1. Add constants to `probe_targets.py` first.
2. Implement `probe_<feature>.py` with R1–R3.
3. Register stem in static gate / task registry (R4).
4. Run hygiene validator before merge.
