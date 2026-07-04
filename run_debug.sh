#!/usr/bin/env bash
#
# run_debug.sh — SPEC-INFRA-001 Dockerized Milvus Station debug launcher
#
# What it does:
#   1) Force-installs all prerequisites (Homebrew, Docker, Docker Compose).
#   2) Starts the Docker daemon and waits until ready.
#   3) Prepares .env from .env.example if missing.
#   4) Builds + pulls, then runs the full 8-service stack in the FOREGROUND
#      (DEBUG mode: plain BuildKit progress + streaming container logs — NOT hidden).
#   5) A background watcher waits until every service is healthy, then OPENS THE FRONTEND.
#   6) When you TERMINATE this script (Ctrl+C / SIGTERM / exit), it STOPS the
#      containers automatically via `docker compose down`.
#
# Usage:   ./run_debug.sh
#          ./run_debug.sh --no-open      # do not auto-open the browser
#          ./run_debug.sh --down         # just tear the stack down and exit
#
set -euo pipefail

# ------------------------------------------------------------------ config ---
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
LOG_FILE="$PROJECT_DIR/run_debug.log"
INGRESS_PORT="$(grep -E '^INGRESS_PORT=' .env.example 2>/dev/null | cut -d= -f2 || true)"
INGRESS_PORT="${INGRESS_PORT:-38005}"
FRONTEND_URL="http://localhost:${INGRESS_PORT}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-900}"   # seconds to wait for all services healthy
OPEN_BROWSER=1
WATCHER_PID=""
CLEANED_UP=0

# DEBUG mode: force plain, verbose build/run output.
export DOCKER_BUILDKIT=1
export BUILDKIT_PROGRESS=plain
export COMPOSE_MENU=0

# --------------------------------------------------------------- utilities ---
c_reset=$'\033[0m'; c_blue=$'\033[1;34m'; c_grn=$'\033[1;32m'; c_yel=$'\033[1;33m'; c_red=$'\033[1;31m'
log()  { printf '%s[run_debug]%s %s\n' "$c_blue" "$c_reset" "$*" | tee -a "$LOG_FILE"; }
ok()   { printf '%s[  ok    ]%s %s\n' "$c_grn"  "$c_reset" "$*" | tee -a "$LOG_FILE"; }
warn() { printf '%s[ warn   ]%s %s\n' "$c_yel"  "$c_reset" "$*" | tee -a "$LOG_FILE"; }
die()  { printf '%s[ error  ]%s %s\n' "$c_red"  "$c_reset" "$*" | tee -a "$LOG_FILE"; exit 1; }

OS="$(uname -s)"

# ---------------------------------------------------- teardown on terminate --
# When the script ends for ANY reason (Ctrl+C, kill, normal exit), stop the stack.
cleanup() {
  [ "$CLEANED_UP" -eq 1 ] && return
  CLEANED_UP=1
  echo ""
  warn "Termination requested — stopping containers (docker compose down)..."
  # Kill the health watcher if still alive.
  [ -n "$WATCHER_PID" ] && kill "$WATCHER_PID" >/dev/null 2>&1 || true
  docker compose down --remove-orphans 2>&1 | tee -a "$LOG_FILE" || true
  ok "Stack stopped. Goodbye, sir."
}
trap cleanup INT TERM EXIT

# --------------------------------------------------------------- arg parse ---
for arg in "$@"; do
  case "$arg" in
    --no-open) OPEN_BROWSER=0 ;;
    --down)    log "Tearing stack down..."; trap - EXIT; docker compose down --remove-orphans; exit 0 ;;
    -h|--help) trap - EXIT; grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) warn "Unknown argument: $arg" ;;
  esac
done

: > "$LOG_FILE"
log "Debug launch started at $(date). Logging to run_debug.log"
log "Detected OS: $OS | Ingress port: $INGRESS_PORT"

# ------------------------------------------------- 1) force-install: brew ----
ensure_homebrew() {
  if command -v brew >/dev/null 2>&1; then ok "Homebrew present."; return; fi
  if [ "$OS" = "Darwin" ]; then
    warn "Homebrew missing — installing (non-interactive)..."
    NONINTERACTIVE=1 /bin/bash -c \
      "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
      >>"$LOG_FILE" 2>&1 || die "Homebrew install failed. See run_debug.log"
    [ -x /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
    [ -x /usr/local/bin/brew ]    && eval "$(/usr/local/bin/brew shellenv)"
    ok "Homebrew installed."
  fi
}

# ------------------------------------------------- 1) force-install: docker --
ensure_docker() {
  if command -v docker >/dev/null 2>&1; then ok "Docker CLI present ($(docker --version))."; return; fi
  warn "Docker not found — force installing..."
  case "$OS" in
    Darwin)
      ensure_homebrew
      brew install --cask docker >>"$LOG_FILE" 2>&1 || die "Docker Desktop install failed."
      ok "Docker Desktop installed."
      ;;
    Linux)
      curl -fsSL https://get.docker.com | sudo sh >>"$LOG_FILE" 2>&1 || die "Docker Engine install failed."
      sudo usermod -aG docker "$USER" 2>/dev/null || true
      ok "Docker Engine installed (re-login may be needed for group membership)."
      ;;
    *) die "Unsupported OS: $OS. Please install Docker manually." ;;
  esac
}

# ------------------------------------------------- 1) verify compose plugin --
ensure_compose() {
  if docker compose version >/dev/null 2>&1; then
    ok "Docker Compose present ($(docker compose version --short 2>/dev/null))."
  else
    warn "Docker Compose plugin missing."
    if [ "$OS" = "Linux" ]; then
      sudo apt-get update -y >>"$LOG_FILE" 2>&1 || true
      sudo apt-get install -y docker-compose-plugin >>"$LOG_FILE" 2>&1 \
        || die "Could not install docker-compose-plugin."
    fi
    docker compose version >/dev/null 2>&1 || die "Docker Compose still unavailable."
    ok "Docker Compose installed."
  fi
}

# ------------------------------------------ 2) start docker daemon -----------
ensure_daemon() {
  if docker info >/dev/null 2>&1; then ok "Docker daemon already running."; return; fi
  log "Starting Docker daemon..."
  case "$OS" in
    Darwin) open -a Docker ;;
    Linux)  sudo systemctl start docker 2>>"$LOG_FILE" || sudo service docker start 2>>"$LOG_FILE" || true ;;
  esac
  log "Waiting for the daemon to become ready..."
  for i in $(seq 1 90); do
    if docker info >/dev/null 2>&1; then ok "Docker daemon ready (after ~$((i*2))s)."; sleep 5; return; fi
    sleep 2
  done
  die "Docker daemon did not become ready in time. See run_debug.log"
}

# ------------------------------------------------------ 3) prepare secrets ---
ensure_env() {
  if [ ! -f .env ]; then cp .env.example .env; ok "Created .env from .env.example."
  else ok ".env already present."; fi
}

# ------------------------------- 4a) build + pull (debug/plain progress) -----
build_pull() {
  log "Pulling service images (debug/plain progress)..."
  docker compose pull --ignore-buildable 2>&1 | tee -a "$LOG_FILE" || warn "Some images build locally."
  log "Building local images (fastapi, nginx)..."
  docker compose --progress=plain build 2>&1 | tee -a "$LOG_FILE" || die "Build failed. See run_debug.log"
  ok "Images ready."
}

# --------------------------- 5) background watcher: wait healthy -> open UI ---
health_watcher() {
  local services total start now elapsed
  services="$(docker compose config --services)"
  total="$(printf '%s\n' "$services" | grep -c . || echo 0)"
  start="$(date +%s)"
  while true; do
    local healthy=0 state health cid
    for svc in $services; do
      cid="$(docker compose ps -q "$svc" 2>/dev/null || true)"
      [ -z "$cid" ] && continue
      state="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || echo unknown)"
      health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo none)"
      if [ "$health" = "healthy" ] || { [ "$health" = "none" ] && [ "$state" = "running" ]; }; then
        healthy=$((healthy+1))
      fi
    done
    now="$(date +%s)"; elapsed=$((now-start))
    if [ "$healthy" -eq "$total" ] && [ "$total" -gt 0 ]; then
      ok "All $total services healthy (after ${elapsed}s)."
      # Ensure the embedding model is present (idempotent; fast no-op if already
      # pulled by the ollama-init service). Read OLLAMA_MODEL from .env if set.
      local ollama_model
      ollama_model="$(grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2 || true)"
      ollama_model="${ollama_model:-nomic-embed-text}"
      log "Ensuring embedding model '$ollama_model' is pulled..."
      docker compose exec -T ollama ollama pull "$ollama_model" 2>&1 | tee -a "$LOG_FILE" \
        && ok "Embedding model '$ollama_model' ready." \
        || warn "Could not confirm embedding model '$ollama_model'; check 'docker compose logs ollama-init'."
      if [ "$OPEN_BROWSER" -eq 1 ]; then
        log "Opening frontend at $FRONTEND_URL ..."
        case "$OS" in
          Darwin) open "$FRONTEND_URL" 2>/dev/null || true ;;
          Linux)  xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true ;;
        esac
        ok "Frontend opened: $FRONTEND_URL  (phpMyAdmin at $FRONTEND_URL/mysql)"
      fi
      return 0
    fi
    [ "$elapsed" -ge "$HEALTH_TIMEOUT" ] && { warn "Not all services healthy within ${HEALTH_TIMEOUT}s; check 'docker compose ps'."; return 1; }
    sleep 4
  done
}

# -------------------------------------------------------------------- main ---
ensure_docker
ensure_compose
ensure_daemon
ensure_env
build_pull

# Launch the health watcher in the background; it opens the browser when ready.
health_watcher &
WATCHER_PID=$!

log "Starting the stack in the FOREGROUND (debug, NOT hidden). Press Ctrl+C to STOP all containers."
log "-----------------------------------------------------------------------------------------------"
# Foreground, attached: streams all container logs. On Ctrl+C, compose stops the
# containers and the EXIT/INT trap runs `docker compose down` to fully clean up.
docker compose up --no-build
# If `up` returns on its own (e.g. all containers exited), the EXIT trap handles teardown.
