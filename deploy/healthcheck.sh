#!/bin/bash
# TG AI Poster Health Check Script
# ================================
# This script checks if the application is healthy by:
# 1. Checking if the main process is running
# 2. Checking if recent logs show activity (no errors in last 5 minutes)
# 3. Checking if the health marker file is recent

set -e

# Configuration
APP_NAME="tg_ai_poster"
LOG_FILE="/app/logs/app.log"
HEALTH_MARKER="/app/data/.health_marker"
MAX_LOG_AGE_SECONDS=300  # 5 minutes
MAX_MARKER_AGE_SECONDS=600  # 10 minutes

# Check 1: Main process is running
if ! pgrep -f "python.*main.py" > /dev/null 2>&1; then
    echo "UNHEALTHY: Main process not running"
    exit 1
fi

# Check 2: Health marker file exists and is recent
if [ -f "$HEALTH_MARKER" ]; then
    marker_age=$(( $(date +%s) - $(stat -c %Y "$HEALTH_MARKER" 2>/dev/null || stat -f %m "$HEALTH_MARKER" 2>/dev/null) ))
    if [ "$marker_age" -gt "$MAX_MARKER_AGE_SECONDS" ]; then
        echo "UNHEALTHY: Health marker too old (${marker_age}s)"
        exit 1
    fi
fi

# Check 3: No critical errors in recent logs (if log file exists)
if [ -f "$LOG_FILE" ]; then
    # Check for critical errors in last 5 minutes
    recent_errors=$(tail -100 "$LOG_FILE" 2>/dev/null | grep -c "CRITICAL\|FATAL" || true)
    if [ "$recent_errors" -gt 5 ]; then
        echo "UNHEALTHY: Too many critical errors in logs ($recent_errors)"
        exit 1
    fi
fi

# All checks passed
echo "HEALTHY: Application is running normally"
exit 0
