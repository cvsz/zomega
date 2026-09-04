# zomega Development

## Local setup

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill local-only values.
3. Install Python 3.12 and the pinned dependencies with `./install.sh` or `make install`.
4. Start PostgreSQL and Redis, then run `make init` for database migrations.
5. Run `make test` and `python3 -m compileall -q zomega tests` before opening a pull request.

For the containerized path, use `docker compose up --build -d` after configuring `.env`.

## Quality expectations

- Keep changes small and reviewable.
- Add tests for behavior changes and preserve catalog counts.
- Prefer deterministic, reproducible tooling and pinned dependencies.
- Do not commit secrets, local credentials, customer data, or runtime databases.
- Do not weaken authorization, billing, tenant-isolation, or security gates to obtain a passing build.

## Service validation

Run `./verify.sh` only when the required PostgreSQL, Redis, OpenAI, Stripe, and
environment configuration are available. It is a production-style validation gate,
not a replacement for unit and integration tests.

Update the architecture, operations, release, and ADR documentation when behavior or
operational assumptions change.
