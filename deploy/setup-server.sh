#!/bin/bash
# =====================================================
# Oracle Cloud Free Tier Server Setup Script
# =====================================================
# Run this script on a fresh Oracle Cloud ARM instance
# Ubuntu 22.04 or Oracle Linux 8+ recommended

set -e

echo "=========================================="
echo "TG AI Poster - Oracle Cloud Setup"
echo "=========================================="

# Update system
echo "[1/6] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "Docker installed. You may need to log out and back in."
else
    echo "Docker already installed."
fi

# Install Docker Compose
echo "[3/6] Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
    # Also install standalone for compatibility
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    echo "Docker Compose already installed."
fi

# Install useful tools
echo "[4/6] Installing additional tools..."
sudo apt-get install -y \
    git \
    curl \
    wget \
    htop \
    nano \
    ufw \
    fail2ban

# Configure firewall
echo "[5/6] Configuring firewall..."
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Setup fail2ban
echo "[6/6] Setting up fail2ban..."
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Create application directory
echo ""
echo "Creating application directory..."
mkdir -p ~/tg-ai-poster
cd ~/tg-ai-poster

# Create subdirectories
mkdir -p data logs sessions

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Upload your project files to ~/tg-ai-poster/"
echo "2. Create .env file with your credentials"
echo "3. Run: docker-compose -f docker-compose.simple.yml up -d"
echo ""
echo "Useful commands:"
echo "  docker logs -f tg-ai-poster    # View logs"
echo "  docker restart tg-ai-poster    # Restart container"
echo "  docker-compose down            # Stop all"
echo "  docker-compose up -d           # Start all"
echo ""
