#!/usr/bin/env bash
# rsync the repo to the EC2 instance and restart the compose stack.
#
# Reads EC2_HOST, EC2_USER (default ubuntu), and EC2_SSH_KEY_PATH from the
# local .env. Run from the repo root:
#
#   bash infra/aws/deploy.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# ── Load .env ────────────────────────────────────────────────────────────
if [ -f "$REPO_ROOT/.env" ]; then
  # shellcheck disable=SC1090
  set -a; source "$REPO_ROOT/.env"; set +a
fi

: "${EC2_HOST:?Set EC2_HOST in .env (EC2 public IP or domain)}"
SSH_USER="${EC2_USER:-ubuntu}"
SSH_KEY="${EC2_SSH_KEY_PATH:-$HOME/.ssh/vidplatform-ec2.pem}"
SSH_KEY="${SSH_KEY/#\~/$HOME}"

REMOTE_DIR="/srv/vidplatform"
COMPOSE_FILE="infra/aws/docker-compose.prod.yml"

echo "▶ Pushing source tree to $SSH_USER@$EC2_HOST:$REMOTE_DIR …"
rsync -az --delete \
  --exclude='.venv' --exclude='node_modules' --exclude='.next' \
  --exclude='.git'  --exclude='__pycache__' --exclude='.DS_Store' \
  --exclude='*.pyc' --exclude='*.pyo' \
  -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new" \
  "$REPO_ROOT/" "$SSH_USER@$EC2_HOST:$REMOTE_DIR/"

echo "▶ Building + restarting compose stack on the EC2 instance…"
ssh -i "$SSH_KEY" "$SSH_USER@$EC2_HOST" \
  "cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE up -d --build"

echo ""
echo "✔ Deploy complete."
echo ""
echo "Tail logs:"
echo "  ssh -i $SSH_KEY $SSH_USER@$EC2_HOST 'cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE logs -f --tail=100'"
echo ""
echo "Run DB migrations (if schema changed):"
echo "  ssh -i $SSH_KEY $SSH_USER@$EC2_HOST 'cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE run --rm api alembic upgrade head'"
echo ""
echo "Deploy Modal workers (if apps/modal_app/ changed):"
echo "  modal deploy apps/modal_app/app.py"
