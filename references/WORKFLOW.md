# ForgePilot workflow reference

## Evidence ledger template

| Claim | Evidence | Confidence | Unknowns |
|---|---|---|---|
| Example: requests enter through a route handler | `src/routes.py`, `create_app()` | High | Runtime config not inspected |

Do not use the example as a claim about a real repository.

## Change plan template

- Goal:
- Acceptance criteria:
- Files to inspect:
- Likely files to change:
- Risks:
- Verification commands:
- Rollback approach (if relevant):

## Verification vocabulary

- **Passed:** command ran and exited successfully; state what it checked.
- **Failed:** command ran and returned a failure.
- **Skipped:** intentionally not run; explain why.
- **Blocked:** could not run due to environment/tool/dependency constraints.
- **Not run:** no execution was attempted.

A successful test suite is evidence, not proof that every behavior is correct.
