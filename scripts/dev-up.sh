#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
VENV_PY="$ROOT_DIR/../.venv/bin/python"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/.run/logs"

mkdir -p "$RUN_DIR" "$LOG_DIR"

if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: Python venv not found at $VENV_PY"
  echo "Create it first, then install dependencies."
  exit 1
fi

start_service() {
  local name="$1"
  local cmd="$2"
  local pid_file="$RUN_DIR/${name}.pid"
  local log_file="$LOG_DIR/${name}.log"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      echo "[skip] $name already running (pid $old_pid)"
      return
    fi
    rm -f "$pid_file"
  fi

  echo "[start] $name"
  nohup bash -lc "$cmd" >"$log_file" 2>&1 &
  local new_pid=$!
  echo "$new_pid" > "$pid_file"
}

# Clean up any stale listeners before boot.
for p in 5174 5173 8516 8517; do
  pids="$(lsof -t -iTCP:"$p" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "[clean] killing existing listeners on :$p -> $pids"
    kill -9 $pids 2>/dev/null || true
  fi
done

start_service "api" "cd '$WEB_DIR' && npm run api"
start_service "web" "cd '$WEB_DIR' && npm run dev -- --host 127.0.0.1 --port 5173"
start_service "streamlit_free" "cd '$ROOT_DIR' && '$VENV_PY' -m streamlit run app_free.py --server.headless true --server.port 8516"
start_service "streamlit_pro" "cd '$ROOT_DIR' && '$VENV_PY' -m streamlit run app_pro.py --server.headless true --server.port 8517"

echo ""
echo "Started services. Check status with: ./scripts/dev-status.sh"
echo "Logs: $LOG_DIR"
