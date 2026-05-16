#!/usr/bin/env bash
# One-shot bootstrap for a fresh Oracle Cloud Always-Free Ampere A1 VM
# (Ubuntu 22.04 ARM64). Run as the default `ubuntu` user with sudo:
#
#   ssh ubuntu@$OCI_VM_PUBLIC_IP 'bash -s' < infra/oracle/bootstrap.sh
#
# Idempotent: re-running is safe.

set -euo pipefail

DEPLOY_DIR=/srv/vidplatform

echo "▶ Updating apt + installing base packages…"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release rsync ufw \
    git build-essential

echo "▶ Installing Docker Engine…"
if ! command -v docker >/dev/null; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
       https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
                          docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
fi

echo "▶ Opening firewall ports 80/443 (OCI VCN security list must also allow these)…"
sudo ufw allow OpenSSH || true
sudo ufw allow 80/tcp  || true
sudo ufw allow 443/tcp || true
sudo ufw --force enable || true

echo "▶ Preparing deploy directory $DEPLOY_DIR…"
sudo mkdir -p "$DEPLOY_DIR"/{data/postgres,data/redis}
sudo chown -R "$USER":"$USER" "$DEPLOY_DIR"

echo "▶ Installing systemd unit…"
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" &> /dev/null && pwd)"
if [ -f "$SCRIPT_DIR/vidplatform.service" ]; then
  sudo cp "$SCRIPT_DIR/vidplatform.service" /etc/systemd/system/vidplatform.service
  sudo systemctl daemon-reload
  sudo systemctl enable vidplatform.service
fi

echo "✔ Bootstrap complete."
echo "Next steps:"
echo "  1. Place your filled .env at $DEPLOY_DIR/.env"
echo "  2. Run infra/oracle/deploy.sh from your laptop to rsync the source."
echo "  3. ssh in and run: cd $DEPLOY_DIR && docker compose -f infra/oracle/docker-compose.prod.yml up -d --build"
echo "  4. Run alembic migrations once: docker compose ... run --rm api alembic upgrade head"
