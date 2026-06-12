#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_by_pid_file() {
  local name="$1"
  local pid_file="$RUN_DIR/${name}.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "[skip] $name pid file not found"
    return
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "[stop] $name (pid $pid)"
    kill "$pid" 2>/dev/null || true
    sleep 0.5
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  else
    echo "[stale] $name pid file present but process not running"
  fi

  rm -f "$pid_file"
}

stop_by_pid_file "api"
stop_by_pid_file "web"
stop_by_pid_file "streamlit_free"
stop_by_pid_file "streamlit_pro"

# Extra safety cleanup by port
for p in 5174 5173 8516 8517; do
  pids="$(lsof -t -iTCP:"$p" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "[kill-port] :$p -> $pids"
    kill -9 $pids 2>/dev/null || true
  fi
done

echo "All services stopped."
