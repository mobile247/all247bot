#!/usr/bin/env bash
# Local development setup for all247
# Sets up Python virtual environment and installs dependencies.
#
# Usage: ./scripts/setup.sh

set -euo pipefail

START_TIME=$(date +%s)

echo "=== all247 Setup ==="
echo "Setting up Python virtual environment..."

python3 -m venv env
source env/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies..."
pip install -r requirements.txt

# Create local data directory for SQLite
mkdir -p data

echo ""
echo "Setup complete!"
echo "Next steps:"
echo "  1. Copy env template:  cp .env.example .env"
echo "  2. Edit credentials:   nano .env  # set TELEGRAM_BOT_TOKEN"
echo "  3. Activate env:       source env/bin/activate"
echo "  4. Run the bot:        python -m bot.main"
echo "  5. Run tests:          python -m pytest tests/"
echo ""

END_TIME=$(date +%s)
echo "Time elapsed: $((END_TIME - START_TIME))s"
