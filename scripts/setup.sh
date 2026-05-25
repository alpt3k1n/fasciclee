#!/usr/bin/env bash
# First-time VPS setup script
# Kullanım: bash scripts/setup.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Fasikül Üretici — İlk Kurulum"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. .env check
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo ""
  echo "  .env oluşturuldu. Devam etmeden önce düzenle:"
  echo "  → PG_PASSWORD, REDIS_PASSWORD, MINIO_PASSWORD"
  echo "  → DEEPSEEK_API_KEY, GROQ_API_KEY"
  echo "  → DOMAIN (örn: fasikul.example.com)"
  echo "  → TAILSCALE_IP (GPU worker için, opsiyonel)"
  echo ""
  echo "  Düzenledikten sonra tekrar çalıştır: bash scripts/setup.sh"
  exit 1
fi

# 2. Frontend build
echo "[1/4] Frontend build..."
cd frontend
npm ci --prefer-offline
npm run build
cd ..
echo "      → frontend/dist hazır"

# 3. Start Docker stack
echo "[2/4] Docker stack başlatılıyor..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Wait for postgres
echo "[3/4] Servisler hazırlanıyor..."
PG_USER=$(grep "^PG_USER=" .env | cut -d= -f2)
timeout 60 bash -c "until docker compose exec postgres pg_isready -U $PG_USER &>/dev/null; do sleep 3; done"
echo "      → Postgres hazır"
sleep 5

# 5. Run migrations
echo "[4/4] Veritabanı migration..."
docker compose exec api alembic upgrade head
echo "      → Migration tamamlandı"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Kurulum tamamlandı!"
DOMAIN=$(grep "^DOMAIN=" .env | cut -d= -f2)
echo "  Uygulama: https://$DOMAIN"
echo ""
echo "  GPU Worker (PC'de çalıştır):"
echo "  bash scripts/start_gpu_worker.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
