# zomega Skill 005: architecture-generator

## Owner
`zomega-architect`

## Objective
Execute `architecture-generator` as a production engineering operation with traceable evidence.

## Procedure
1. Validate the supplied objective, scope, environment, and constraints.
2. Inspect current-state evidence relevant to `architecture-generator` before proposing change.
3. Identify dependencies, trust boundaries, failure modes, and rollback requirements.
4. Produce the smallest complete implementation or decision required by this capability.
5. Validate the result with deterministic checks appropriate to the capability.
6. Record changed artifacts, commands/results, risks, and unresolved external blockers.
7. Return `PASS` only when required validation evidence is present; otherwise return `FAIL` or `BLOCKED`.

## Security Contract
Never reveal secret values, weaken authentication/TLS, bypass authorization, or perform destructive
operations without explicit authorization plus backup and rollback evidence.

## Result Contract
Return structured fields:
`status`, `findings`, `changes`, `validation`, `evidence`, `blockers`, `next_action`.
