#!/bin/bash
set -e

cd /app

# Initialize the venv
uv venv --python 3.12

# Set path
PATH="/app/.venv/bin:$PATH"

# Activate environment
. .venv/bin/activate

# Install Python dependencies using uv (fast pip alternative)
uv pip install -r requirements.txt --no-cache-dir

# Remove previous migrations
rm -rf migrations

# Initialize the database
flask db init
flask create-schema
flask db migrate -m "init table"
flask db upgrade

# Start app and bot
python app.py & python bot.py