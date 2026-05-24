#!/bin/bash
# deploy.sh — Deploy the HomeStudio LangGraph stack to TrueNAS (HOM-347).
#
# Mirrors home-budgeting-system/deploy.sh: rsync source → ssh → docker.
# Difference vs HBS: the dev box has no Docker daemon, so we cannot
# `langgraph build` + `docker save` locally. Instead we:
#   1. Run `langgraph dockerfile` on the dev box (pure-Python, no Docker)
#      to generate a Dockerfile that pins the canonical
#      langchain/langgraph-api base image and matches what
#      `langgraph build -t homestudio-langgraph` would produce.
#   2. Rsync the graph/ source + generated Dockerfile to TrueNAS.
#   3. `docker build` on TrueNAS, then `docker compose up -d`.
#
# Usage (from repo root):
#   ./deploy.sh                — fast restart: docker compose restart server (no rebuild)
#   ./deploy.sh --rebuild      — rsync source + docker build + recreate (full)
#   ./deploy.sh --secrets      — push .env template to server; halt if not present
#   ./deploy.sh --status       — show container state + recent server logs
#   ./deploy.sh --logs         — tail server logs
#
# Server: TrueNAS SCALE at 192.168.1.115
#   SSH alias: truenas (user: claude, key: ~/.ssh/truenas, passwordless sudo)
#   Server-side project dir: /var/lib/homestudio-langgraph/
#   Containers (HOM-347 port allocations):
#     homestudio-langgraph-postgres  →  host 5443
#     homestudio-langgraph-redis     →  host 6380
#     homestudio-langgraph-server    →  host 8124
#
# Secrets: /var/lib/homestudio-langgraph/.env on the server must contain
#   LANGSMITH_API_KEY=lsv2_...
# This is operator-supplied (free Developer tier at https://smith.langchain.com).
# The file is NEVER committed. `./deploy.sh --secrets` writes a template if
# missing and exits with instructions; `./deploy.sh --rebuild` halts with a
# pointer if the key is absent.

set -e

TRUENAS="truenas"
REMOTE_PROJECT="/var/lib/homestudio-langgraph"
IMAGE_TAG="homestudio-langgraph:local"
SERVER_CONTAINER="homestudio-langgraph-server"
SERVER_SERVICE="homestudio-langgraph-server"
POSTGRES_CONTAINER="homestudio-langgraph-postgres"
REDIS_CONTAINER="homestudio-langgraph-redis"
SERVER_PORT=8124
COMPOSE_FILE="docker-compose.truenas.yml"

# Resolve dev-box langgraph CLI. Prefer the worktree-local venv, fall back to
# the main worktree's venv (graph/.venv/Scripts/langgraph.exe under
# repo root). Cygwin/MinGW path on Windows.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANGGRAPH_CLI=""
for candidate in \
    "$SCRIPT_DIR/graph/.venv/Scripts/langgraph.exe" \
    "$SCRIPT_DIR/graph/.venv/bin/langgraph" \
    "$SCRIPT_DIR/../../graph/.venv/Scripts/langgraph.exe" \
    "$SCRIPT_DIR/../../graph/.venv/bin/langgraph"; do
    if [ -x "$candidate" ]; then LANGGRAPH_CLI="$candidate"; break; fi
done

log()  { echo "[deploy] $*"; }
die()  { echo "[deploy] ERROR: $*" >&2; exit 1; }
warn() { echo "[deploy] WARN: $*" >&2; }

SYNC_TOOL=""
check_prereqs() {
    if command -v rsync >/dev/null 2>&1; then
        SYNC_TOOL="rsync"
    elif command -v tar >/dev/null 2>&1 && command -v ssh >/dev/null 2>&1; then
        SYNC_TOOL="tar-ssh"
        warn "rsync not available — falling back to tar|ssh sync (works fine, just slightly slower for re-syncs)"
    else
        die "Need either rsync or (tar + ssh) for transferring source to truenas"
    fi
    ssh "$TRUENAS" "echo ok" >/dev/null 2>&1 || die "Cannot connect to truenas — check SSH config (~/.ssh/config)"
    ssh "$TRUENAS" "sudo -n docker version >/dev/null" 2>&1 || die "Passwordless sudo docker not working on truenas"
}

# Sync a local directory to a remote path, deleting files on the remote that
# are not present locally. Works with either rsync or a tar|ssh fallback.
sync_dir() {
    local src="$1" dest="$2"
    if [ "$SYNC_TOOL" = "rsync" ]; then
        rsync -av --delete \
            --exclude __pycache__ \
            --exclude '*.pyc' \
            --exclude '.venv' \
            --exclude '.langgraph_api' \
            --exclude '.cache' \
            "$src" "$TRUENAS":"$dest"
    else
        # tar|ssh: pack locally with the same excludes, wipe remote, untar.
        ssh "$TRUENAS" "sudo rm -rf $dest && sudo mkdir -p $dest && sudo chown claude:claude $dest"
        tar -C "$src" \
            --exclude=__pycache__ \
            --exclude='*.pyc' \
            --exclude='.venv' \
            --exclude='.langgraph_api' \
            --exclude='.cache' \
            -cf - . | ssh "$TRUENAS" "tar -C $dest -xf -"
    fi
}

# Sync a single file to a remote path.
sync_file() {
    local src="$1" dest="$2"
    if [ "$SYNC_TOOL" = "rsync" ]; then
        rsync -av "$src" "$TRUENAS":"$dest"
    else
        scp "$src" "$TRUENAS":"$dest" >/dev/null
        log "Copied $(basename "$src") → $dest"
    fi
}

require_secrets() {
    if ! ssh "$TRUENAS" "sudo test -f $REMOTE_PROJECT/.env"; then
        die "Missing $REMOTE_PROJECT/.env on truenas. Run: ./deploy.sh --secrets"
    fi
    if ! ssh "$TRUENAS" "sudo grep -qE '^LANGSMITH_API_KEY=.+$' $REMOTE_PROJECT/.env"; then
        die "LANGSMITH_API_KEY not set in $REMOTE_PROJECT/.env on truenas. Get a free Developer-tier key at https://smith.langchain.com and add it."
    fi
}

push_secrets_template() {
    log "=== Push .env template to $REMOTE_PROJECT/.env ==="
    ssh "$TRUENAS" "sudo mkdir -p $REMOTE_PROJECT && sudo chown claude:claude $REMOTE_PROJECT"
    if ssh "$TRUENAS" "sudo test -f $REMOTE_PROJECT/.env"; then
        warn "$REMOTE_PROJECT/.env already exists on truenas — not overwriting"
    else
        # shellcheck disable=SC2087
        ssh "$TRUENAS" "sudo tee $REMOTE_PROJECT/.env >/dev/null && sudo chmod 600 $REMOTE_PROJECT/.env" <<'EOF'
# HOM-347: HomeStudio LangGraph stack secrets — server-side, operator-supplied.
#
# LANGSMITH_API_KEY: required by langgraph-api boot license check.
# Get a free Developer-tier key at https://smith.langchain.com → Settings → API Keys.
# Self-Hosted Lite plan is the free tier and is what this stack uses.
LANGSMITH_API_KEY=

# Optional: pin LangSmith project / org if running multiple deployments.
# LANGSMITH_PROJECT=homestudio-langgraph
EOF
        log "Wrote $REMOTE_PROJECT/.env (template, 0600 perms)."
    fi
    log ""
    log "Next step: ssh truenas and edit $REMOTE_PROJECT/.env to fill in LANGSMITH_API_KEY."
    log "Then re-run: ./deploy.sh --rebuild"
}

wait_healthy() {
    log "Waiting for langgraph-server to become healthy on port $SERVER_PORT..."
    for i in $(seq 1 30); do
        if ssh "$TRUENAS" "curl -sf http://localhost:$SERVER_PORT/ok" >/dev/null 2>&1; then
            log "langgraph-server is healthy."
            return 0
        fi
        sleep 2
    done
    die "langgraph-server did not respond at /ok after 60s — check: ssh truenas 'sudo docker logs $SERVER_CONTAINER 2>&1 | tail -40'"
}

ensure_dockerfile() {
    [ -n "$LANGGRAPH_CLI" ] || die "langgraph CLI not found in any candidate venv (graph/.venv/...). Activate the dev venv or set LANGGRAPH_CLI explicitly."
    log "Generating Dockerfile via: $LANGGRAPH_CLI dockerfile (pure-Python, no local Docker needed)"
    local build_dir="$SCRIPT_DIR/graph/.build"
    rm -rf "$build_dir"
    mkdir -p "$build_dir"
    # `langgraph dockerfile` writes Dockerfile relative to its target arg.
    # Run it with cwd=graph so langgraph.json is auto-discovered.
    (cd "$SCRIPT_DIR/graph" && "$LANGGRAPH_CLI" dockerfile "$build_dir/Dockerfile") || die "langgraph dockerfile failed"
    # Inject ENV UV_LINK_MODE=copy right after the first FROM. uv's default
    # clonefile/reflink mode produces "Resource temporarily unavailable
    # (os error 11)" inside docker build on TrueNAS (overlay2 over ZFS).
    # Forcing the copy link mode avoids that filesystem code path entirely.
    sed -i '/^FROM /a ENV UV_LINK_MODE=copy' "$build_dir/Dockerfile"
    log "Dockerfile written to graph/.build/Dockerfile (UV_LINK_MODE=copy injected)"
}

deploy_rebuild() {
    log "=== Full rebuild: rsync source + docker build on truenas + recreate stack ==="
    require_secrets
    ensure_dockerfile

    log "Syncing graph/ to $TRUENAS:$REMOTE_PROJECT/graph/..."
    ssh "$TRUENAS" "sudo mkdir -p $REMOTE_PROJECT && sudo chown claude:claude $REMOTE_PROJECT"
    sync_dir "graph/" "$REMOTE_PROJECT/graph"

    # Approach B (HOM-347 fixup): the graph code subprocess-invokes
    # `python -m scripts.pickup` (and similar) with cwd=scripts_root(), which
    # at runtime equals repo_root(). In the container there is no .git/ — we
    # set HOMESTUDIO_REPO_ROOT=/deps/graph in compose, and we need scripts/
    # to exist at /deps/graph/scripts/ so `python -m scripts.X` resolves.
    # Simplest landing: rsync scripts/ INTO the build context as a sibling of
    # src/. The langgraph-generated Dockerfile's `ADD . /deps/graph` then
    # picks it up automatically; no Dockerfile post-edit beyond UV_LINK_MODE.
    log "Syncing scripts/ into $TRUENAS:$REMOTE_PROJECT/graph/scripts/ (for /deps/graph/scripts)..."
    sync_dir "scripts/" "$REMOTE_PROJECT/graph/scripts"

    log "Syncing compose file..."
    sync_file "graph/$COMPOSE_FILE" "$REMOTE_PROJECT/$COMPOSE_FILE"

    log "Building image $IMAGE_TAG on truenas..."
    ssh "$TRUENAS" "cd $REMOTE_PROJECT && sudo docker build --pull -t $IMAGE_TAG -f graph/.build/Dockerfile graph/"

    log "Recreating stack via docker compose..."
    ssh "$TRUENAS" "cd $REMOTE_PROJECT && sudo docker compose -f $COMPOSE_FILE up -d --remove-orphans"

    wait_healthy
    show_status_brief
    log "=== Rebuild done ==="
    log "Studio URL: http://192.168.1.115:$SERVER_PORT"
}

deploy_restart() {
    log "=== Fast restart: docker compose restart $SERVER_SERVICE ==="
    ssh "$TRUENAS" "cd $REMOTE_PROJECT && sudo docker compose -f $COMPOSE_FILE restart $SERVER_SERVICE"
    wait_healthy
    log "=== Restart done ==="
}

show_status_brief() {
    log "Container state:"
    ssh "$TRUENAS" "sudo docker ps --filter name=homestudio-langgraph- --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
}

show_status() {
    show_status_brief
    log "--- Recent server logs (last 40 lines) ---"
    ssh "$TRUENAS" "sudo docker logs --tail 40 $SERVER_CONTAINER" || true
}

tail_logs() {
    log "Tailing $SERVER_CONTAINER logs (Ctrl-C to stop)..."
    ssh "$TRUENAS" "sudo docker logs -f $SERVER_CONTAINER"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

case "${1:-}" in
    --rebuild)  check_prereqs; deploy_rebuild ;;
    --secrets)  check_prereqs; push_secrets_template ;;
    --status)   check_prereqs; show_status ;;
    --logs)     check_prereqs; tail_logs ;;
    "")         check_prereqs; deploy_restart ;;
    *)
        cat <<EOF
Usage: $0 [--rebuild | --secrets | --status | --logs]
  (no args)    fast restart — docker compose restart server (no image rebuild)
  --rebuild    full rebuild — rsync source + langgraph dockerfile + docker build + recreate
  --secrets    push .env template to /var/lib/homestudio-langgraph/.env on truenas
  --status     show container state + recent server logs
  --logs       tail server logs (follow)

Server: truenas (192.168.1.115). Studio after deploy: http://192.168.1.115:$SERVER_PORT
EOF
        exit 1
        ;;
esac
