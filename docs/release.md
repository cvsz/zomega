# OMEGA Release

## Versioning

Use an explicit versioning policy for the service and keep user-visible changes in
`CHANGELOG.md`. Confirm compatibility and migration requirements before tagging.

## Release checklist

1. Review the diff, security impact, and rollback plan.
2. Run `make test`, Python compilation, and repository contract checks.
3. Run `./verify.sh` against the intended environment when its dependencies are available.
4. Confirm PostgreSQL migrations, Redis compatibility, Stripe behavior, and OpenAI configuration.
5. Confirm required GitHub checks, reviews, environment approvals, and signed release artifacts.
6. Update `CHANGELOG.md` and create the release tag according to project policy.
7. Verify the deployed version, health, tenant isolation, billing invariants, and operational telemetry.

The current deployment and release workflows are explicit-dispatch gates; artifact
publishing and production target wiring must be configured and reviewed before use.

## Rollback

Restore the last known-good application image and configuration, assess whether any
migration requires a forward fix, stop or reconcile affected queued work, and verify
credit and payment state before reopening traffic. Document operational impact and
recovery evidence.
