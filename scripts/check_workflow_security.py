#!/usr/bin/env python3
"""Fail-closed checks for GitHub Actions trust boundaries."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

ALLOWED_SECURITY_EVENT_WORKFLOWS = {"codeql.yml", "security.yml"}

def _event_block(source: str) -> str:
    match = re.search(r"(?ms)^(?:on|['\"]on['\"]):[ \t]*(.*?)(?=^[A-Za-z_][A-Za-z0-9_-]*:[ \t]*|\Z)", source)
    return match.group(1) if match else ""

def _has_event(block: str, event: str) -> bool:
    return bool(re.search(rf"(?m)^\s+{re.escape(event)}\s*:", block) or re.search(rf"(?<![A-Za-z0-9_-]){re.escape(event)}(?![A-Za-z0-9_-])", block))

def _has_unsafe_write_permissions(source: str, *, allow_security_events: bool) -> bool:
    lines = source.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^(?P<indent>[ \t]*)permissions:[ \t]*(?P<inline>.*)$", line)
        if not match:
            continue
        indent = len(match.group("indent").expandtabs(8))
        permission_lines = [match.group("inline")]
        for following in lines[index + 1:]:
            if not following.strip():
                permission_lines.append("")
                continue
            following_indent = len(following) - len(following.lstrip(" \t"))
            if following_indent <= indent:
                break
            permission_lines.append(following.strip())
        for item in permission_lines:
            if re.search(r"\bwrite-all\b", item):
                return True
            permission = re.match(r"(?P<scope>[A-Za-z0-9_-]+):\s*write\b", item)
            if permission and not (allow_security_events and permission.group("scope") == "security-events"):
                return True
    return False

def scan_workflows(root: Path) -> list[str]:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return [f"missing workflow directory: {workflow_dir}"]
    files = sorted(path for path in workflow_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".yml", ".yaml"})
    if not files:
        return [f"no workflow files found under: {workflow_dir}"]
    findings: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        events = _event_block(source)
        has_pull_request = _has_event(events, "pull_request")
        has_pull_request_target = _has_event(events, "pull_request_target")
        has_secrets = bool(re.search(r"\bsecrets(?:\.|\s*:)", source))
        checks_out_code = bool(re.search(r"(?m)^\s+uses:\s*actions/checkout@", source))
        persist_false = bool(re.search(r"(?m)^\s+persist-credentials:\s*false\s*$", source))
        untrusted_ref = bool(re.search(r"refs/pull/|github\.event\.pull_request|github\.event\.inputs\.sha|inputs\.sha", source))
        if has_pull_request_target:
            findings.append(f"{relative}: pull_request_target is forbidden")
        if has_pull_request and has_secrets:
            findings.append(f"{relative}: pull_request workflow must not reference secrets")
        if has_pull_request and _has_unsafe_write_permissions(source, allow_security_events=path.name in ALLOWED_SECURITY_EVENT_WORKFLOWS):
            findings.append(f"{relative}: unsafe write permission in pull_request workflow")
        if has_pull_request and checks_out_code and not persist_false:
            findings.append(f"{relative}: pull_request checkout must set persist-credentials: false")
        if has_secrets and untrusted_ref:
            findings.append(f"{relative}: secrets combined with PR-controlled/operator-supplied ref")
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
    print("Workflow trust-boundary checks passed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
