#!/usr/bin/env bash
# Apaga la demo y borra sus datos (contenedores, red y volumen de Postgres). Las imágenes quedan en caché.
set -euo pipefail
cd "$(dirname "$0")"
docker compose --profile herramientas down -v --remove-orphans
echo "Demo apagada y datos borrados."
