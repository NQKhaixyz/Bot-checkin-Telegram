#!/bin/bash

# Telegram Check-in Bot - Watchdog Script
# This script checks if bot is running and restarts it if not
# Used by cron to ensure bot stays alive

BOT_DIR="/root/Bot-checkin-Telegram"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/bot.log"
VENV_PYTHON="$BOT_DIR/venv/bin/python"

cd "$BOT_DIR"

# Function to start bot
start_bot() {
    echo "[$(date)] Starting bot..." >> "$LOG_FILE"
    nohup "$VENV_PYTHON" -m src.main >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "[$(date)] Bot started with PID $!" >> "$LOG_FILE"
}

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "[$(date)] Watchdog: No PID file found, starting bot..." >> "$LOG_FILE"
    start_bot
    exit 0
fi

# Check if process is running
PID=$(cat "$PID_FILE")
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "[$(date)] Watchdog: Bot (PID $PID) not running, restarting..." >> "$LOG_FILE"
    rm -f "$PID_FILE"
    start_bot
fi
