#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\n' \
  'Direct database restore is disabled. This entry point never invokes pg_restore.' \
  'Use the separately reviewed disaster-recovery procedure and a verified disposable target.' \
  'See docs/DISASTER_RECOVERY.md. Do not use the disposable verification drill for production recovery.' >&2
exit 64
