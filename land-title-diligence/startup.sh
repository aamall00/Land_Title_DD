#!/usr/bin/env bash
# startup.sh — Start BhumiCheck frontend and backend together
# Usage: bash startup.sh

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${BOLD}[startup]${RESET} $*"; }
ok()   { echo -e "${GREEN}✔${RESET}  $*"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $*"; }
err()  { echo -e "${RED}✖${RESET}  $*"; }

# ── Cleanup on exit ───────────────────────────────────────────────────────────
PIDS=()
cleanup() {
  echo ""
  log "Shutting down..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  log "Done."
}
trap cleanup EXIT INT TERM

# ── Check .env files ──────────────────────────────────────────────────────────
check_env() {
  local dir="$1" file="$dir/.env" example="$dir/.env.example"
  if [[ ! -f "$file" ]]; then
    if [[ -f "$example" ]]; then
      warn "$file not found — copying from .env.example"
      cp "$example" "$file"
      warn "Please edit $file and fill in your credentials, then re-run."
      MISSING_ENV=1
    else
      err "$file not found and no .env.example to copy from."
      MISSING_ENV=1
    fi
  fi
}

MISSING_ENV=0
check_env "$BACKEND"
check_env "$FRONTEND"
if [[ "$MISSING_ENV" -eq 1 ]]; then
  err "Fix missing .env files above, then re-run."
  exit 1
fi

# ── Backend setup ─────────────────────────────────────────────────────────────
log "Setting up backend..."

VENV="$BACKEND/.venv"
if [[ ! -d "$VENV" ]]; then
  log "Creating Python virtual environment..."
  python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

log "Installing/updating Python dependencies..."
pip install -q --upgrade pip
pip install -q -r "$BACKEND/requirements.txt"
ok "Backend dependencies ready"

# ── Frontend setup ────────────────────────────────────────────────────────────
log "Setting up frontend..."

if ! command -v node &>/dev/null; then
  err "Node.js not found. Install from https://nodejs.org"
  exit 1
fi

if [[ ! -d "$FRONTEND/node_modules" ]]; then
  log "Installing npm packages..."
  npm --prefix "$FRONTEND" install
fi
ok "Frontend dependencies ready"

# ── Launch backend ────────────────────────────────────────────────────────────
log "Starting FastAPI backend on ${CYAN}http://localhost:8000${RESET} ..."
(
  source "$VENV/bin/activate"
  cd "$BACKEND"
  uvicorn app.main:app --reload --port 8000 2>&1 | sed "s/^/${CYAN}[backend]${RESET} /"
) &
PIDS+=($!)

# Give the backend a moment to start before printing the frontend URL
sleep 2

# ── Launch frontend ───────────────────────────────────────────────────────────
log "Starting Vite frontend on ${CYAN}http://localhost:5173${RESET} ..."
(
  cd "$FRONTEND"
  npm run dev 2>&1 | sed "s/^/${GREEN}[frontend]${RESET} /"
) &
PIDS+=($!)

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  ${BOLD}BhumiCheck is starting up${RESET}"
echo -e "  Frontend  →  ${CYAN}http://localhost:5173${RESET}"
echo -e "  Backend   →  ${CYAN}http://localhost:8000${RESET}"
echo -e "  API docs  →  ${CYAN}http://localhost:8000/docs${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop both servers"
echo ""

# ── Wait for both processes ───────────────────────────────────────────────────
wait
