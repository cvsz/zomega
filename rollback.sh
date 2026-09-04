#!/usr/bin/env bash
set -Eeuo pipefail
LATEST="$(ls -1t backups/zomega-*.db 2>/dev/null | head -n1 || true)"
[ -n "$LATEST" ] || { echo "No backup found"; exit 2; }
cp "$LATEST" .zomega/zomega.db
echo "Rolled back database to $LATEST"
