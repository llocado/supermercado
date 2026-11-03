# Riesgos conocidos y cuándo se cierran

Este proyecto es de portafolio y **no está desplegado**: corre en una máquina local, con puertos ligados a `127.0.0.1` y credenciales de
desarrollo. Aquí está, sin maquillar, lo que se resolvió y lo que queda pendiente antes de un despliegue real. Cada pendiente tiene su
"cuándo" (el momento natural para cerrarlo) y su "cómo".

## Lo que ya está resuelto

| Tema | Qué se hizo |
|---|---|
| Exposición de red | Todos los puertos de Docker (Postgres, RabbitMQ, Keycloak) publicados solo en `127.0.0.1`. |
| Dependencias vulnerables | Tomcat, Jackson, Netty, amqp-client y log4j parcheados; reescaneo con OSV sin avisos al cerrar la revisión. |
| Logging | SLF4J con `clave=valor`; nunca tokens, `Authorization`, contraseñas ni payloads completos; saltos de línea neutralizados (anti falsificación de logs); `X-Request-Id` con formato estricto. Una dependencia caída da **una línea** de WARN, no una avalancha de trazas. |
| Entrada hostil | Topes en cantidades, importes y largo de textos; UUID inválidos → 400 (no 500); mensajes de eventos con payload inválido → DLQ sin reintentos. |
| Mensajería | Reintentos acotados (1 + 3) y luego DLQ; *outbox* transaccional; idempotencia por `eventId`; `mandatory` y confirmaciones del publicador. |
| Concurrencia | Bloqueo optimista (`@Version`) en carrito y productos; claves únicas e idempotencia para eventos y checkouts repetidos. |
| Front | Login por redirección con **PKCE**; token solo en memoria (nada en `localStorage`, `sessionStorage` ni cookies); sin `dangerouslySetInnerHTML`; datos de la red validados con *type guards*; URL acotada. |
| CORS | Origen explícito (`http://localhost:5173`), nunca `*`, sin cookies; carrito abre lectura/escritura, pedidos y catálogo solo lectura. |
| Cliente Keycloak de la tienda | `redirectUris` y `webOrigins` acotados al origen del front; PKCE `S256` exigido. |
| Calidad | Cobertura (JaCoCo), tests de mutación (PIT) y análisis estático (SonarQube) en el flujo de trabajo; pruebas de fallo con servicios reales (dependencia caída, mensaje venenoso, concurrencia, entrada hostil). |

## Lo que queda pendiente

| Riesgo | Cuándo se cierra | Cómo |
|---|---|---|
| **El catálogo no exige autenticación**: cualquiera que alcance `app-productos` puede crear, editar o borrar productos. | Al construir un API Gateway o antes de exponerlo fuera de `localhost`. | Validar JWT y exigir rol `admin` para escribir; la lectura puede seguir pública. |
| **Keycloak de desarrollo**: sin HTTPS (`sslRequired: none`), registro abierto, sin protección contra fuerza bruta, usuarios de prueba y credenciales de administrador por defecto en el repo. | Antes de cualquier despliegue. | `sslRequired: external`, registro desactivado o con aprobación, `bruteForceProtected`, sin usuarios de prueba, credenciales por variables de entorno. |
| **`directAccessGrants` activo** en el cliente de la tienda (lo usan Bruno y curl para pedir tokens). | Al preparar producción. | Un cliente aparte solo para pruebas y apagarlo en el de la tienda. |
| **Credenciales de desarrollo por defecto** en `application.yml` y `docker-compose.yml`. | Junto con el despliegue real. | Quitar los valores por defecto (que falle si falta la variable) y usar secretos del entorno. |
| **Sin rate limiting**. | Con el API Gateway. | Limitar tasa por usuario/IP. |
| **Tablas que crecen sin límite** (`eventos_procesados`, `eventos_salida`) en los cuatro servicios. | Antes de operar con volumen real. | Tarea programada por antigüedad, con un plazo mayor que la reentrega máxima de RabbitMQ. |
| **El pago es simulado** y determinista (se rechaza sobre 100.000 CLP). | Cuando se integre una pasarela real. | Adaptador hacia la pasarela y conciliación; no se almacenan datos de tarjeta. |
| **Un `pago.aprobado` falsificado** con otro `eventId` y el mismo `pagoId` descontaría el stock dos veces (la idempotencia es por `eventId`). Requiere acceso al broker. | Con permisos de RabbitMQ por servicio. | Usuarios de broker con permisos mínimos y deduplicar también por `pagoId`. |
| **En productos, 4 conflictos de versión seguidos** (solo con ingresos de stock concurrentes) llevan el mensaje a la DLQ sin descontar ni publicar el rechazo. | Con monitoreo de colas. | Vigilar la DLQ y alertar; reprocesar manualmente. |
| **No hay reserva de stock**: puede haber más carritos que unidades; si al pagar ya no alcanza, el pedido queda `SIN_STOCK`. | Si el negocio lo exige. | Reservar stock al iniciar el checkout, con expiración. |
| **Logging estructurado / observabilidad**: hoy son líneas `clave=valor`, sin trazas distribuidas ni métricas. | Al desplegar. | JSON estructurado, métricas y trazas (por ejemplo OpenTelemetry). |
| **Reescaneo periódico de dependencias y CI**. | Pronto: es barato. | GitHub Actions por servicio (tests) y un escaneo programado (OSV/Dependabot). |

## Cómo se decidió qué cerrar primero

Se priorizó lo que podía perder dinero o datos (pagos, stock, duplicados) y lo que un atacante en la red local habría explotado primero
(puertos, dependencias, logs), antes que lo que depende de un despliegue (HTTPS, gateway, secretos). Es la misma lógica de
[negocio.md](negocio.md): *un pago aprobado nunca se pierde ni se duplica*.
