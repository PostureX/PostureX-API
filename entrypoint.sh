#!/bin/bash
set -e

cd /app

# Initialize the venv if it doesn't exist
uv venv --python 3.12

# Set path
PATH="/app/.venv/bin:$PATH"

# Activate environment
. .venv/bin/activate

# Install Python dependencies using uv (fast pip alternative)
uv pip install -r requirements.txt --no-cache-dir

# Initialize the database only if migrations directory does not exist
if [ ! -d "migrations" ]; then
    flask db init
    flask create-schema
    flask db migrate -m "init table"
    flask db upgrade
fi

# Start app and bot
python app.py & python bot.py