#!/usr/bin/env bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check() {
    local name=$1
    local url=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ $name${NC} ($url)"
    else
        echo -e "${RED}✗ $name${NC} ($url)"
    fi
}

echo "=== MediCop Healthcheck ==="
check "Frontend"   "http://localhost:3000"
check "Backend"    "http://localhost:8000/health"
check "API Docs"   "http://localhost:8000/docs"
check "Qdrant"     "http://localhost:6333/readyz"
check "Ollama"     "http://localhost:11434/api/tags"

echo ""
echo "=== Estado Docker Compose ==="
docker compose ps
