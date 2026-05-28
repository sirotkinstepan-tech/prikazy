# Deploy on Yandex Cloud VM

## VM requirements

- Ubuntu 22.04 LTS
- 4 vCPU, 8 GB RAM, 50 GB disk (PostgreSQL + MinIO + Tesseract OCR worker)
- Public IPv4, security group: TCP **22**, **8001**

## One-command deploy (on the server)

```bash
curl -fsSL https://raw.githubusercontent.com/sirotkinstepan-tech/prikazy/main/scripts/deploy-on-server.sh | sudo bash
```

Or after `git clone`:

```bash
sudo PUBLIC_HOST=<your-vm-ip> bash scripts/deploy-on-server.sh
```

Optional: copy Yandex LLM keys into `/opt/prikazy/.env` (`YANDEX_API_KEY`, `YANDEX_FOLDER_ID`) and restart:

```bash
cd /opt/prikazy && docker compose -f docker-compose.prod.yml restart app worker
```

## Smoke test

```bash
API_BASE=http://<vm-ip>:8001 ./scripts/smoke-test-server.sh
```

Default users after `seed`: `admin@example.com` / `admin123`, `employee@example.com` / `employee123`.
