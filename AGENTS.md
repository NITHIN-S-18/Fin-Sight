# AGENTS.md

# FinSight AI Agent Instructions

Before making any changes, read:

- docs/ARCHITECTURE.md
- docs/BUSINESS_RULES.md
- docs/PHASE_HISTORY.md
- docs/VERIFICATION.md
- docs/API_GUIDE.md
- docs/ROADMAP.md

## Development Rules

- Preserve existing architecture.
- Reuse services instead of duplicating logic.
- Never redesign frozen modules.
- Never call internal HTTP APIs.
- Keep business logic inside services.
- Keep endpoints thin.
- Update documentation if APIs or business rules change.

## Required Workflow

1. Inspect existing implementation.
2. Reuse existing services.
3. Implement only the requested feature.
4. Compile (`python -m compileall app`).
5. Verify affected endpoints.
6. Summarize:
   - Files modified
   - Business rules
   - Verification
   - Known limitations
   - Next steps

Stop after completing the requested work. Do not continue to unrelated tasks.
## Communication Rules

Before implementation

- read AGENTS.md
- read every file inside docs
- inspect the existing architecture
- ask clarification questions if requirements are ambiguous

Never assume business rules.

Never redesign existing modules.

Stop after completing only the requested phase.

Never continue to future phases automatically.