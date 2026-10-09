#!/usr/bin/env bash
# staging-gate.sh - runs on the GitHub runner before a PRODUCTION build.
# Same file in every microservice repo; keep them identical.
#
#   staging-gate.sh <image-repo> <tree-hash>
#
# Passes only if <image-repo>:staging-tree-<tree-hash> exists in GHCR. The
# staging job pushes that tag after the staging container passed its health
# check, so it means "this exact source tree ran healthy on staging".
# The tree hash (git rev-parse HEAD^{tree}) is the same for a branch and for its
# squash- or merge-commit on main, as long as main had not moved in between.
#
# SKIP_STAGING_GATE=true (the workflow_dispatch emergency override) passes with
# a warning. Needs `docker login ghcr.io` first.
set -euo pipefail
REPO=${1:?image repo, e.g. ghcr.io/org/name}
TREE=${2:?tree hash required}
[[ $TREE =~ ^[0-9a-f]{40}$ ]] || { echo "::error::bad tree hash '$TREE'"; exit 2; }
TAG="$REPO:staging-tree-$TREE"

if [ "${SKIP_STAGING_GATE:-false}" = true ]; then
  echo "::warning title=Staging gate skipped::skip_staging_gate=true - deploying tree $TREE to production without checking that it ran on staging."
  exit 0
fi

if out=$(docker buildx imagetools inspect "$TAG" 2>&1); then
  echo "Staging gate passed: $TAG exists ($(printf '%s\n' "$out" | grep -m1 '^Digest:' | tr -s ' ' || true))."
  exit 0
fi

cat <<EOF
::error title=Not deployed to staging::Tree $TREE has not been deployed to staging (no $TAG). Deploy it first: git push origin HEAD:staging, or run this workflow with environment=staging. A squash merge keeps the tree only if main had not moved; if it had, stage main itself. Emergency only: dispatch with skip_staging_gate=true.
EOF
printf '   registry said: %s\n' "$(printf '%s' "$out" | head -n2 | tr '\n' ' ')"
exit 1
