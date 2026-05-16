#!/usr/bin/env bash
# rsync the repo to the OCI VM and restart the compose stack.
#
# Reads OCI_VM_PUBLIC_IP, OCI_SSH_USER (default ubuntu) and OCI_SSH_KEY_PATH
# from the local .env. Run from the repo root:
#
#   bash infra/oracle/deploy.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# ── Load .env ────────────────────────────────────────────────────────
if [ -f "$REPO_ROOT/.env" ]; then
  # shellcheck disable=SC1090
  set -a; source "$REPO_ROOT/.env"; set +a
fi

: "${OCI_VM_PUBLIC_IP:?Set OCI_VM_PUBLIC_IP in .env}"
SSH_USER="${OCI_SSH_USER:-ubuntu}"
SSH_KEY="${OCI_SSH_KEY_PATH:-$HOME/.ssh/oci_vidplatform}"
SSH_KEY="${SSH_KEY/#\~/$HOME}"

REMOTE_DIR="/srv/vidplatform"
COMPOSE_FILE="infra/oracle/docker-compose.prod.yml"

echo "▶ Pushing source tree to $SSH_USER@$OCI_VM_PUBLIC_IP:$REMOTE_DIR …"
rsync -az --delete \
  --exclude='.venv' --exclude='node_modules' --exclude='.next' \
  --exclude='.git'  --exclude='__pycache__' --exclude='.DS_Store' \
  --exclude='video generation platform' \
  -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new" \
  "$REPO_ROOT/" "$SSH_USER@$OCI_VM_PUBLIC_IP:$REMOTE_DIR/"

echo "▶ Building + restarting compose stack on the VM…"
ssh -i "$SSH_KEY" "$SSH_USER@$OCI_VM_PUBLIC_IP" \
  "cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE up -d --build"

echo "✔ Deploy complete. Tail logs with:"
echo "  ssh -i $SSH_KEY $SSH_USER@$OCI_VM_PUBLIC_IP 'cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE logs -f --tail=100'"
