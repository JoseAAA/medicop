#!/usr/bin/env bash
set -euo pipefail

echo "Cargando datos de demostración (médico demo + 6 pacientes peruanos + guías)..."
docker compose exec -T backend python -m app.db.seed

echo ""
echo "Listo. Credenciales del médico demo:"
echo "  email:    demo@medicop.pe"
echo "  password: Demo1234!"
