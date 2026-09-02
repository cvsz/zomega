# Contributing to OMEGA

Thank you for helping improve OMEGA. Keep changes focused, reviewable, secure, and
compatible with the paid-before-use and multi-tenant service boundaries.

## Development workflow

1. Fork the repository or create a feature branch from `main`.
2. Review the relevant architecture, security, and operational documentation.
3. Add or update tests for behavior changes.
4. Run `make test` and `python3 -m compileall -q omega tests`.
5. Run `./verify.sh` when PostgreSQL, Redis, and the required environment are available.
6. Update documentation and `CHANGELOG.md` when relevant.
7. Open a pull request and complete the repository checklist.

## Branch and commit guidance

Use concise branch prefixes such as `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`,
`test/`, or `security/`. Prefer Conventional Commits, for example:

- `feat: add skill execution control`
- `fix: prevent duplicate credit settlement`
- `security: harden webhook validation`
- `docs: update deployment guide`

## Pull requests

Explain the problem, implementation, validation, security impact, compatibility
impact, migration requirements, and rollback plan where applicable. Do not bypass
quality, authorization, billing, or security checks to obtain a passing build.

## Security

Do not report exploitable vulnerabilities in public issues, pull requests, or
discussions. Follow [`SECURITY.md`](SECURITY.md).
