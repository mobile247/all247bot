#!/bin/bash
# Deployment script for all247 to EC2
# Usage: ./scripts/deploy.sh user@ec2-host
#
# Deploys to /opt/all247 on the remote host.
# Preserves existing .env — credentials are never overwritten.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -z "$1" ]; then
    echo -e "${RED}Error: No host specified${NC}"
    echo "Usage: ./scripts/deploy.sh user@ec2-host"
    echo "Example: ./scripts/deploy.sh ubuntu@ec2-54-123-45-67.compute-1.amazonaws.com"
    exit 1
fi

SSH_HOST=$1
REMOTE_DIR="/opt/all247"

echo -e "${GREEN}Deploying all247 to $SSH_HOST${NC}"

# Build deployment package — exclude secrets, caches, and dev artifacts
echo -e "${YELLOW}Creating deployment package...${NC}"
tar -czf all247.tar.gz \
    --exclude='env' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='all247.tar.gz' \
    --exclude='.pytest_cache' \
    --exclude='*.egg-info' \
    --exclude='data' \
    bot/ migrations/ scripts/ docs/ deployment/ requirements.txt README.md .env.example

echo -e "${GREEN}Package ready: all247.tar.gz${NC}"

# Copy to remote
echo -e "${YELLOW}Copying to $SSH_HOST...${NC}"
scp all247.tar.gz $SSH_HOST:/tmp/

# Remote install
echo -e "${YELLOW}Installing on remote...${NC}"
ssh $SSH_HOST << 'ENDSSH'
set -e

# Use pyenv if available
if [ -d "$HOME/.pyenv" ]; then
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
    echo "pyenv initialized"
fi

# Stop existing service if running
echo "Stopping all247 service (if running)..."
sudo systemctl stop all247 2>/dev/null || true

# Create application directory
echo "Creating /opt/all247..."
sudo mkdir -p /opt/all247
sudo chown $USER:$USER /opt/all247

# Preserve existing .env
if [ -f /opt/all247/.env ]; then
    echo "Backing up .env..."
    cp /opt/all247/.env /tmp/all247.env.backup
fi

# Extract package
echo "Extracting package..."
cd /opt/all247
tar -xzf /tmp/all247.tar.gz
rm /tmp/all247.tar.gz

# Restore .env
if [ -f /tmp/all247.env.backup ]; then
    echo "Restoring .env..."
    mv /tmp/all247.env.backup /opt/all247/.env
fi

# Create SQLite data directory (owner-only — contains member PII)
echo "Creating data directory..."
mkdir -p /opt/all247/data
chmod 700 /opt/all247/data

# Set up Python virtual environment
echo "Setting up virtual environment..."
python --version
python -m venv env
source env/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env from template if first deploy
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "================================================"
    echo "IMPORTANT: Edit /opt/all247/.env before starting!"
    echo "  Required: TELEGRAM_BOT_TOKEN"
    echo "  Optional: DB_PATH (default: ./data/all247.db)"
    echo "================================================"
    echo ""
fi

# Install systemd service
echo "Installing systemd service..."
sudo cp deployment/all247.service /etc/systemd/system/all247.service

# Patch user/group to match current user
sudo sed -i "s|User=ubuntu|User=$USER|g" /etc/systemd/system/all247.service
sudo sed -i "s|Group=ubuntu|Group=$USER|g" /etc/systemd/system/all247.service

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload
sudo systemctl enable all247

echo ""
echo "================================================"
echo "Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Edit credentials:  nano /opt/all247/.env"
echo "2. Start the bot:     sudo systemctl start all247"
echo "3. Check status:      sudo systemctl status all247"
echo "4. Watch logs:        sudo journalctl -u all247 -f"
echo "================================================"
echo ""
ENDSSH

# Clean up local package
echo -e "${YELLOW}Cleaning up...${NC}"
rm all247.tar.gz

echo -e "${GREEN}Done!${NC}"
echo ""
echo "SSH in and start the bot:"
echo "  ssh $SSH_HOST"
echo "  nano /opt/all247/.env   # set TELEGRAM_BOT_TOKEN"
echo "  sudo systemctl start all247"
echo "  sudo journalctl -u all247 -f"
