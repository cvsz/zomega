#!/usr/bin/env python3
"""Fail-closed regression checks for GitHub Actions trust boundaries."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

ALLOWED_SECURITY_EVENT_WORKFLOWS = {
    ".github/workflows/codeql.yml",
    ".github/workflows/security.yml",
}
SAFE_PERMISSION_VALUES = {"read", "none"}
UNTRUSTED_REF_PATTERNS = (
    r"refs/pull/",
    r"github\.event\.pull_request",
    r"github\.event\.inputs\.sha",
    r"inputs\.sha",
)


class UniqueKeyLoader(yaml.BaseLoader):
    """BaseLoader that preserves GitHub's 'on' key and rejects duplicate keys."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "unhashable mapping key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _event_names(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    if isinstance(value, dict):
        return {key for key in value if isinstance(key, str)}
    return set()


def _permission_findings(
    value: Any,
    *,
    relative: str,
    location: str,
) -> list[str]:
    findings: list[str] = []
    if value == "read-all":
        return findings
    if value == "write-all":
        return [f"{relative}: {location} grants write-all"]
    if not isinstance(value, dict):
        return [f"{relative}: {location} must be an explicit permission map or read-all"]

    for scope, level in value.items():
        if not isinstance(scope, str) or not isinstance(level, str):
            findings.append(f"{relative}: {location} contains a non-string permission")
            continue
        normalized = level.lower()
        if normalized in SAFE_PERMISSION_VALUES:
            continue
        if normalized == "write" and (
            scope == "security-events" and relative in ALLOWED_SECURITY_EVENT_WORKFLOWS
        ):
            continue
        if normalized == "write":
            findings.append(f"{relative}: {location} grants {scope}: write")
        else:
            findings.append(
                f"{relative}: {location} has unsupported permission level for {scope}: {level}"
            )
    return findings


def _checkout_findings(
    document: dict[str, Any],
    *,
    relative: str,
    has_pull_request: bool,
) -> list[str]:
    if not has_pull_request:
        return []

    findings: list[str] = []
    jobs = document.get("jobs", {})
    if not isinstance(jobs, dict):
        return [f"{relative}: jobs must be a mapping"]

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            findings.append(f"{relative}: job {job_name!r} must be a mapping")
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            findings.append(f"{relative}: steps for job {job_name!r} must be a list")
            continue
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if not isinstance(uses, str) or not uses.lower().startswith("actions/checkout@"):
                continue
            options = step.get("with", {})
            persisted = options.get("persist-credentials") if isinstance(options, dict) else None
            if not isinstance(persisted, str) or persisted.lower() != "false":
                findings.append(
                    f"{relative}: checkout in job {job_name!r} step {index + 1} "
                    "must set with.persist-credentials: false"
                )
    return findings


def scan_workflows(root: Path) -> list[str]:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return [f"missing workflow directory: {workflow_dir}"]

    files = sorted(
        path
        for path in workflow_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )
    if not files:
        return [f"no workflow files found under: {workflow_dir}"]

    findings: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        try:
            document = yaml.load(source, Loader=UniqueKeyLoader)
        except yaml.YAMLError as exc:
            findings.append(f"{relative}: invalid or ambiguous YAML: {exc.__class__.__name__}")
            continue

        if not isinstance(document, dict):
            findings.append(f"{relative}: workflow document must be a mapping")
            continue

        events = _event_names(document.get("on"))
        has_pull_request = "pull_request" in events
        if "pull_request_target" in events:
            findings.append(f"{relative}: pull_request_target is forbidden")

        if has_pull_request:
            if "permissions" not in document:
                findings.append(
                    f"{relative}: pull_request workflow requires explicit top-level permissions"
                )
            else:
                findings.extend(
                    _permission_findings(
                        document["permissions"],
                        relative=relative,
                        location="top-level permissions",
                    )
                )

            has_secrets = bool(
                re.search(r"\bsecrets(?:\s*\.|\s*\[|\s*:)", source)
            )
            if has_secrets:
                findings.append(f"{relative}: pull_request workflow must not reference secrets")

            jobs = document.get("jobs", {})
            if isinstance(jobs, dict):
                for job_name, job in jobs.items():
                    if isinstance(job, dict) and "permissions" in job:
                        findings.extend(
                            _permission_findings(
                                job["permissions"],
                                relative=relative,
                                location=f"job {job_name!r} permissions",
                            )
                        )

            findings.extend(
                _checkout_findings(
                    document,
                    relative=relative,
                    has_pull_request=has_pull_request,
                )
            )

        has_secrets = bool(re.search(r"\bsecrets(?:\s*\.|\s*\[|\s*:)", source))
        untrusted_ref = any(re.search(pattern, source) for pattern in UNTRUSTED_REF_PATTERNS)
        if has_secrets and untrusted_ref:
            findings.append(
                f"{relative}: secrets combined with PR-controlled/operator-supplied ref"
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    findings = scan_workflows(args.root.resolve())
    if findings:
        for finding in findings:
            print(f"::error::{finding}")
        return 1
    print("Workflow trust-boundary regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
