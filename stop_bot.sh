#!/bin/bash

# Telegram Check-in Bot - Stop Script
# Usage: ./stop_bot.sh

BOT_DIR="/root/Bot-checkin-Telegram"
PID_FILE="$BOT_DIR/bot.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Bot is not running (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping bot (PID: $PID)..."
    kill "$PID"
    sleep 2
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Force killing bot..."
        kill -9 "$PID"
    fi
    
    rm -f "$PID_FILE"
    echo "Bot stopped successfully!"
else
    echo "Bot process not found, cleaning up PID file..."
    rm -f "$PID_FILE"
fi
