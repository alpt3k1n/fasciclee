#!/usr/bin/env bash
# GPU worker starter — çalıştır: bash scripts/start_gpu_worker.sh
# PC'de (RTX 2060) Tailscale üzerinden VPS Redis'e bağlanır.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$REPO_ROOT/backend"

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "ERROR: .env dosyası bulunamadı ($REPO_ROOT/.env)"
  exit 1
fi

# Load env vars
set -a
source "$REPO_ROOT/.env"
set +a

# Activate virtualenv if present
if [[ -d "$BACKEND_DIR/.venv" ]]; then
  source "$BACKEND_DIR/.venv/bin/activate"
elif command -v conda &>/dev/null && conda info --envs | grep -q fasikul; then
  conda activate fasikul
fi

cd "$BACKEND_DIR"

echo "GPU worker başlatılıyor — redis: ${REDIS_URL}"
echo "Modeller ilk çalıştırmada otomatik indirilir (Whisper large-v3 ~3GB, embedding ~1GB)"
echo ""

exec rq worker gpu_queue \
  --url "${REDIS_URL}" \
  --name "gpu-worker-$(hostname)" \
  --with-scheduler
