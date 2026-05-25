#!/bin/bash
# First-time VPS setup script
set -e

echo "=== Fasikül Üretici Setup ==="

# Copy env file
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — edit it before continuing!"
  exit 1
fi

# Create MinIO bucket (runs after stack is up)
echo "Starting stack..."
docker compose up -d

echo "Waiting for services..."
sleep 15

# Run migrations
docker compose exec api alembic upgrade head

echo "Done! Visit https://$(grep DOMAIN .env | cut -d= -f2)"
