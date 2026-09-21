#!/bin/bash

echo "Launching GPTWOL..."

#Launch Cron
cron

# Launch application
# --preload: load app once so the uptime monitor thread starts in the master
# -w 1: single worker to share in-memory state (status cache, uptime tracking)
cd /app
GUNICORN_CMD_ARGS="--bind=$IP:$PORT" gunicorn --preload -w 1 --access-logfile - wol:app
