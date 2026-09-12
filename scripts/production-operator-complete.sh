#!/usr/bin/env bash
set -euo pipefail

REPO="${ZOMEGA_REPO:-cvsz/zomega}"
BRANCH="${ZOMEGA_PROTECTED_BRANCH:-main}"
ENVIRONMENT="${ZOMEGA_ENVIRONMENT:-production}"
RULESET_NAME="${ZOMEGA_RULESET_NAME:-main-production-protection}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for cmd in gh jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: $cmd is required" >&2; exit 1; }
done

gh auth status >/dev/null

echo "==> Configuring repository security for $REPO"
if ! gh api --method PUT "repos/$REPO/vulnerability-alerts" >/dev/null; then
  echo "WARN: could not enable Dependabot alerts; verify repository plan/admin permissions" >&2
fi
if ! gh api --method PUT "repos/$REPO/automated-security-fixes" >/dev/null; then
  echo "WARN: could not enable Dependabot security updates; verify repository plan/admin permissions" >&2
fi

security_payload="$(mktemp)"
trap 'rm -f "$security_payload"' EXIT
cat >"$security_payload" <<'JSON'
{
  "security_and_analysis": {
    "secret_scanning": {"status": "enabled"},
    "secret_scanning_push_protection": {"status": "enabled"}
  }
}
JSON
if ! gh api --method PATCH "repos/$REPO" --input "$security_payload" >/dev/null; then
  echo "WARN: could not enable secret scanning/push protection through the API" >&2
fi

echo "==> Applying main-branch ruleset"
ruleset_payload="$(mktemp)"
trap 'rm -f "$security_payload" "$ruleset_payload"' EXIT
cat >"$ruleset_payload" <<JSON
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/$BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {
      "type": "pull_request",
      "parameters": {
        "allowed_merge_methods": ["merge", "squash", "rebase"],
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          {"context": "unit"},
          {"context": "integration"},
          {"context": "Analyze Actions and Python"},
          {"context": "application-security"},
          {"context": "dependency-review"}
        ]
      }
    }
  ]
}
JSON
ruleset_id="$(gh api "repos/$REPO/rulesets" | jq -r --arg name "$RULESET_NAME" '.[] | select(.name == $name) | .id' | head -n1)"
if [[ -n "$ruleset_id" ]]; then
  gh api --method PUT "repos/$REPO/rulesets/$ruleset_id" --input "$ruleset_payload" >/dev/null
  echo "Updated ruleset $RULESET_NAME ($ruleset_id)"
else
  gh api --method POST "repos/$REPO/rulesets" --input "$ruleset_payload" >/dev/null
  echo "Created ruleset $RULESET_NAME"
fi

echo "==> Reconciling legacy branch protection"
branch_protection_payload="$(mktemp)"
trap 'rm -f "$security_payload" "$ruleset_payload" "$branch_protection_payload"' EXIT
if ! existing_branch_protection="$(gh api "repos/$REPO/branches/$BRANCH/protection")"; then
  echo "ERROR: unable to read existing branch protection for $BRANCH; refusing to reconcile without preserving current restrictions" >&2
  exit 1
fi
restrictions_payload="$(jq -c '
  if .restrictions == null then null
  else {
    users: [.restrictions.users[]?.login],
    teams: [.restrictions.teams[]?.slug],
    apps: [.restrictions.apps[]?.slug]
  }
  end
' <<<"$existing_branch_protection")"
dismissal_restrictions_payload="$(jq -c '
  if .required_pull_request_reviews.dismissal_restrictions == null then {}
  else {
    users: [.required_pull_request_reviews.dismissal_restrictions.users[]?.login],
    teams: [.required_pull_request_reviews.dismissal_restrictions.teams[]?.slug],
    apps: [.required_pull_request_reviews.dismissal_restrictions.apps[]?.slug]
  }
  end
' <<<"$existing_branch_protection")"
bypass_pull_request_allowances_payload="$(jq -c '
  if .required_pull_request_reviews.bypass_pull_request_allowances == null then {}
  else {
    users: [.required_pull_request_reviews.bypass_pull_request_allowances.users[]?.login],
    teams: [.required_pull_request_reviews.bypass_pull_request_allowances.teams[]?.slug],
    apps: [.required_pull_request_reviews.bypass_pull_request_allowances.apps[]?.slug]
  }
  end
' <<<"$existing_branch_protection")"
cat >"$branch_protection_payload" <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "unit",
      "integration",
      "Analyze Actions and Python",
      "application-security",
      "dependency-review"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismissal_restrictions": $dismissal_restrictions_payload,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1,
    "require_last_push_approval": false,
    "bypass_pull_request_allowances": $bypass_pull_request_allowances_payload
  },
  "restrictions": $restrictions_payload,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON
gh api --method PUT "repos/$REPO/branches/$BRANCH/protection" --input "$branch_protection_payload" >/dev/null

echo "==> Configuring protected GitHub Environment: $ENVIRONMENT"
reviewer_id="$(gh api user --jq .id)"
environment_payload="$(mktemp)"
trap 'rm -f "$security_payload" "$ruleset_payload" "$branch_protection_payload" "$environment_payload"' EXIT
cat >"$environment_payload" <<JSON
{
  "wait_timer": 0,
  "prevent_self_review": false,
  "reviewers": [{"type": "User", "id": $reviewer_id}],
  "deployment_branch_policy": {"protected_branches": true, "custom_branch_policies": false}
}
JSON
gh api --method PUT "repos/$REPO/environments/$ENVIRONMENT" --input "$environment_payload" >/dev/null

if [[ -z "${KUBECONFIG_B64:-}" && -n "${KUBECONFIG:-}" && -f "${KUBECONFIG}" ]]; then
  export KUBECONFIG_B64="$(base64 <"$KUBECONFIG" | tr -d '\n')"
fi

set_env_secret_if_present() {
  local name="$1"
  local value="${!name:-}"
  if [[ -n "$value" ]]; then
    printf '%s' "$value" | gh secret set "$name" --env "$ENVIRONMENT" --repo "$REPO" --body - >/dev/null
    echo "Set environment secret: $name"
  else
    echo "PENDING input: $name"
  fi
}

for name in \
  KUBECONFIG_B64 \
  DR_SOURCE_DATABASE_URL \
  DR_RESTORE_DATABASE_URL \
  DATABASE_URL \
  REDIS_URL \
  ZOMEGA_API_KEY_PEPPER \
  ZOMEGA_ADMIN_TOKEN \
  OPENAI_API_KEY \
  STRIPE_SECRET_KEY \
  STRIPE_WEBHOOK_SECRET \
  STRIPE_PRICE_CREDITS_1000 \
  STRIPE_PRICE_CREDITS_5000 \
  STRIPE_PRICE_CREDITS_20000; do
  set_env_secret_if_present "$name"
done

health_url="${ZOMEGA_HEALTH_URL:-${OMEGA_HEALTH_URL:-}}"
public_url="${ZOMEGA_PUBLIC_URL:-$health_url}"
if [[ -n "$health_url" ]]; then
  gh variable set ZOMEGA_HEALTH_URL --env "$ENVIRONMENT" --repo "$REPO" --body "$health_url" >/dev/null
  gh variable set OMEGA_HEALTH_URL --env "$ENVIRONMENT" --repo "$REPO" --body "$health_url" >/dev/null
  echo "Set production health URL variables"
else
  echo "PENDING input: ZOMEGA_HEALTH_URL (or OMEGA_HEALTH_URL)"
fi
if [[ -n "$public_url" ]]; then
  gh variable set ZOMEGA_PUBLIC_URL --env "$ENVIRONMENT" --repo "$REPO" --body "$public_url" >/dev/null
fi

echo "==> Verification"
if ! "$SCRIPT_DIR/production-operator-verify.sh"; then
  echo
  echo "Repository-side controls were applied where permitted, but production completion still has missing inputs/evidence." >&2
  exit 2
fi
