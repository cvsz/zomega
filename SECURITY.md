# Security Policy

Security is part of zomega's delivery baseline. The service handles tenant data,
authorization credentials, paid credits, third-party API keys, and execution results;
security-sensitive behavior must fail closed and remain auditable.

## Reporting a vulnerability

Do not disclose exploitable vulnerabilities in public issues, pull requests,
discussions, or commit messages. Use GitHub's private vulnerability reporting or
security advisory capability for cvsz/zomega
(https://github.com/cvsz/zomega/security) when enabled. Include affected versions or
commits, reproduction details, impact, prerequisites, and suggested remediation.

## Supported versions

The latest release line is the primary supported version. Older release lines may
receive security fixes only when explicitly maintained by the project.

## Security expectations

- Never commit credentials, tokens, private keys, production secrets, or sensitive personal data.
- Keep dependencies patched and review Dependabot alerts.
- Keep CodeQL and dependency-review workflows enabled and passing.
- Use least-privilege GitHub Actions permissions.
- Enforce authentication, authorization, tenant isolation, and input validation at trust boundaries.
- Verify Stripe signatures and treat payment state as authoritative only after verification.
- Preserve paid-before-use credit reservation and settlement invariants.
- Prefer fail-closed behavior for security-sensitive paths.
- Review third-party actions and constrain them according to project policy.
- Do not disable security gates merely to obtain a passing build.

## GitHub Actions trust-boundary regression checks

scripts/check_workflow_security.py parses workflow YAML structurally and checks for
explicit pull-request permissions, unsafe top-level or job-level write grants,
credential persistence on every checkout step, secret use in pull_request workflows,
and duplicate or malformed YAML keys.

The PR-triggered workflow that runs this scanner executes code from the candidate
revision. It is therefore a regression check only, not a trusted admission control:
a candidate can modify its own scanner or workflow. Required-check configuration,
review policy, and any trusted policy enforcement must be administered and verified
outside the candidate-controlled workflow. Never place reviewer PATs, signing
credentials, or other privileged secrets in workflows that execute PR-controlled code.

## Incident handling

Maintainers should contain affected access or artifacts, assess tenant and financial
impact, remediate the root cause, validate the fix, document disclosure decisions,
and use the documented rollback path when a release is unsafe.
