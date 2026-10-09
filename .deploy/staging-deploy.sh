#!/usr/bin/env bash
# staging-deploy.sh - runs ON the AI box. Rolls ONE staging service to an exact
# image digest, and nothing else.
#
# The same file ships in every microservice repo (.deploy/staging-deploy.sh);
# keep the copies identical. The workflow uploads it with staging-remote.sh.
#
#   staging-deploy.sh --dir=<dir> --service=<svc> --image=<repo@sha256:...>
#                     [--pin-var=NAME] [--migrate=<spec>]
#                     (--health-port=N [--health-path=/health] | --health-host-url=URL)
#                     [--health-expect=key=value] [--preflight]
#
#   --dir          staging compose directory; relative paths are under $HOME.
#                  Its name MUST end in -staging.
#   --service      compose service to roll. MUST end in -staging, and so must
#                  the container it runs as.
#   --image        immutable reference, repo@sha256:<64 hex>. Never a tag.
#   --pin-var      if the compose file interpolates ${NAME}, the pin is the
#                  NAME= line of <dir>/.env (the ms-staging contract). Otherwise
#                  the pin is a marked docker-compose.override.yml written here.
#   --migrate      none (default)
#                  compose <cmd...>   docker compose run --rm --no-deps -T <svc> <cmd...>
#                  script <file> <args...>  <dir>/<file> <args...> (e.g. ms-staging's migrate.sh)
#                  Runs with the NEW image, before the live container is touched.
#   --health-*     probe http://127.0.0.1:<port><path> inside the container
#                  (docker exec ... python), or a URL from the host (python3).
#                  --health-expect=k=v also requires JSON field k == v.
#   --preflight    validate the arguments and the -staging guards, then exit
#                  without calling docker (the workflow runs this on the runner).
#
# Order: guards -> lock -> pull -> pin -> verify pin -> migrate -> recreate
#        -> verify container -> health -> (rollback to previous pin on failure).
# A failure before "recreate" leaves the live container untouched.
# Migrations are forward-only: a rollback restores the old image, not the schema.
set -euo pipefail

die()  { echo "ERROR: $*" >&2; exit 2; }
say()  { printf '==> %s\n' "$*"; }

DIR="" SVC="" IMAGE="" PIN_VAR="" MIGRATE="none"
HEALTH_PORT="" HEALTH_PATH="/health" HEALTH_HOST_URL="" HEALTH_EXPECT="" PREFLIGHT=0
HEALTH_ATTEMPTS=${HEALTH_ATTEMPTS:-40}
HEALTH_SLEEP=${HEALTH_SLEEP:-3}
PULL_SLEEP=${PULL_SLEEP:-10}

for arg in "$@"; do
  case $arg in
    --dir=*)             DIR=${arg#*=} ;;
    --service=*)         SVC=${arg#*=} ;;
    --image=*)           IMAGE=${arg#*=} ;;
    --pin-var=*)         PIN_VAR=${arg#*=} ;;
    --migrate=*)         MIGRATE=${arg#*=} ;;
    --health-port=*)     HEALTH_PORT=${arg#*=} ;;
    --health-path=*)     HEALTH_PATH=${arg#*=} ;;
    --health-host-url=*) HEALTH_HOST_URL=${arg#*=} ;;
    --health-expect=*)   HEALTH_EXPECT=${arg#*=} ;;
    --preflight)         PREFLIGHT=1 ;;
    *) die "unknown argument: $arg" ;;
  esac
done

# ── Guards that need no docker ──────────────────────────────────────────────
[ -n "$DIR" ] || die "--dir is required"
[ -n "$SVC" ] || die "--service is required"
[ -n "$IMAGE" ] || die "--image is required"
case $DIR in *..*) die "--dir may not contain '..': $DIR" ;; esac
case ${DIR%/} in
  *-staging) ;;
  *) die "refusing: target dir '$DIR' does not end in -staging. This script only deploys staging." ;;
esac
case $SVC in
  *-staging) ;;
  *) die "refusing: service '$SVC' does not end in -staging. This script only deploys staging." ;;
esac
[[ $SVC =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die "bad service name: $SVC"
[[ $IMAGE =~ ^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$ ]] || die "refusing non-digest image '$IMAGE' (deploys use repo@sha256:<digest>, never a tag)"
if [ -n "$PIN_VAR" ]; then [[ $PIN_VAR =~ ^[A-Z_][A-Z0-9_]*$ ]] || die "bad --pin-var: $PIN_VAR"; fi
if [ -n "$HEALTH_HOST_URL" ]; then
  [[ $HEALTH_HOST_URL =~ ^http://(127\.0\.0\.1|localhost):[0-9]+/ ]] || die "--health-host-url must be a loopback http URL"
else
  [[ $HEALTH_PORT =~ ^[0-9]+$ ]] || die "--health-port (or --health-host-url) is required"
  case $HEALTH_PATH in /*) ;; *) die "--health-path must start with /" ;; esac
fi
if [ -n "$HEALTH_EXPECT" ]; then [[ $HEALTH_EXPECT =~ ^[A-Za-z0-9_]+=.+$ ]] || die "--health-expect must be key=value"; fi
read -r -a MIG <<<"$MIGRATE"
case ${MIG[0]:-none} in
  none) ;;
  compose) [ ${#MIG[@]} -ge 2 ] || die "--migrate=compose needs a command" ;;
  script)  [ ${#MIG[@]} -ge 2 ] || die "--migrate=script needs a file"
           case ${MIG[1]} in /*|*..*) die "--migrate=script file must be relative to --dir" ;; esac ;;
  *) die "unknown --migrate kind: ${MIG[0]}" ;;
esac

if [ "$PREFLIGHT" = 1 ]; then
  say "preflight ok: $SVC in $DIR -> $IMAGE (migrate: $MIGRATE)"
  exit 0
fi

# ── Guards on the box ───────────────────────────────────────────────────────
case $DIR in /*) ;; *) DIR=$HOME/$DIR ;; esac
[ -d "$DIR" ] || die "$DIR does not exist: the staging stack is not set up on this box. Nothing changed."
DIR=$(cd "$DIR" && pwd -P)
case $(basename "$DIR") in
  *-staging) ;;
  *) die "refusing: $DIR resolves outside a -staging directory" ;;
esac
cd "$DIR"

BASE=""
for f in compose.yaml compose.yml docker-compose.yml docker-compose.yaml; do
  if [ -f "$f" ]; then BASE=$f; break; fi
done
[ -n "$BASE" ] || die "no compose file in $DIR. Nothing changed."
case $BASE in compose.*) OVERRIDE=compose.override.yaml ;; *) OVERRIDE=docker-compose.override.yml ;; esac
MARK="# staging-deploy.sh image pin"

# One staging deploy at a time per directory: ms-staging is shared by four repos.
if command -v flock >/dev/null 2>&1; then
  exec 9>"$DIR/.staging-deploy.lock"
  flock -w 900 9 || die "another staging deploy holds $DIR/.staging-deploy.lock"
fi

container_name() { docker inspect -f '{{.Name}}' "$1" | sed 's#^/##'; }

LIVE=$(docker compose ps -q "$SVC" </dev/null | head -n1 || true)
OLD_IMAGE=""
if [ -n "$LIVE" ]; then
  LIVE_NAME=$(container_name "$LIVE")
  case $LIVE_NAME in *-staging) ;; *) die "refusing: live container '$LIVE_NAME' for $SVC does not end in -staging" ;; esac
  OLD_IMAGE=$(docker inspect -f '{{.Config.Image}}' "$LIVE")
fi
say "target: $SVC in $DIR; live: ${LIVE_NAME:-none} on ${OLD_IMAGE:-none}"

# ── Pin mode ────────────────────────────────────────────────────────────────
MODE=override
if [ -n "$PIN_VAR" ] && grep -qE "\\\$\\{$PIN_VAR([:?}-]|\$)" "$BASE"; then MODE=var; fi

set_var() {  # set_var NAME VALUE  - one line in .env, in place, other lines kept
  local tmp; tmp=$(mktemp "$DIR/.env.tmp.XXXXXX")
  grep -v "^$1=" .env >"$tmp" || true
  if [ -s "$tmp" ] && [ -n "$(tail -c1 "$tmp")" ]; then echo >>"$tmp"; fi
  printf '%s=%s\n' "$1" "$2" >>"$tmp"
  cat "$tmp" >.env; rm -f "$tmp"
}
unset_var() {
  local tmp; tmp=$(mktemp "$DIR/.env.tmp.XXXXXX")
  grep -v "^$1=" .env >"$tmp" || true
  cat "$tmp" >.env; rm -f "$tmp"
}

HAD_PIN=0 OLD_PIN=""
if [ "$MODE" = var ]; then
  [ -f .env ] || die "$DIR/.env missing; $BASE expects \${$PIN_VAR} from it. Nothing changed."
  if grep -q "^$PIN_VAR=" .env; then HAD_PIN=1; OLD_PIN=$(grep "^$PIN_VAR=" .env | tail -n1 | cut -d= -f2-); fi
  say "pin: $PIN_VAR in $DIR/.env (was ${OLD_PIN:-unset})"
else
  if [ -f "$OVERRIDE" ]; then
    head -n1 "$OVERRIDE" | grep -qF "$MARK" || die "$DIR/$OVERRIDE exists and was not written by this script; refusing to overwrite it"
    HAD_PIN=1; OLD_PIN=$(cat "$OVERRIDE")
  fi
  if [ "$HAD_PIN" = 1 ]; then say "pin: $DIR/$OVERRIDE (replacing the previous pin)"; else say "pin: $DIR/$OVERRIDE (new file)"; fi
fi

apply_pin() {
  if [ "$MODE" = var ]; then
    set_var "$PIN_VAR" "$1"
  else
    printf '%s. Rewritten by every staging deploy; delete it to fall\n# back to the image in %s.\nservices:\n  %s:\n    image: %s\n' \
      "$MARK" "$BASE" "$SVC" "$1" >"$OVERRIDE"
  fi
}
restore_pin() {
  if [ "$MODE" = var ]; then
    if [ "$HAD_PIN" = 1 ]; then set_var "$PIN_VAR" "$OLD_PIN"; else unset_var "$PIN_VAR"; fi
  else
    if [ "$HAD_PIN" = 1 ]; then printf '%s\n' "$OLD_PIN" >"$OVERRIDE"; else rm -f "$OVERRIDE"; fi
  fi
  say "pin restored"
}

# ── Pull (nothing changed yet) ──────────────────────────────────────────────
pulled=0
for i in 1 2 3; do
  if docker pull -q "$IMAGE" </dev/null; then pulled=1; break; fi
  echo "pull attempt $i failed; retrying in ${PULL_SLEEP}s" >&2; sleep "$PULL_SLEEP"
done
[ "$pulled" = 1 ] || die "could not pull $IMAGE. Nothing changed."

apply_pin "$IMAGE"
if ! docker compose config "$SVC" </dev/null 2>/dev/null | grep -qF "image: $IMAGE"; then
  restore_pin
  die "the pin did not take: 'docker compose config $SVC' does not show $IMAGE. Nothing else changed."
fi

# ── Migrate with the new image, live container still serving ────────────────
case ${MIG[0]:-none} in
  none) say "migrate: none" ;;
  compose)
    say "migrate: docker compose run --rm --no-deps -T $SVC ${MIG[*]:1}"
    if ! docker compose run --rm --no-deps -T "$SVC" "${MIG[@]:1}" </dev/null; then
      restore_pin; die "migration failed; $SVC left on ${OLD_IMAGE:-its old image}. Check the staging DB: a migration may be half applied."
    fi ;;
  script)
    [ -x "$DIR/${MIG[1]}" ] || { restore_pin; die "$DIR/${MIG[1]} is missing or not executable. Nothing else changed."; }
    say "migrate: $DIR/${MIG[*]:1}"
    if ! "$DIR/${MIG[1]}" "${MIG[@]:2}" </dev/null; then
      restore_pin; die "migration failed; $SVC left on ${OLD_IMAGE:-its old image}. Check the staging DB: a migration may be half applied."
    fi ;;
esac

# ── Health ──────────────────────────────────────────────────────────────────
PROBE='
import json, sys, urllib.request
url, expect = sys.argv[1], sys.argv[2]
try:
    body = urllib.request.urlopen(url, timeout=5).read()
except Exception as e:
    print("   %s: %s" % (url, e)); sys.exit(1)
if expect:
    k, v = expect.split("=", 1)
    try:
        got = json.loads(body).get(k)
    except Exception:
        got = None
    if str(got) != v:
        print("   %s: %s=%s, want %s" % (url, k, got, v)); sys.exit(1)
print("   %s -> %s" % (url, body[:200].decode("utf-8", "replace")))
'
current() { docker compose ps -q "$SVC" </dev/null | head -n1; }
healthy() {  # healthy <attempts>
  local cid
  for i in $(seq 1 "$1"); do
    cid=$(current || true)
    if [ -n "$cid" ] && [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)" = true ]; then
      if [ -n "$HEALTH_HOST_URL" ]; then
        python3 -c "$PROBE" "$HEALTH_HOST_URL" "$HEALTH_EXPECT" && return 0
      else
        docker exec "$cid" python -c "$PROBE" "http://127.0.0.1:$HEALTH_PORT$HEALTH_PATH" "$HEALTH_EXPECT" </dev/null && return 0
      fi
    fi
    sleep "$HEALTH_SLEEP"
  done
  return 1
}

rollback() {
  echo "ERROR: $1 - rolling $SVC back" >&2
  cid=$(current || true)
  [ -n "$cid" ] && docker logs --tail 40 "$cid" 2>&1 | sed 's/^/   | /' >&2 || true
  restore_pin
  if [ "$HAD_PIN" = 1 ] || [ -n "$OLD_IMAGE" ]; then
    docker compose up -d --no-deps --no-build --force-recreate "$SVC" </dev/null || true
    if healthy "$HEALTH_ATTEMPTS"; then echo "rolled back to ${OLD_IMAGE:-the previous pin}; $SVC healthy" >&2
    else echo "ERROR: rollback is unhealthy too - intervene in $DIR" >&2; fi
  else
    echo "no previous image to return to; $SVC left as is for inspection" >&2
  fi
  exit 1
}

# ── Recreate only this service ──────────────────────────────────────────────
say "recreate: $SVC"
docker compose up -d --no-deps --no-build --force-recreate "$SVC" </dev/null || rollback "docker compose up failed"

NEW=$(current || true)
[ -n "$NEW" ] || rollback "no container for $SVC after up"
NEW_NAME=$(container_name "$NEW")
case $NEW_NAME in *-staging) ;; *) rollback "new container '$NEW_NAME' does not end in -staging" ;; esac
[ "$(docker inspect -f '{{.Config.Image}}' "$NEW")" = "$IMAGE" ] || rollback "$NEW_NAME is not running $IMAGE"

say "health: ${HEALTH_HOST_URL:-$NEW_NAME:$HEALTH_PORT$HEALTH_PATH}${HEALTH_EXPECT:+ ($HEALTH_EXPECT)}"
healthy "$HEALTH_ATTEMPTS" || rollback "health check failed"

docker image prune -f >/dev/null 2>&1 || true
say "STAGING_DEPLOYED $SVC $IMAGE"
