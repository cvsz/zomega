#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\n' 'Restore verification is disabled until target-cluster identity, target authorization, and production Environment protections are independently verified. See docs/DISASTER_RECOVERY.md.' >&2
exit 64
