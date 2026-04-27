#!/usr/bin/env bash
set -euo pipefail

echo "Descargando MedGemma 4B (Q4_K_M)..."
echo "Tamaño aproximado: ~3.3 GB. Puede tomar varios minutos."

docker compose exec ollama ollama pull medgemma:4b

echo ""
echo "Modelos disponibles en Ollama:"
docker compose exec ollama ollama list

echo ""
echo "Listo. Verificación rápida: curl http://localhost:11434/api/tags"
