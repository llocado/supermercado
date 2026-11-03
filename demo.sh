#!/usr/bin/env bash
# Levanta la demo completa: infraestructura, los cuatro servicios y la tienda. Solo necesita Docker.
# Uso: ./demo.sh        (la primera vez compila todo desde GitHub: tarda varios minutos)
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "Falta Docker: https://docs.docker.com/get-docker/"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker no está corriendo: ábrelo y vuelve a ejecutar ./demo.sh"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Falta 'docker compose' (Docker Compose v2)"; exit 1; }

# Compilar los cuatro servicios a la vez agota la memoria de una máquina normal: de dos en dos.
export COMPOSE_PARALLEL_LIMIT=2

echo "==> 1/3 Construyendo y arrancando (la primera vez tarda varios minutos)…"
docker compose up -d --build

echo "==> 2/3 Esperando a que los servicios estén sanos…"
for intento in $(seq 1 90); do
  pendientes=$(docker compose ps --format '{{.Name}} {{.Health}}' | grep -v ' healthy$' | grep -v 'web-' || true)
  [ -z "$pendientes" ] && break
  sleep 4
done
[ -z "${pendientes:-}" ] || { echo "Aún no están sanos:"; echo "$pendientes"; echo "Mira los registros con: docker compose logs <servicio>"; exit 1; }

# Regla de arranque: los productores publican con "mandatory", así que hay que esperar a que existan TODAS las colas
# de consumo antes de generar tráfico (si no, un evento puede perderse). Ver docs/flujo-completo.md.
echo "==> 3/3 Esperando las colas de RabbitMQ…"
colas="carrito.pago-aprobado pagos.pedido-creado pedidos.carrito-checkout-iniciado pedidos.pago-aprobado pedidos.pago-rechazado pedidos.stock-descuento-rechazado productos.pago-aprobado"
for intento in $(seq 1 60); do
  listado=$(docker compose exec -T rabbitmq rabbitmqctl list_queues name consumers --quiet 2>/dev/null || true)
  faltan=""
  for cola in $colas; do
    echo "$listado" | grep -Eq "^$cola[[:space:]]+[1-9]" || faltan="$faltan $cola"
  done
  [ -z "$faltan" ] && break
  sleep 3
done
[ -z "$faltan" ] || { echo "Faltan colas con consumidor:$faltan"; exit 1; }

docker compose run --rm cargador

cat <<'T'

Listo. Abre la tienda:  http://localhost:5173

  Usuario de prueba:  cliente1   /   clave: cliente1      (es solo de la demo)
  Prueba esto:        agrega productos al carrito, entra a "Carrito", pulsa "Pagar"
                      y mira cómo el pedido pasa a "Pagado" (los eventos viajan por RabbitMQ).
  Un pago de más de 100.000 CLP se rechaza a propósito: el pedido queda "Creado".

  RabbitMQ (ver las colas):  http://localhost:15672   (supermercado / supermercado)
  Para apagar todo:          ./demo-down.sh
T
