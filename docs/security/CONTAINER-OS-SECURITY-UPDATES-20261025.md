# Container OS Security Updates — 2026-10-26

## Finding

The 2026-09-17 hosted Trivy image scan of the `python:3.12-slim`-based zomega image reported 13 HIGH/CRITICAL OS package findings, including Debian packages with fixed revisions available from the configured repositories.

## Immutable base-image reference

The candidate pins the Docker Official Image multi-platform index to:

`python:3.12.15-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704`

The digest was checked against the official Docker Hub image metadata on 2026-10-26:
https://hub.docker.com/layers/library/python/3.12-slim

The regression contract fails if the Dockerfile changes back to a mutable tag or changes the reviewed digest without updating the contract in a reviewed change.

## Controlled OS package refresh and evidence

The image build runs `apt-get update` and `apt-get upgrade -y --no-install-recommends` before installing application dependencies and switching to the unprivileged `zomega` user. It captures the resolved Debian package names and versions in `/usr/share/zomega/os-packages.tsv`.

Because APT resolves packages from the configured repositories at build time, pinning the base image alone does not make the complete image byte-for-byte reproducible. The security workflow therefore:

- builds one local image for the exact workflow-tested ref;
- records the tested ref commit (`GITHUB_SHA`) and, for pull requests, the PR head SHA separately;
- records the local image-config digest and pinned base reference;
- extracts and hashes the resolved OS package manifest;
- runs the blocking HIGH/CRITICAL Trivy scan against that same local image;
- generates an SPDX JSON SBOM from that same local image; and
- uploads the image SBOM and OS package evidence as workflow artifacts (30-day retention for the OS manifest evidence).

For pull requests, GitHub's default `GITHUB_SHA` identifies the synthetic merge ref used by the workflow. The evidence artifact records both that tested ref and the PR head so reviewers can reconcile the result to the exact candidate head.

The local image-config digest is not a registry manifest digest. No registry publication or production deployment is performed by this candidate. The release workflow must record the pushed OCI manifest digest and verify its signature/provenance and SBOM association before deployment.

Trivy remains blocking for HIGH/CRITICAL findings. No CVE ignore, scanner bypass, or severity downgrade is introduced.

## Verification required

- Run the complete unit, integration, dependency audit, SAST, and security workflows on the final exact PR head.
- Confirm the Trivy container scan passes for the image built from that head.
- Verify the uploaded SBOM describes the scanned image and the package manifest is non-empty and hash-verifiable.
- Reconcile `pr_head_commit` and `tested_ref_commit` from the evidence artifact with the current PR metadata.
- Before release, link the registry image digest, SBOM, and signed provenance to the same approved source commit.
- Verify deployment smoke tests, rollback acceptance, and operator approval independently.

## Rollback

Do not restore a known-vulnerable image as a production release. If the package-upgrade layer causes a build/runtime regression, use a reviewed, digest-pinned base-image update, rebuild and rescan, and retain the resulting manifest/SBOM evidence. Keep the security gate blocking.

No production deployment, migration, payment, trade, or DNS change is part of this patch.
