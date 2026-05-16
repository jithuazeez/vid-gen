# Oracle Cloud Always-Free deployment

vidplatform's API + Celery worker run in Docker on a single Oracle Cloud
Always-Free **Ampere A1 VM** (4 OCPU / 24 GB RAM, ARM64). Postgres and
Redis run as sibling containers; object storage is whichever S3-compat
service you prefer (AWS S3 free tier or OCI Object Storage with
S3-compat). GPU work runs on Modal regardless.

Cost: **$0/month** indefinitely (Always Free). Sarvam + Gemini are
pay-as-you-go; Modal uses the $30 starter credit.

---

## One-time setup

1. **Create the VM** in the OCI Console:
   - Shape: `VM.Standard.A1.Flex`, 4 OCPU / 24 GB
   - Image: Canonical Ubuntu 22.04 (ARM)
   - VCN security list: open ports 22, 80, 443
   - SSH key: upload your public key

2. **Bootstrap** (installs Docker + opens firewall + creates `/srv/vidplatform`):

   ```bash
   ssh ubuntu@$OCI_VM_PUBLIC_IP 'bash -s' < infra/oracle/bootstrap.sh
   ```

3. **Place secrets** on the VM at `/srv/vidplatform/.env` (mirror `.env.example`).
   At minimum: `POSTGRES_PASSWORD`, `GEMINI_API_KEY`, `SARVAM_API_KEY`,
   `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, `S3_*`.

4. **Issue a TLS cert** (one-time, on the VM) — replace `$DOMAIN`:

   ```bash
   sudo apt-get install -y certbot
   sudo certbot certonly --standalone -d $DOMAIN
   ```

5. **First deploy** from your laptop:

   ```bash
   bash infra/oracle/deploy.sh
   ```

6. **Run database migrations** (once):

   ```bash
   ssh ubuntu@$OCI_VM_PUBLIC_IP \
     'cd /srv/vidplatform && docker compose -f infra/oracle/docker-compose.prod.yml run --rm api alembic upgrade head'
   ```

7. **Deploy Modal GPU workers** (from your laptop, one-time then on changes):

   ```bash
   modal deploy apps/modal_app/app.py
   ```

---

## Routine deploys

Just push code:

```bash
bash infra/oracle/deploy.sh
```

This rsyncs the repo, then runs `docker compose up -d --build` on the VM.

## Tail logs

```bash
ssh ubuntu@$OCI_VM_PUBLIC_IP \
  'cd /srv/vidplatform && docker compose -f infra/oracle/docker-compose.prod.yml logs -f --tail=200'
```

## Files in this directory

| File | Purpose |
|---|---|
| `bootstrap.sh` | One-shot install of Docker + firewall + dirs on a fresh VM |
| `deploy.sh` | rsync repo from laptop → VM, then `docker compose up -d --build` |
| `docker-compose.prod.yml` | api + worker + postgres + redis + nginx |
| `nginx.conf` | TLS + SSE-friendly reverse proxy in front of the API |
| `vidplatform.service` | systemd unit so the stack auto-starts on boot |
