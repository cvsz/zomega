#!/usr/bin/env bash
set -euo pipefail

REPO="${ZOMEGA_REPO:-cvsz/zomega}"
BRANCH="${ZOMEGA_PROTECTED_BRANCH:-main}"
ENVIRONMENT="${ZOMEGA_ENVIRONMENT:-production}"
RULESET_NAME="${ZOMEGA_RULESET_NAME:-main-production-protection}"
failures=0

for cmd in gh jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: $cmd is required" >&2; exit 1; }
done

gh auth status >/dev/null

pass() { printf 'PASS    %s\n' "$*"; }
pending() { printf 'PENDING %s\n' "$*"; failures=$((failures + 1)); }

rulesets="$(gh api "repos/$REPO/rulesets")"
ruleset="$(jq -c --arg name "$RULESET_NAME" '.[] | select(.name == $name)' <<<"$rulesets" | head -n1)"
if [[ -z "$ruleset" ]]; then
  pending "active ruleset $RULESET_NAME"
else
  ruleset_id="$(jq -r '.id' <<<"$ruleset")"
  detail="$(gh api "repos/$REPO/rulesets/$ruleset_id")"
  if jq -e '.enforcement == "active"' <<<"$detail" >/dev/null; then pass "ruleset enforcement active"; else pending "ruleset enforcement active"; fi
  for rule in deletion non_fast_forward pull_request required_status_checks; do
    if jq -e --arg type "$rule" '.rules | any(.type == $type)' <<<"$detail" >/dev/null; then pass "ruleset rule: $rule"; else pending "ruleset rule: $rule"; fi
  done
  for context in unit integration 'Analyze Actions and Python' application-security dependency-review; do
    if jq -e --arg context "$context" '[.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[]?.context] | index($context) != null' <<<"$detail" >/dev/null; then
      pass "required check: $context"
    else
      pending "required check: $context"
    fi
  done
fi

branch_protection=""
if branch_protection="$(gh api "repos/$REPO/branches/$BRANCH/protection" 2>/dev/null)"; then
  pass "legacy branch protection readable"
  if jq -e '.required_status_checks.strict == true' <<<"$branch_protection" >/dev/null; then
    pass "branch protection strict status checks"
  else
    pending "branch protection strict status checks"
  fi
  for context in unit integration 'Analyze Actions and Python' application-security dependency-review; do
    if jq -e --arg context "$context" '.required_status_checks.contexts | index($context) != null' <<<"$branch_protection" >/dev/null; then
      pass "branch protection required check: $context"
    else
      pending "branch protection required check: $context"
    fi
  done
  if jq -e '.required_pull_request_reviews.required_approving_review_count >= 1' <<<"$branch_protection" >/dev/null; then
    pass "branch protection review requirement"
  else
    pending "branch protection review requirement"
  fi
  if jq -e '.allow_force_pushes.enabled == false and .allow_deletions.enabled == false' <<<"$branch_protection" >/dev/null; then
    pass "branch protection blocks force-push and deletion"
  else
    pending "branch protection blocks force-push and deletion"
  fi
else
  pending "legacy branch protection readable"
fi

repo_json="$(gh api "repos/$REPO")"
if jq -e '.security_and_analysis.secret_scanning.status == "enabled"' <<<"$repo_json" >/dev/null 2>&1; then pass "secret scanning enabled"; else pending "secret scanning enabled"; fi
if jq -e '.security_and_analysis.secret_scanning_push_protection.status == "enabled"' <<<"$repo_json" >/dev/null 2>&1; then pass "push protection enabled"; else pending "push protection enabled"; fi
if gh api "repos/$REPO/vulnerability-alerts" >/dev/null 2>&1; then pass "Dependabot alerts enabled"; else pending "Dependabot alerts enabled"; fi
if gh api "repos/$REPO/automated-security-fixes" >/dev/null 2>&1; then pass "Dependabot security updates enabled"; else pending "Dependabot security updates enabled"; fi

environment_json=""
if environment_json="$(gh api "repos/$REPO/environments/$ENVIRONMENT" 2>/dev/null)"; then
  pass "GitHub Environment $ENVIRONMENT exists"
  if jq -e '[.protection_rules[]? | select(.type == "required_reviewers") | .reviewers[]?] | length >= 1' <<<"$environment_json" >/dev/null; then
    pass "production required reviewer configured"
  else
    pending "production required reviewer configured"
  fi
else
  pending "GitHub Environment $ENVIRONMENT exists"
fi

secret_names="$(gh secret list --env "$ENVIRONMENT" --repo "$REPO" --json name 2>/dev/null | jq -r '.[].name' || true)"
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
  if grep -Fxq "$name" <<<"$secret_names"; then pass "production secret present: $name"; else pending "production secret present: $name"; fi
done

variable_names="$(gh variable list --env "$ENVIRONMENT" --repo "$REPO" --json name 2>/dev/null | jq -r '.[].name' || true)"
if grep -Fxq ZOMEGA_HEALTH_URL <<<"$variable_names" || grep -Fxq OMEGA_HEALTH_URL <<<"$variable_names"; then
  pass "production health URL variable present"
else
  pending "production health URL variable present"
fi

branch_sha="$(gh api "repos/$REPO/commits/$BRANCH" --jq .sha)"
checks="$(gh api "repos/$REPO/commits/$branch_sha/check-runs" --jq '.check_runs[] | select(.conclusion == "success") | .name' || true)"
for context in unit integration 'Analyze Actions and Python' application-security; do
  if grep -Fxq "$context" <<<"$checks"; then pass "latest $BRANCH check successful: $context"; else pending "latest $BRANCH check successful: $context"; fi
done

if dep_json="$(gh run list --repo "$REPO" --workflow 'Dependency Review' --limit 1 --json conclusion,status 2>/dev/null)" && jq -e '.[0].status == "completed" and .[0].conclusion == "success"' <<<"$dep_json" >/dev/null; then
  pass "latest Dependency Review successful"
else
  pending "latest Dependency Review successful"
fi

health_url="${ZOMEGA_HEALTH_URL:-${OMEGA_HEALTH_URL:-}}"
if [[ -z "$health_url" ]]; then
  health_url="$(gh variable get ZOMEGA_HEALTH_URL --env "$ENVIRONMENT" --repo "$REPO" 2>/dev/null || true)"
fi
if [[ -n "$health_url" ]]; then
  health_url="${health_url%/}"
  if curl --fail --silent --show-error --retry 3 --retry-all-errors "$health_url/health/ready" >/dev/null; then
    pass "external /health/ready"
  else
    pending "external /health/ready"
  fi
else
  pending "external /health/ready (health URL unavailable)"
fi

if (( failures > 0 )); then
  echo "RESULT: PENDING ($failures item(s))"
  exit 1
fi

echo "RESULT: PASS"
