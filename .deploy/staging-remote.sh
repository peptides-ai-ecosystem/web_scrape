#!/usr/bin/env bash
# staging-remote.sh - runs on the GitHub runner. Checks the arguments locally,
# logs the AI box in to GHCR, uploads staging-deploy.sh and runs it there with
# the same arguments. Same file in every microservice repo; keep them identical.
#
#   EC2_HOST EC2_USER EC2_SSH_KEY GHCR_ACTOR GHCR_TOKEN [EC2_KNOWN_HOSTS] \
#     staging-remote.sh <staging-deploy.sh arguments...>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)

# The -staging guards and the digest check run here first, so a bad argument
# fails on the runner before any connection is made.
bash "$HERE/staging-deploy.sh" "$@" --preflight

: "${EC2_HOST:?EC2_HOST required}"
: "${EC2_USER:?EC2_USER required}"
: "${EC2_SSH_KEY:?EC2_SSH_KEY required}"
: "${GHCR_ACTOR:?GHCR_ACTOR required}"
: "${GHCR_TOKEN:?GHCR_TOKEN required}"

KEY_FILE=$(mktemp); KNOWN_HOSTS_FILE=""
trap 'rm -f "$KEY_FILE" ${KNOWN_HOSTS_FILE:+"$KNOWN_HOSTS_FILE"}' EXIT
printf '%s\n' "$EC2_SSH_KEY" >"$KEY_FILE"; chmod 600 "$KEY_FILE"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=30 -i "$KEY_FILE")
if [ -n "${EC2_KNOWN_HOSTS:-}" ]; then
  KNOWN_HOSTS_FILE=$(mktemp)
  printf '%s\n' "$EC2_KNOWN_HOSTS" >"$KNOWN_HOSTS_FILE"
  SSH_OPTS=(-o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS_FILE" -o ConnectTimeout=10 -o ServerAliveInterval=30 -i "$KEY_FILE")
fi
TARGET="${EC2_USER}@${EC2_HOST}"

# The token travels on stdin, never in argv. The actor and the arguments are
# deliberately expanded here, on the runner, already %q-quoted.
# shellcheck disable=SC2029
printf '%s\n' "$GHCR_TOKEN" | ssh "${SSH_OPTS[@]}" "$TARGET" "docker login ghcr.io -u $(printf '%q' "$GHCR_ACTOR") --password-stdin >/dev/null"

# Upload to a temp file and run it from there, so nothing the script starts can
# read the rest of the script from stdin.
ARGS=$(printf ' %q' "$@")
# shellcheck disable=SC2029
ssh "${SSH_OPTS[@]}" "$TARGET" "f=\$(mktemp); trap 'rm -f \"\$f\"' EXIT; cat >\"\$f\"; bash \"\$f\"$ARGS" <"$HERE/staging-deploy.sh"
