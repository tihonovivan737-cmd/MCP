#!/usr/bin/env bash
# Запуск бота: всё, что видно в терминале, дублируется в logs/terminal.log
# Зависимости должны быть в том же Python: pip install -r requirements.txt
# Можно задать: PYTHON=/path/to/python3 ./run_bot.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs
if [ -x ".venv/bin/python" ]; then
  PYTHON="${PYTHON:-.venv/bin/python}"
else
  PYTHON="${PYTHON:-python3}"
fi
LOCK_FILE="logs/bot.lock"
PID_FILE="logs/bot.pid"

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Бот уже запущен (pid: $OLD_PID)"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

echo $$ > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT INT TERM
exec "$PYTHON" bot.py 2>&1 | tee -a logs/terminal.log
