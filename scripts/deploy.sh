#!/usr/bin/env bash
# VPS deploy script — git pull → fe build → docker build → migrate
# Kullanım: bash scripts/deploy.sh [--skip-fe] [--skip-pull]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_FE=false
SKIP_PULL=false
for arg in "$@"; do
  [[ "$arg" == "--skip-fe" ]] && SKIP_FE=true
  [[ "$arg" == "--skip-pull" ]] && SKIP_PULL=true
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Fasikül Üretici — Deploy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Pull latest code
if [[ "$SKIP_PULL" == false ]]; then
  echo "[1/5] git pull..."
  git pull --ff-only
fi

# 2. Build frontend
if [[ "$SKIP_FE" == false ]]; then
  echo "[2/5] Frontend build..."
  cd frontend
  npm ci --prefer-offline
  npm run build
  cd ..
  echo "      → frontend/dist ready ($(du -sh frontend/dist | cut -f1))"
else
  echo "[2/5] Frontend build — skipped"
fi

# 3. Rebuild backend images
echo "[3/5] Docker build..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --pull api worker_vps

# 4. Restart services
echo "[4/5] docker compose up..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 5. Run migrations
echo "[5/5] Alembic migrate..."
# Wait for api container to be healthy
timeout 30 bash -c 'until docker compose exec api alembic current &>/dev/null; do sleep 2; done' || true
docker compose exec api alembic upgrade head

echo ""
echo "✓ Deploy tamamlandı!"
DOMAIN=$(grep "^DOMAIN=" .env 2>/dev/null | cut -d= -f2 || echo "")
[[ -n "$DOMAIN" ]] && echo "  https://$DOMAIN"
