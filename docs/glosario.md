# Glosario: los conceptos que se repiten en todos los servicios

Si entiendes esta página, entiendes el 80 % de cualquier archivo del proyecto. Cada término trae una analogía y dónde verlo.

## Arquitectura hexagonal (la forma de las carpetas)

Piensa en una **casa con enchufes**. El interior (las reglas del negocio) no sabe de qué marca es la lámpara: solo exige que haya un enchufe estándar. Cada servicio se organiza así:

```
domain/            ← el negocio puro: qué es un Carrito/Pedido/Pago y qué reglas cumple. Sin Spring, sin BD.
application/       ← lo que el servicio SABE HACER (casos de uso) + los enchufes (puertos).
infrastructure/    ← las lámparas: HTTP, Postgres, RabbitMQ, Keycloak. Se pueden cambiar sin tocar el centro.
```

| Término | Qué es | Analogía | Ejemplo |
|---|---|---|---|
| **Modelo de dominio / agregado** | La clase con las reglas del negocio y su propio estado. No se modifica "desde afuera": tiene métodos. | El *reglamento* con vida propia | `Carrito`, `Pedido`, `Pago` |
| **Objeto de valor** | Clase pequeña, inmutable, que se **valida al construirse**. | Un billete: o es válido o no existe | `Sku`, `Precio`, `Stock`, `ItemCarrito`, `ProductoId` |
| **Puerto** (`...Port`) | Una **interfaz** que dice "necesito poder hacer X", sin decir cómo. Vive en `application/port`. | El enchufe estándar | `CarritoRepositoryPort`, `PedidoEventPublisherPort` |
| **Adaptador** (`...Adapter`, `...Client`) | La clase que **implementa** un puerto con una tecnología concreta. Vive en `infrastructure`. | La lámpara que se enchufa | `CarritoPersistenceAdapter` (JPA), `ProductosServiceClient` (HTTP), `CheckoutEventPublisherAdapter` (RabbitMQ) |
| **Caso de uso** (`...UseCase`) | Una acción del negocio, de principio a fin ("agregar un ítem", "marcar pedido pagado"). Orquesta dominio + puertos. Método `execute`. | Un *procedimiento* escrito en un manual | `AgregarItemAlCarritoUseCase` |
| **Controlador** (`...Controller`) | Adaptador de **entrada** HTTP: traduce una petición a un caso de uso. Sin lógica de negocio. | El mostrador de atención | `CarritoController` |
| **Listener** | Adaptador de **entrada** de eventos: traduce un mensaje de RabbitMQ a un caso de uso. | El buzón que alguien vacía | `PagoEventListener` |
| **Entidad** (`...Entity`) | La clase que representa **una fila** de la tabla (JPA). Es de infraestructura, no del dominio. | La ficha de papel del archivo | `CarritoEntity` |
| **Mapper** | Convierte entre dos representaciones (dominio ⇄ entidad, dominio ⇄ DTO). | Un traductor | `CarritoEntityMapper`, `PedidoDtoMapper` |
| **Repositorio Spring Data** | Interfaz que Spring implementa sola para leer/escribir una entidad. | El archivador con cajones ya hechos | `SpringDataCarritoRepository` |
| **DTO** (`...Request`, `...Response`, `...Payload`) | Un "formulario": los datos tal como **entran o salen** de la aplicación (HTTP o evento). No tienen reglas. | El formulario impreso | `AgregarItemRequest`, `PagoAprobadoPayload` |
| **Excepción de dominio** | Error con significado de negocio. El `GlobalExceptionHandler` la traduce a un código HTTP. | Un sello de "rechazado" | `CarritoVacioException` → 409 |

### Por qué tanto ceremonial
Si mañana cambias Postgres por otra base, **solo** reescribes el adaptador; el caso de uso y el dominio ni se enteran, y los tests del centro siguen valiendo.

## Seguridad

| Término | Explicación |
|---|---|
| **Keycloak** | El servidor de identidad. Emite tokens. |
| **JWT** (token) | Un pase firmado que contiene quién eres (`sub`) y tus roles. Los servicios lo validan con la clave pública de Keycloak, sin llamarlo en cada petición. |
| **Resource Server** | Un servicio que **solo valida** tokens (no tiene pantalla de login). Lo configura `SecurityConfig`. |
| **Claim `sub`** | El id del usuario dentro del token. **El usuario nunca viaja en el body ni en la URL**: siempre sale de aquí, así nadie puede pedir el carrito de otro. |
| **Rol `cliente`** | Se exige en todos los endpoints de carrito, pedidos y pagos. |
| **IDOR** | Acceder al recurso de otro adivinando su id. Se evita respondiendo "no existe" cuando el recurso es de otro usuario. |

## Mensajería (RabbitMQ)

| Término | Explicación | Analogía |
|---|---|---|
| **Evento** | Un hecho ya ocurrido, en pasado: `pedido.creado`, `pago.aprobado`. | Una *carta* que dice "esto pasó" |
| **Envelope** | El sobre común de todo evento: `eventId`, `eventType`, `eventVersion`, `occurredAt`, `producer`, `correlationId`, `payload`. | El sobre con remitente y fecha |
| **Exchange** | Donde el productor deja el evento (uno por servicio: `carrito.events`, `pedidos.events`, `pagos.events`). Tipo *topic*: el *routing key* = el tipo de evento. | El buzón de correos |
| **Cola** | La bandeja propia de **un consumidor** (`pagos.pedido-creado`). Se enlaza (*binding*) al exchange. | La casilla de cada vecino |
| **DLQ** (dead-letter queue) | Cola de "cartas devueltas": lo que no se pudo procesar va aquí para no atascar la principal. | Objetos perdidos |
| **Mensaje venenoso** | Uno que nunca se podrá procesar (JSON roto, campo inválido). Va directo a la DLQ, sin reintentos. | Carta ilegible |
| **Reintentos 1 + 3** | Un fallo transitorio (BD caída un momento) se reintenta 3 veces (1 s, 2 s, 4 s) y luego va a la DLQ. Nunca se reencola sin límite. | Llamar 3 veces antes de rendirse |
| **At-least-once** | RabbitMQ garantiza entregar **al menos una vez**: puede entregar **dos**. Por eso los consumidores deben ser idempotentes. | El cartero a veces entrega doble |
| **Idempotencia** | Procesar el mismo evento dos veces tiene el mismo efecto que una. Se logra anotando el `eventId` en `eventos_procesados` **en la misma transacción** del efecto. | Marcar la lista de asistencia |
| **`correlationId`** | Número de seguimiento del trámite: el mismo (`checkoutId`) viaja carrito → pedidos → pagos → pedidos/carrito. Con él se sigue una compra en los logs de los cuatro servicios. | El número de encomienda |
| **Outbox** | Para **publicar** sin perder nada: el evento se guarda en la BD en la misma transacción que el cambio y un publicador lo envía después, con confirmación. Hoy solo en `pagos-service`. | Bandeja de salida con acuse de recibo |
| **Publisher confirm + mandatory** | El broker confirma que recibió el mensaje (*ack*) y devuelve el mensaje si ninguna cola lo aceptó. Así el outbox sabe si *de verdad* llegó. | Firma de recibido |
| **Contrato de evento / JSON Schema** | El archivo en `docs/events/` del **productor** que describe exactamente qué lleva el evento. Cada consumidor tiene su propio DTO armado a partir de él (**no se importan clases de otro servicio**). | El formulario oficial |

## Base de datos y concurrencia

| Término | Explicación |
|---|---|
| **Liquibase** | El "historial de obras" de la base: cada cambio de esquema es un archivo numerado (`001-...`). **Nunca** `ddl-auto: update`; Hibernate solo **valida** que coincida. |
| **`@Transactional`** | "Todo o nada": varias escrituras se confirman juntas o ninguna. Imprescindible también en lecturas que recorren colecciones *lazy*. |
| **Lazy** | Una colección (los ítems del carrito) que no se carga hasta que la tocas; si la sesión ya se cerró da `LazyInitializationException`. |
| **Bloqueo optimista (`@Version`)** | Cada fila lleva un número de versión; guardar con una versión vieja falla. Evita que dos escritores se pisen en silencio (hoy en `carritos`). |
| **UNIQUE como red de seguridad** | `pagos.pedido_id` único: aunque dos eventos idénticos lleguen a la vez, solo uno crea el pago. |
| **`FOR UPDATE SKIP LOCKED`** | Consulta que bloquea las filas que toma y salta las ya bloqueadas: dos publicadores del outbox no toman los mismos eventos. |

## Logging y operación

| Término | Explicación |
|---|---|
| **`requestId`** | Id por petición HTTP (header `X-Request-Id`, solo si cumple un formato estricto). Aparece en cada línea de log de esa petición. |
| **MDC** | La "pizarra" por hilo donde se dejan `requestId` / `correlationId` para que el logger los agregue solo a cada línea. |
| **try-with-resources** | `try (recurso) { ... }`: cierra el recurso solo, haya error o no. Con el MDC, lo que quede fuera de las llaves ya no tiene la etiqueta. |
| **Línea de acceso** | Una línea por petición: método, ruta, estado, milisegundos. Sin query ni headers. |
| **Pruebas de fallo (`/probar-fallos`)** | Romper el servicio a propósito con servicios reales (BD caída, broker caído, mensajes basura, duplicados simultáneos, `kill -9`) y medir qué pasa. |

## Calidad
**JaCoCo** (qué líneas ejecutan los tests), **PIT** (tests de mutación: cambia el código y comprueba que algún test falle), **SonarQube** (análisis estático), **OSV** (avisos de dependencias vulnerables), **Testcontainers** (Postgres y RabbitMQ reales y desechables para los tests de integración), **Bruno** (colección de requests para probar a mano).
