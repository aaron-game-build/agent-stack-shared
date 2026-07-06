# Agent Doc & Encoding Safety

Before editing any UTF-8 Chinese doc or source file, or on ANY mojibake / 乱码 / encoding signal: stop and consult the knowledge base first. This is a recorded pitfall (`pitfall:WindowsEncodingDrift`), not a novel bug — do not re-debug it from scratch.

- On a 乱码 / encoding symptom, targeted-grep `{{KB_ROOT}}` before improvising a fix. CJK→CJK mojibake (e.g. `仇恨实验` → `浠囨仺瀹為獙`) is still valid UTF-8, so a naive "is it valid UTF-8?" check gives a false all-clear.
- Edit Chinese-facing docs/source with `apply_patch`, or `{{UTF8_MARKERS_TOOL}}` for marker blocks. Never use PowerShell `Get-Content | Set-Content`, `-replace | Set-Content`, or any text-rewrite pipeline on UTF-8 Chinese files (`rule:DoNotUsePowerShellSetContentForUtf8ChineseFiles`). `Set-Content -Encoding UTF8` is acceptable only for generated ASCII/log artifacts owned by a script.
- Machine gates read ASCII marker blocks, not Chinese prose (`concept:AsciiMachineMarkers`). A green machine gate does not prove the human-facing Chinese is readable.

Details: [agent-doc-governance.md §Windows UTF-8 / ASCII Marker Guardrail]({{KB_ROOT}}/modules/agent-doc-governance.md).
