# Human Validation Handoff

When stopping for user L4/H validation, include a player-facing handoff. Do not give only tokens, script names, empty fields, or "please validate."

Must include: `Validation goal`, `Entry point`, `Player steps`, `Observation points`, `Pass criteria`, `Failure/tuning route`, `Out of scope this round`, and `Response format`.

## Instantiate the goal; never ship bare words

`Validation goal` must be instantiated from the project's active validation lock / gate definition — the specific open question this gate answers, plus the concrete changes in this build. Bare quality words (`fun`, `playability`, `娱乐性`, `可玩性`, `好玩`, `feel good`) are not a validation goal; they name the whole game, not what this round can decide. Turn the gate's open question into a falsifiable, observable statement and point the observation points at this build's actual changes.

`Out of scope this round` must list what is deliberately NOT being judged (frozen systems, thin content not yet wired, provisional numbers). This exists so a reviewer's "I can't tell" does not collapse into a Fail: name the verdict vocabulary and keep "can't tell because X is out of scope" distinct from "the mechanic was exercised and has no teeth."

If entry or steps are unknown, say the handoff is not ready and name the missing prerequisite. Do not claim feel/readability/fun/UI clarity from probes alone.

Details: [human-validation-handoff.md]({{KB_ROOT}}/modules/human-validation-handoff.md).
