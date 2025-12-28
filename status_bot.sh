#!/bin/bash

# Telegram Check-in Bot - Status Script
# Usage: ./status_bot.sh

BOT_DIR="/root/Bot-checkin-Telegram"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/bot.log"

echo "=== Telegram Check-in Bot Status ==="
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "Status: STOPPED (no PID file)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Status: RUNNING"
    echo "PID: $PID"
    echo ""
    echo "Process info:"
    ps -p "$PID" -o pid,ppid,cmd,%cpu,%mem,etime
    echo ""
    echo "=== Recent logs (last 20 lines) ==="
    tail -n 20 "$LOG_FILE"
else
    echo "Status: STOPPED (process not found)"
    rm -f "$PID_FILE"
fi
