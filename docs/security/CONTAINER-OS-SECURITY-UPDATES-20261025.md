# Container OS Security Updates — 2026-10-25

## Finding

The 2026-09-17 hosted Trivy image scan of the `python:3.12-slim`-based zomega image reported 13 HIGH/CRITICAL OS package findings, including Debian packages with fixed revisions available from the configured repositories.

## Change

The image build now runs `apt-get update` and `apt-get upgrade -y --no-install-recommends` before installing application dependencies and switching to the unprivileged `zomega` user. A contract test prevents removal or reordering of this update step.

Trivy remains blocking for HIGH/CRITICAL findings. This change does not add an ignore rule, suppress a CVE, or weaken scanner settings.

## Verification required

- Build the image from the exact PR head with `docker build --pull`.
- Confirm the Trivy container scan reports no remaining fixable HIGH/CRITICAL OS findings.
- Run the complete unit, integration, and application-security workflows on the exact head.
- Compare the final image digest and SBOM before release admission.

## Rollback

Do not restore the vulnerable image as a production release. If the package-upgrade layer causes a build/runtime regression, fix the base-image package set or pin a verified patched base-image digest, then rebuild and rescan. Keep the security gate blocking.

No production deployment, migration, payment, trade, or DNS change is part of this patch.
