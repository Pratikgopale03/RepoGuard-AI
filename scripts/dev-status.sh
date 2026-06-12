#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

check_pid() {
  local name="$1"
  local pid_file="$RUN_DIR/${name}.pid"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "[up]   $name (pid $pid)"
      return
    fi
  fi
  echo "[down] $name"
}

check_http() {
  local label="$1"
  local url="$2"
  local code
  code="$(curl -sS -o /dev/null -w "%{http_code}" "$url" || true)"
  if [[ "$code" == "200" ]]; then
    echo "[ok]   $label -> $url (200)"
  else
    echo "[fail] $label -> $url ($code)"
  fi
}

echo "Process status"
check_pid "api"
check_pid "web"
check_pid "streamlit_free"
check_pid "streamlit_pro"

echo ""
echo "HTTP status"
check_http "Web" "http://localhost:5173"
check_http "API key endpoint" "http://localhost:5174/api/razorpay-key"
check_http "Free Streamlit" "http://localhost:8516"
check_http "Pro Streamlit" "http://localhost:8517"
