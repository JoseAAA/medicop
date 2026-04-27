#!/usr/bin/env bash
set -euo pipefail

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     MediCop — Instalación              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"

# 1. Verificar Docker
echo -e "\n${YELLOW}[1/5] Verificando Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker no está instalado. Instálalo desde https://docs.docker.com/get-docker/${NC}"
    exit 1
fi
if ! docker info &> /dev/null; then
    echo -e "${RED}✗ Docker no está corriendo. Inicia Docker Desktop primero.${NC}"
    exit 1
fi
if ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Docker Compose v2 no disponible.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker + Compose v2 OK${NC}"

# 2. Verificar openssl (para generar claves)
echo -e "\n${YELLOW}[2/5] Verificando openssl...${NC}"
if ! command -v openssl &> /dev/null; then
    echo -e "${RED}✗ openssl no encontrado — necesario para generar claves seguras.${NC}"
    echo -e "${YELLOW}  En Windows: viene con Git Bash. En Linux/Mac: ya está instalado.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ openssl OK${NC}"

# 3. Generar .env con claves aleatorias seguras
echo -e "\n${YELLOW}[3/5] Configurando archivo .env...${NC}"
if [ -f .env ]; then
    echo -e "${GREEN}✓ .env ya existe — se respeta${NC}"
    echo -e "${YELLOW}  (Para regenerar desde cero: rm .env && make install)${NC}"
else
    POSTGRES_PWD=$(openssl rand -hex 16)
    SECRET=$(openssl rand -hex 64)
    ENC_KEY=$(openssl rand -hex 16)

    sed -e "s|CHANGE_ME_strong_password_here|${POSTGRES_PWD}|g" \
        -e "s|CHANGE_ME_generate_with_secrets_token_hex_64|${SECRET}|g" \
        -e "s|CHANGE_ME_exactly_32_bytes_for_aes!|${ENC_KEY}|g" \
        -e "s|postgresql+asyncpg://medicop:CHANGE_ME@|postgresql+asyncpg://medicop:${POSTGRES_PWD}@|g" \
        .env.example > .env
    echo -e "${GREEN}✓ .env generado con claves aleatorias (POSTGRES_PASSWORD, SECRET_KEY, ENCRYPTION_KEY)${NC}"
fi

# 4. Construir imágenes y levantar servicios
echo -e "\n${YELLOW}[4/5] Construyendo y levantando servicios (puede tardar 2-5 min la primera vez)...${NC}"
docker compose up -d --build

echo -e "\n   Esperando healthchecks (puede tardar 3-5 min en el primer build mientras se descargan modelos)..."
SERVICES=("medicop-postgres" "medicop-redis" "medicop-qdrant" "medicop-ollama" "medicop-backend" "medicop-frontend")
MAX_WAIT=360

for SERVICE in "${SERVICES[@]}"; do
    printf "   %-22s " "$SERVICE"
    ELAPSED=0
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$SERVICE" 2>/dev/null || echo "none")
        if [ "$STATUS" = "healthy" ]; then
            echo -e "${GREEN}✓${NC}"
            break
        elif [ "$STATUS" = "unhealthy" ]; then
            echo -e "${RED}✗ unhealthy${NC} (logs: docker compose logs $SERVICE)"
            break
        fi
        sleep 5
        ELAPSED=$((ELAPSED + 5))
    done
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo -e "${YELLOW}⚠ timeout — sigue inicializando${NC}"
    fi
done

# 5. Final
echo -e "\n${YELLOW}[5/5] Instalación completada${NC}"
echo -e "\n${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   MediCop está corriendo                ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Frontend:  http://localhost:3000       ║${NC}"
echo -e "${GREEN}║  Salud:     http://localhost:8000/health║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Siguiente paso — descargar el modelo:  ║${NC}"
echo -e "${GREEN}║    make pull-models                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
