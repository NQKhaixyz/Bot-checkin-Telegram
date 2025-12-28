#!/bin/bash

# Telegram Check-in Bot - Start Script
# Usage: ./start_bot.sh

BOT_DIR="/root/Bot-checkin-Telegram"
VENV_PYTHON="$BOT_DIR/venv/bin/python"
PID_FILE="$BOT_DIR/bot.pid"
LOG_FILE="$BOT_DIR/bot.log"

cd "$BOT_DIR"

# Check if bot is already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Bot is already running with PID $PID"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# Start bot in background
echo "Starting Telegram Check-in Bot..."
nohup "$VENV_PYTHON" -m src.main >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# Save PID
echo $BOT_PID > "$PID_FILE"

# Wait a moment and check if bot started successfully
sleep 2
if ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "Bot started successfully!"
    echo "PID: $BOT_PID"
    echo "Log file: $LOG_FILE"
    echo ""
    echo "To check status: ./status_bot.sh"
    echo "To stop: ./stop_bot.sh"
    echo "To view logs: tail -f $LOG_FILE"
else
    echo "Failed to start bot. Check log file: $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
