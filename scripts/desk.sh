#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEV=0
STOP=0
FORCE_BUILD=0
NO_BUILD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev|-d) DEV=1 ;;
    --stop) STOP=1 ;;
    --build) FORCE_BUILD=1 ;;
    --no-build) NO_BUILD=1 ;;
    -h|--help)
      echo "用法: scripts/desk.sh [--dev] [--stop] [--build] [--no-build]"
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 2
      ;;
  esac
  shift
done

WEB_DIR="$ROOT/web"
ENV_FILE="$ROOT/.env"
ENV_EXAMPLE="$ROOT/.env.example"
VENV_PY="$ROOT/.venv/bin/python"
DEFAULT_PORT=8000
VITE_PORT=5173

step() { printf '==> %s\n' "$*"; }
warn() { printf '!!  %s\n' "$*" >&2; }

dotenv_get() {
  local key="$1"
  [[ -f "$ENV_FILE" ]] || return 0
  awk -F= -v k="$key" '
    $0 ~ "^[[:space:]]*#" { next }
    $1 == k { sub(/^[^=]+=/, ""); gsub(/\r$/, ""); print; exit }
  ' "$ENV_FILE"
}

listen_port() {
  local raw
  raw="$(dotenv_get OPTION_DESK_WEB_PORT || true)"
  if [[ "$raw" =~ ^[0-9]+$ ]]; then
    echo "$raw"
  else
    echo "$DEFAULT_PORT"
  fi
}

pids_on_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$port" 2>/dev/null | awk '{print $1}' || true
  else
    ss -lptn "sport = :$port" 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' || true
  fi
}

kill_pattern() {
  local pattern="$1"
  if command -v pkill >/dev/null 2>&1; then
    pkill -f "$pattern" 2>/dev/null || true
  fi
}

stop_desk() {
  local port="$1"
  step "停止已有服务（端口 $port / $VITE_PORT，以及 option_desk.web / vite）"
  kill_pattern "option_desk.web|option-desk-web"
  if [[ "$DEV" -eq 1 || "$STOP" -eq 1 ]]; then
    kill_pattern "[v]ite"
  fi
  local pid
  for pid in $(pids_on_port "$port") $(pids_on_port "$VITE_PORT"); do
    [[ -n "$pid" && "$pid" != "$$" ]] && kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 0.4
  for pid in $(pids_on_port "$port") $(pids_on_port "$VITE_PORT"); do
    [[ -n "$pid" && "$pid" != "$$" ]] && kill -KILL "$pid" 2>/dev/null || true
  done
}

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    [[ -f "$ENV_EXAMPLE" ]] || { echo "找不到 .env 或 .env.example" >&2; exit 1; }
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    warn "已复制 .env.example → .env，请补 LLM key 和口令"
  fi
  if [[ -z "$(dotenv_get OPTION_DESK_WEB_PASSWORD || true)" ]]; then
    printf '\nOPTION_DESK_WEB_PASSWORD=desk\n' >> "$ENV_FILE"
    warn "OPTION_DESK_WEB_PASSWORD 为空，已写入本机默认口令 desk（上云请改掉）"
  fi
}

ensure_python() {
  if [[ ! -x "$VENV_PY" ]]; then
    step "创建虚拟环境 .venv"
    if command -v uv >/dev/null 2>&1; then
      uv venv .venv
    else
      python3 -m venv .venv
    fi
  fi
  if ! "$VENV_PY" -c "import option_desk.web, fastapi, uvicorn" >/dev/null 2>&1; then
    step "安装 Python 依赖"
    if command -v uv >/dev/null 2>&1; then
      uv pip install -e ".[dev]" --python "$VENV_PY"
    else
      "$VENV_PY" -m pip install -e ".[dev]"
    fi
  fi
}

frontend_stale() {
  local dist="$WEB_DIR/dist/index.html"
  [[ -f "$dist" ]] || return 0
  find "$WEB_DIR/src" "$WEB_DIR/index.html" "$WEB_DIR/package.json" "$WEB_DIR/vite.config.ts" \
    -type f -newer "$dist" 2>/dev/null | grep -q .
}

ensure_frontend() {
  if [[ ! -d "$WEB_DIR/node_modules" ]]; then
    command -v npm >/dev/null 2>&1 || { echo "需要 Node.js/npm" >&2; exit 1; }
    step "npm install"
    (cd "$WEB_DIR" && npm install)
  fi
  local need=0
  if [[ "$FORCE_BUILD" -eq 1 ]]; then
    need=1
  elif [[ "$NO_BUILD" -eq 0 ]] && frontend_stale; then
    need=1
  fi
  if [[ "$NO_BUILD" -eq 1 && ! -f "$WEB_DIR/dist/index.html" ]]; then
    need=1
    warn "指定了 --no-build 但 dist 不存在，仍会构建一次"
  fi
  if [[ "$need" -eq 1 ]]; then
    step "构建前端 web/dist"
    (cd "$WEB_DIR" && npm run build)
  else
    step "前端 dist 已是最新，跳过构建"
  fi
}

PORT="$(listen_port)"
stop_desk "$PORT"
if [[ "$STOP" -eq 1 ]]; then
  echo "已停止。"
  exit 0
fi

ensure_env
ensure_python

if [[ "$DEV" -eq 1 ]]; then
  step "启动 API :$PORT 和 Vite :$VITE_PORT（Ctrl+C 停两边）"
  "$VENV_PY" -m option_desk.web &
  api_pid=$!
  cleanup() {
    kill "$api_pid" 2>/dev/null || true
    stop_desk "$PORT"
  }
  trap cleanup EXIT INT TERM
  (cd "$WEB_DIR" && npm run dev)
  exit 0
fi

ensure_frontend

PASSWORD="$(dotenv_get OPTION_DESK_WEB_PASSWORD || true)"
printf '\n本机决策台: http://127.0.0.1:%s\n' "$PORT"
[[ -n "$PASSWORD" ]] && printf '登录口令:   %s\n' "$PASSWORD"
echo "Ctrl+C 停止。再执行本脚本即重启。"
echo
exec "$VENV_PY" -m option_desk.web
