---
name: frontend-design
description: Canonical frontend-design workflow for distinctive, production-grade frontend interfaces in this repo.
---

# Frontend Design

Use when implementing frontend pages, components, browser tools, dashboards, or prototypes.

Workflow:

1. Identify product purpose, audience, stack, constraints, and whether an existing design system applies.
2. Choose a clear aesthetic direction before coding.
3. Implement real responsive code; do not deliver mock prose when the user asked for a build.
4. Use expressive type, committed color, intentional motion, and non-flat backgrounds when appropriate.
5. Preserve the host project's existing UI conventions for existing project surfaces.

Avoid:

- Generic AI layouts, purple-on-white defaults, and predictable component grids.
- Default font stacks unless required by an existing system.
- Decorative motion that hurts accessibility or responsiveness.

Delivery checklist:

- Desktop and mobile layout works.
- Interactive elements have hover/focus affordances.
- Text contrast and reduced-motion behavior is considered.
- Existing project patterns are preserved when applicable.