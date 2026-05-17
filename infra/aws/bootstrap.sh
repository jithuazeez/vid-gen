#!/usr/bin/env bash
# One-time bootstrap for a fresh AWS EC2 instance running Ubuntu 22.04 LTS (x86_64).
# Run from your laptop:
#
#   ssh -i ~/.ssh/vidplatform-ec2.pem ubuntu@<EC2-IP> 'bash -s' < infra/aws/bootstrap.sh
#
# Idempotent: re-running is safe.

set -euo pipefail

DEPLOY_DIR=/srv/vidplatform

echo "▶ Updating apt + installing base packages…"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release rsync ufw \
    git build-essential

echo "▶ Installing Docker Engine (official Docker apt repo)…"
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
  echo "ℹ Docker installed. You may need to log out and back in for group membership to take effect."
fi

echo "▶ Opening UFW firewall ports 22 / 80 / 443…"
# EC2 security groups handle the outer firewall; UFW provides defence-in-depth.
sudo ufw allow OpenSSH || true
sudo ufw allow 80/tcp  || true
sudo ufw allow 443/tcp || true
sudo ufw --force enable || true

echo "▶ Preparing deploy directory $DEPLOY_DIR…"
sudo mkdir -p "$DEPLOY_DIR"/{data/postgres,data/redis}
sudo chown -R "$USER":"$USER" "$DEPLOY_DIR"

echo "▶ Installing certbot (Let's Encrypt) via snap…"
if ! command -v certbot >/dev/null; then
  sudo snap install --classic certbot
  sudo ln -sf /snap/bin/certbot /usr/bin/certbot
fi

echo "▶ Installing systemd unit…"
# The unit file is installed from the rsynced source tree.
# If deploy.sh has already run, the unit will be in the right place.
UNIT_SRC="$DEPLOY_DIR/infra/aws/vidplatform.service"
if [ -f "$UNIT_SRC" ]; then
  sudo cp "$UNIT_SRC" /etc/systemd/system/vidplatform.service
  sudo systemctl daemon-reload
  sudo systemctl enable vidplatform.service
  echo "✔ systemd unit installed and enabled."
else
  echo "ℹ vidplatform.service not found at $UNIT_SRC — run deploy.sh first, then re-run bootstrap.sh to install the unit."
fi

echo ""
echo "✔ Bootstrap complete."
echo ""
echo "Next steps:"
echo "  1. If this is the first run, log out and back in so the docker group takes effect."
echo "  2. Place your filled .env at $DEPLOY_DIR/.env"
echo "     scp -i ~/.ssh/vidplatform-ec2.pem .env ubuntu@<EC2-IP>:$DEPLOY_DIR/.env"
echo "  3. Issue a TLS certificate (before starting nginx):"
echo "     sudo certbot certonly --standalone -d your.domain.com"
echo "  4. Run the deploy script from your laptop:"
echo "     bash infra/aws/deploy.sh"
echo "  5. Run database migrations once:"
echo "     docker compose -f $DEPLOY_DIR/infra/aws/docker-compose.prod.yml run --rm api alembic upgrade head"
echo "  6. Deploy Modal GPU workers:"
echo "     modal deploy apps/modal_app/app.py"
