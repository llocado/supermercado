# Cómo funciona todo: el flujo completo

Este documento responde: **¿qué pasa, paso a paso, desde que un cliente agrega una manzana al carrito hasta que su pedido queda pagado?** y **¿quién habla con quién?** Los diagramas son [Mermaid](https://mermaid.js.org/): GitHub los dibuja directamente.

Para el detalle de cada servicio, mira el README de su repositorio (enlaces en el [README principal](../README.md)) y el [glosario](glosario.md) para los términos.

---

## 1. El mapa general: quién es quién

```mermaid
flowchart LR
    U["Cliente<br/>(tienda-web / Bruno)"]

    subgraph INFRA["supermercado-infra"]
        KC["Keycloak :8180<br/>emite tokens"]
        RMQ["RabbitMQ :5672<br/>bus de eventos"]
    end

    subgraph PROD["app-productos :8080"]
        P_APP["catalogo"]
        P_DB[("Postgres :5432")]
    end
    subgraph CAR["carrito-service :8081"]
        C_APP["carrito"]
        C_DB[("Postgres :5433")]
    end
    subgraph PED["pedidos-service :8082"]
        PE_APP["pedidos"]
        PE_DB[("Postgres :5434")]
    end
    subgraph PAG["pagos-service :8083"]
        PA_APP["pagos"]
        PA_DB[("Postgres :5435")]
    end

    U -- "1 login: usuario y clave" --> KC
    KC -- "token JWT" --> U
    U -- "HTTP + token" --> C_APP
    U -- "HTTP + token (solo lectura)" --> PE_APP
    U -- "HTTP + token (solo lectura)" --> PA_APP
    U -. "HTTP sin token" .-> P_APP

    C_APP -- "HTTP: precio y nombre" --> P_APP
    P_APP --- P_DB
    C_APP --- C_DB
    PE_APP --- PE_DB
    PA_APP --- PA_DB

    C_APP -- "publica carrito.checkout-iniciado" --> RMQ
    RMQ -- "carrito.checkout-iniciado" --> PE_APP
    PE_APP -- "publica pedido.creado" --> RMQ
    RMQ -- "pedido.creado" --> PA_APP
    PA_APP -- "publica pago.aprobado / pago.rechazado (outbox)" --> RMQ
    RMQ -- "pago.aprobado / pago.rechazado" --> PE_APP
    RMQ -- "pago.aprobado" --> C_APP
    RMQ -- "pago.aprobado" --> P_APP
    P_APP -- "publica stock.descuento-rechazado (outbox)" --> RMQ
    RMQ -- "stock.descuento-rechazado" --> PE_APP

    C_APP -. "valida firma del token" .-> KC
    PE_APP -. "valida firma del token" .-> KC
    PA_APP -. "valida firma del token" .-> KC
```

**Cómo leerlo**
- Las **flechas con texto "HTTP"** son llamadas directas y bloqueantes (se espera la respuesta).
- Las que pasan por **RabbitMQ** son **asíncronas**: quien publica no espera; el consumidor lo procesa cuando puede.
- Cada servicio tiene **su propia base de datos** y nadie más la toca. Si pedidos necesita algo de carrito, no consulta su BD: recibe un evento.
- Solo `carrito` llama por HTTP a otro servicio (a `productos`, para saber el precio y el stock). Todo lo demás es por eventos.
- `productos` es el **único dueño del stock**: lo descuenta al recibir `pago.aprobado` y solo publica si **no** alcanza (`stock.descuento-rechazado`).

---

## 2. El camino feliz, paso a paso (compra que se aprueba)

En una frase: el cliente llena su carrito, pide pagar, y desde ahí los servicios se avisan entre sí con mensajes hasta que el pedido queda **PAGADO**. Son 4 fases; cada una tiene su propio diagrama corto y una explicación en palabras simples.

```mermaid
flowchart LR
    F1["Fase 1<br/>Llenar el carrito<br/>(HTTP, el cliente espera)"] --> F2["Fase 2<br/>Checkout<br/>(se crea el pedido)"]
    F2 --> F3["Fase 3<br/>Cobrar<br/>(pagos decide)"]
    F3 --> F4["Fase 4<br/>Consecuencias<br/>(pedido PAGADO y stock descontado)"]
```

**Antes de todo:** el cliente inicia sesión en Keycloak con usuario y clave y recibe un **token JWT**. Ese token viaja en cada llamada HTTP que haga después.

### Fase 1: llenar el carrito (síncrono)

```mermaid
sequenceDiagram
    actor U as Cliente
    participant CAR as carrito
    participant PRO as productos
    U->>CAR: Agregar producto y cantidad
    CAR->>PRO: Cuánto cuesta este producto y cuánto stock hay
    PRO-->>CAR: Nombre, precio, moneda y stock
    CAR->>CAR: Si lo que habría en el carrito supera el stock, responde 422
    CAR->>CAR: Guarda el item en su base de datos
    CAR-->>U: 200 OK, carrito con total
```

Es una conversación normal: el cliente pregunta y espera la respuesta. `carrito` es el único servicio que llama por HTTP a otro (`productos`), porque necesita el precio real y no puede fiarse del que mande el cliente. De paso le pregunta el **stock**: si no alcanza, avisa de inmediato (es un aviso temprano, no una garantía: la garantía es el descuento de la fase 4).

### Fase 2: checkout (aquí empiezan los mensajes)

```mermaid
sequenceDiagram
    actor U as Cliente
    participant CAR as carrito
    participant MQ as RabbitMQ
    participant PED as pedidos
    U->>CAR: Quiero pagar (checkout)
    CAR->>MQ: Mensaje carrito.checkout-iniciado
    CAR-->>U: 202 Recibido, te doy un checkoutId
    MQ->>PED: Entrega el mensaje
    PED->>PED: Crea el Pedido en estado CREADO
    PED->>MQ: Mensaje pedido.creado
    Note over CAR: El carrito NO se vacía todavía
```

Fíjate en el orden: `carrito` responde **202** al cliente *antes* de que el pedido exista. 202 significa "recibido, lo estoy procesando". El pedido se crea después, cuando `pedidos` recibe el mensaje.

### Fase 3: cobrar

```mermaid
sequenceDiagram
    participant MQ as RabbitMQ
    participant PAG as pagos
    MQ->>PAG: Entrega pedido.creado
    PAG->>PAG: Regla de pago: total mayor a 100000 se rechaza, si no se aprueba
    PAG->>PAG: Guarda el Pago y deja pago.aprobado en su bandeja de salida
    Note over PAG: Las dos cosas se guardan juntas en una sola transacción
    PAG->>MQ: Cada 1 segundo el publicador envía lo que haya en la bandeja
    MQ-->>PAG: Recibido, se marca como publicado
```

Esta es la fase más delicada. `pagos` no publica el mensaje directamente: primero lo escribe en una "bandeja de salida" (el **outbox**) junto con el pago, en la misma transacción. Así, o se guardan las dos cosas o ninguna. Después, un proceso aparte (`PublicadorOutbox`) lee la bandeja y la manda a RabbitMQ. Si algo falla en medio, el mensaje sigue en la bandeja y se reintenta; no se pierde.

### Fase 4: consecuencias del pago (en paralelo)

```mermaid
sequenceDiagram
    actor U as Cliente
    participant MQ as RabbitMQ
    participant PED as pedidos
    participant CAR as carrito
    participant PRO as productos
    MQ->>PED: pago.aprobado
    PED->>PED: Verifica pedido, usuario y monto, y pasa CREADO a PAGADO
    MQ->>CAR: pago.aprobado
    CAR->>CAR: Resta del carrito solo lo que se pagó
    MQ->>PRO: pago.aprobado
    PRO->>PRO: Descuenta el stock de todo lo comprado (todo o nada)
    U->>PED: Consultar el pedido
    PED-->>U: Estado PAGADO
```

El mismo mensaje `pago.aprobado` llega a **tres** servicios y cada uno hace lo suyo sin esperar a los otros. Si el cliente agregó algo al carrito después del checkout, eso se conserva. Si en `productos` no alcanza el stock, ver la sección 3b.

**Puntos que conviene entender**

1. **El checkout devuelve `202`, no `200`:** "recibido, se está procesando". El pedido aún no existe cuando respondes.
2. **El `checkoutId` es el hilo conductor:** es el `eventId` del primer mensaje y el `correlationId` de **todos** los siguientes. Buscándolo en los logs de los 4 servicios ves toda la compra.
3. **El carrito no se vacía al hacer checkout**, sino cuando el pago se aprueba (y solo lo comprado). Por eso, si el pago se rechaza, el cliente conserva su carrito.
4. **El stock se descuenta al pagar, no al agregar al carrito.** Agregar solo *avisa*; el descuento de la fase 4 es el árbitro.
5. **La fase 3 usa outbox** para no perder mensajes: pago y mensaje de salida se confirman juntos o no se confirma nada.

---

## 3. Cuando el pago se rechaza

El recorrido es idéntico al camino feliz hasta la **Fase 3**. La diferencia aparece cuando `pagos` aplica su regla y el total supera el límite (ejemplo: pedido de 150000).

```mermaid
sequenceDiagram
    actor U as Cliente
    participant MQ as RabbitMQ
    participant PAG as pagos
    participant PED as pedidos
    participant CAR as carrito
    MQ->>PAG: Entrega pedido.creado con total 150000
    PAG->>PAG: Regla de pago: 150000 supera 100000, RECHAZADO
    PAG->>PAG: Guarda Pago RECHAZADO y deja pago.rechazado en la bandeja de salida
    PAG->>MQ: Publica pago.rechazado
    MQ->>PED: Entrega pago.rechazado
    PED->>PED: Solo lo anota en el log, el pedido SIGUE en CREADO
    Note over CAR: carrito no escucha pago.rechazado, queda intacto
    U->>PED: Consultar el pedido
    PED-->>U: Estado CREADO (pendiente)
```

**Comparación rápida**

| | Pago aprobado | Pago rechazado |
|---|---|---|
| Mensaje que publica `pagos` | `pago.aprobado` | `pago.rechazado` (motivo `MONTO_EXCEDE_LIMITE`) |
| Qué hace `pedidos` | CREADO pasa a PAGADO | Solo escribe en el log; sigue en CREADO |
| Qué hace `carrito` | Resta lo pagado | Nada: no escucha este mensaje |
| Qué hace `productos` | Descuenta el stock | Nada: no escucha este mensaje |
| Resultado para el cliente | Pedido PAGADO, carrito y stock descontados | Pedido pendiente, carrito y stock intactos |

El pedido queda **pendiente** (decisión de diseño cerrada). El reintento de pago es un pendiente fuera de alcance.

---

## 3b. Cuando el pago se aprueba pero ya no hay stock

Entre agregar al carrito y pagar, otro cliente pudo comprar la última unidad. No hay reserva: el descuento al pagar es el árbitro.

```mermaid
sequenceDiagram
    autonumber
    participant MQ as RabbitMQ
    participant PRO as app-productos
    participant PED as pedidos-service

    MQ->>PRO: pago.aprobado (compra 3 unidades, quedan 2)
    PRO->>PRO: valida: no alcanza, NO descuenta nada (todo o nada)
    PRO->>PRO: en UNA transaccion: stock.descuento-rechazado a la bandeja de salida + marca el evento procesado
    PRO->>MQ: stock.descuento-rechazado (outbox, con confirmación)
    MQ->>PED: cola pedidos.stock-descuento-rechazado
    alt el pedido ya está PAGADO
        PED->>PED: PAGADO pasa a SIN_STOCK (estado final, gestión manual)
    else el pedido sigue en CREADO (el evento se adelantó al pago.aprobado)
        PED->>PED: CREADO pasa directo a SIN_STOCK (el rechazo prueba que el pago se aprobó)
        Note over PED: el pago.aprobado que llegue después se ignora (el pedido ya no está en CREADO)
    end
    Note over PED: sin reembolso automático: el dinero es simulado (fuera de alcance)
```

- Si dos pagos compiten por la **última unidad**, `@Version` hace que uno confirme y el otro falle por conflicto; se reintenta, ve el stock en 0 y se rechaza. Nunca queda stock negativo ni se vende dos veces.
- Si el éxito es silencioso (no hay evento `stock.descontado`), pedidos solo se entera de los fallos.

---

## 4. La topología de RabbitMQ: exchanges, colas y DLQ

```mermaid
flowchart LR
    subgraph EX["Exchanges (topic): uno por productor"]
        E1(["carrito.events"])
        E2(["pedidos.events"])
        E3(["pagos.events"])
        E4(["productos.events"])
    end

    E1 -- "carrito.checkout-iniciado" --> Q1["pedidos.carrito-checkout-iniciado"]
    E2 -- "pedido.creado" --> Q2["pagos.pedido-creado"]
    E3 -- "pago.aprobado" --> Q3["pedidos.pago-aprobado"]
    E3 -- "pago.aprobado" --> Q4["carrito.pago-aprobado"]
    E3 -- "pago.rechazado" --> Q5["pedidos.pago-rechazado"]
    E3 -- "pago.aprobado" --> Q6["productos.pago-aprobado"]
    E4 -- "stock.descuento-rechazado" --> Q7["pedidos.stock-descuento-rechazado"]

    Q1 --> L1["CarritoEventListener<br/>(pedidos)"]
    Q2 --> L2["PedidoEventListener<br/>(pagos)"]
    Q3 --> L3["PagoEventListener<br/>(pedidos)"]
    Q4 --> L4["PagoEventListener<br/>(carrito)"]
    Q5 --> L3
    Q6 --> L5["PagoEventListener<br/>(productos)"]
    Q7 --> L6["StockEventListener<br/>(pedidos)"]

    Q1 -. "falla definitiva" .-> D1[("pedidos.carrito-checkout-iniciado.dlq")]
    Q2 -. "falla definitiva" .-> D2[("pagos.pedido-creado.dlq")]
    Q3 -. "falla definitiva" .-> D3[("pedidos.pago-aprobado.dlq")]
    Q4 -. "falla definitiva" .-> D4[("carrito.pago-aprobado.dlq")]
    Q5 -. "falla definitiva" .-> D5[("pedidos.pago-rechazado.dlq")]
    Q6 -. "falla definitiva" .-> D6[("productos.pago-aprobado.dlq")]
    Q7 -. "falla definitiva" .-> D7[("pedidos.stock-descuento-rechazado.dlq")]
```

- Un **exchange por servicio productor**; la *routing key* es el nombre del evento.
- **Cada consumidor tiene su propia cola**: `pago.aprobado` va a **tres** colas (pedidos, carrito y productos) y cada uno la procesa a su ritmo.
- Cada cola tiene su **DLQ** (a través del exchange `*.dlx` del consumidor).
- Cada servicio **declara** (de forma idempotente) los exchanges ajenos que necesita, para poder enlazar su cola aunque el otro servicio no haya arrancado.

---

## 5. ¿Qué pasa cuando un evento falla? (el árbol de decisión del listener)

```mermaid
flowchart TD
    A["Llega un mensaje a la cola"] --> B{"Envelope y payload<br/>legibles y validos?"}
    B -- "no: JSON roto, campo ausente, tamano excedido" --> X["AmqpRejectAndDontRequeueException<br/>DLQ de inmediato, SIN reintentos<br/>(1 linea de log)"]
    B -- si --> C{"eventId ya procesado?"}
    C -- si --> Y["Se descarta como duplicado<br/>INFO y ack"]
    C -- no --> D["Ejecuta el caso de uso"]
    D -- "OK" --> OK["Guarda efecto y marca eventId<br/>en la MISMA transaccion, ack"]
    D -- "regla de dominio violada<br/>(ej. usuario o monto distintos)" --> X
    D -- "choque de unicidad por duplicado concurrente" --> E{"ya estaba procesado?"}
    E -- si --> Y
    E -- no --> F
    D -- "fallo transitorio<br/>(BD caida, pedido aun no visible)" --> F["Reintento 1 + 3<br/>esperas de 1 s, 2 s y 4 s"]
    F -- "se recupera" --> OK
    F -- "agota los reintentos" --> G["MessageRecoverer: 1 linea de log<br/>y a la DLQ"]
```

**La regla de oro:** un mensaje que falla **nunca** vuelve a la cola sin límite (`default-requeue-rejected: false`). Antes de esta regla, un solo mensaje malo llegó a generar 115 MB de log en 6 segundos.

---

## 6. El outbox de pagos (y de productos): cómo se publica sin perder nada

El problema que resuelve: si pagos guarda el pago y **después** publica el evento, un fallo entre las dos cosas deja un pago sin aviso (o un aviso de un pago que nunca se guardó).

```mermaid
sequenceDiagram
    autonumber
    participant L as PedidoEventListener
    participant UC as ProcesarPagoDePedidoUseCase
    participant DB as Postgres de pagos
    participant PUB as PublicadorOutbox (cada 1 s)
    participant MQ as RabbitMQ

    L->>UC: execute(comando)
    rect rgb(240,255,240)
    Note over UC,DB: UNA sola transaccion
    UC->>DB: INSERT pagos
    UC->>DB: INSERT eventos_salida (publicado_en = NULL)
    UC->>DB: INSERT eventos_procesados
    end
    Note over DB: o se confirman las 3, o ninguna

    loop cada segundo
        PUB->>DB: SELECT ... WHERE publicado_en IS NULL FOR UPDATE SKIP LOCKED
        PUB->>MQ: publica (mandatory) y espera confirmacion
        alt ack Y alguna cola lo recibio
            PUB->>DB: UPDATE publicado_en = now()
        else broker no responde
            PUB->>DB: intentos + 1 (queda pendiente, se corta el lote)
        else ninguna cola lo recibio
            PUB->>DB: intentos + 1 (queda pendiente)
        end
    end
```

- Si el servicio muere entre guardar y publicar, **el evento sigue en la tabla** y se publica al reiniciar.
- Si muere entre publicar y marcar `publicado_en`, se publica **dos veces**. No importa: los consumidores son idempotentes (por eso la garantía es *at-least-once*).
- El `eventId` del evento es **determinista** (`tipo + pagoId`), así el mismo evento siempre tiene el mismo id.
- `app-productos` usa **el mismo patrón** para publicar `stock.descuento-rechazado` (su bandeja es `eventos_salida`, el cartero es su propio `PublicadorOutbox`).

---

## 7. Por dentro de un servicio: el recorrido de una petición HTTP

Ejemplo: `POST /api/carrito/items`.

```mermaid
flowchart TD
    R["Peticion HTTP"] --> F1["RequestIdFilter<br/>asigna requestId, linea de acceso"]
    F1 --> F2["Spring Security<br/>valida firma del JWT y exige rol cliente"]
    F2 --> CTRL["CarritoController<br/>saca el usuario del claim sub, valida el body"]
    CTRL --> UC["AgregarItemAlCarritoUseCase<br/>@Transactional"]
    UC --> PORT1["CatalogoProductosPort"]
    PORT1 --> ADP1["ProductosServiceClient<br/>HTTP a app-productos, con timeouts"]
    UC --> DOM["Carrito.agregarItem<br/>reglas del dominio"]
    UC --> PORT2["CarritoRepositoryPort"]
    PORT2 --> ADP2["CarritoPersistenceAdapter<br/>mapper a CarritoEntity"]
    ADP2 --> DB[("Postgres")]
    UC --> RESP["Carrito de dominio"]
    RESP --> MAP["CarritoDtoMapper"]
    MAP --> OUT["CarritoResponse JSON"]
    UC -. "excepcion de dominio" .-> GEH["GlobalExceptionHandler<br/>404, 409, 502, 503..."]
```

La flecha es siempre **hacia adentro**: `infrastructure → application → domain`. El dominio no importa nada de los demás; los casos de uso solo conocen **puertos** (interfaces).

---

## 8. Seguridad: cómo se sabe quién eres

```mermaid
sequenceDiagram
    autonumber
    actor U as Cliente
    participant KC as Keycloak
    participant S as Un servicio (Resource Server)

    U->>KC: POST /realms/supermercado/.../token (usuario, clave)
    KC-->>U: access_token (JWT firmado)
    U->>S: GET /api/pedidos con "Authorization: Bearer token"
    S->>S: valida firma, expiracion y emisor (clave publica de Keycloak)
    S->>S: lee sub (id del usuario) y realm_access.roles
    alt rol cliente presente
        S->>S: ejecuta con usuarioId = sub
        S-->>U: 200
    else sin token o token invalido
        S-->>U: 401
    else rol insuficiente
        S-->>U: 403
    end
```

- El servicio **no guarda contraseñas ni sesiones**; solo verifica la firma.
- El `usuarioId` **siempre** sale del `sub` del token, nunca del body ni de la URL.
- Recursos de otro usuario responden **404** (igual que "no existe") para no revelar que el id es válido.
- **`app-productos` no tiene seguridad todavía** (pendiente documentado).

---

## 9. Ciclo de vida del pedido

```mermaid
stateDiagram-v2
    [*] --> CREADO: evento carrito.checkout-iniciado
    CREADO --> PAGADO: pago.aprobado (usuario y monto coinciden)
    PAGADO --> DESPACHADO: futuro (entregas-service)
    DESPACHADO --> ENTREGADO: futuro
    CREADO --> CREADO: pago.rechazado (solo se registra)
    PAGADO --> SIN_STOCK: stock.descuento-rechazado (no alcanzó el stock)
    CREADO --> SIN_STOCK: stock.descuento-rechazado que se adelantó al pago.aprobado
    SIN_STOCK --> [*]: gestión manual
    ENTREGADO --> [*]
```

Solo se puede avanzar **un paso** (`EstadoPedido.puedeTransicionarA`). `DESPACHADO` y `ENTREGADO` existen en el modelo pero ningún flujo los usa todavía. `SIN_STOCK` es una **rama lateral**: se llega desde `PAGADO` (o desde `CREADO` si el rechazo se adelantó al pago) y no se sale (no forma parte del orden lineal, por eso el código lo trata aparte).

---

## 10. Dos escritores sobre el mismo carrito (bloqueo optimista)

```mermaid
sequenceDiagram
    autonumber
    participant REST as Peticion REST del usuario
    participant PAGO as Listener de pago.aprobado
    participant DB as Postgres de carrito

    REST->>DB: lee carrito (version = 7)
    PAGO->>DB: lee carrito (version = 7)
    PAGO->>DB: UPDATE ... WHERE version = 7 (descuenta lo pagado)
    DB-->>PAGO: ok, version = 8
    REST->>DB: UPDATE ... WHERE version = 7 (agrega 3 manzanas)
    DB-->>REST: 0 filas: la version ya no es 7
    REST-->>REST: OptimisticLockingFailure, responde 409
    Note over PAGO: si el que pierde es el listener,<br/>se reintenta solo y lee la version nueva
```

Sin `@Version`, el segundo en guardar **pisaba en silencio** al primero y el usuario perdía lo recién agregado. `app-productos` usa lo mismo en `productos.version`: dos pagos que descuentan el mismo stock no se pisan.

---

## 10b. Dónde entra la tienda web

El cliente no usa Bruno: usa un navegador. La **tienda web** (`tienda-web`, React + TypeScript, puerto 5173) se sienta *delante* de los servicios y les habla por HTTP, igual que Bruno, pero desde el navegador del cliente.

```mermaid
flowchart LR
    NAV["Navegador del cliente<br/>tienda-web :5173"] -->|"GET /api/productos<br/>(catálogo, búsqueda, detalle)"| PRO["app-productos :8080"]
    NAV -->|"login por redirección + PKCE"| KC["Keycloak :8180"]
    NAV -->|"carrito y pagar<br/>(Bearer token)"| CAR["carrito-service :8081"]
    NAV -->|"mis pedidos<br/>(Bearer token)"| PED["pedidos-service :8082"]
```

El front cubre: catálogo con búsqueda y detalle, login, carrito (agregar, cambiar cantidad, quitar, vaciar), **pagar** y **Mis pedidos**. Como `POST /checkout` responde `202`, el pedido aún no existe al volver a la pantalla: "Mis pedidos" consulta cada 1,5 s (máximo ~20 s) hasta que aparece y sale de `CREADO` (consistencia eventual). Un reintento de pago con la misma `Idempotency-Key` no duplica el pedido.

Como no hay *API Gateway*, el front conoce tres direcciones distintas y cada servicio debe autorizar su origen con CORS. El token vive solo en memoria de la pestaña (nada en `localStorage` ni cookies). El resto del recorrido —eventos, pagos, stock— no cambia: el front solo reemplaza a Bruno como cliente.

---

## 11. Datos: qué guarda cada servicio

```mermaid
erDiagram
    PRODUCTOS {
        uuid id PK
        varchar sku UK
        varchar nombre
        numeric precio_monto
        varchar precio_moneda
        int stock
        uuid categoria_id
        boolean activo
        bigint version
    }

    CARRITOS ||--o{ ITEMS_CARRITO : contiene
    CARRITOS {
        uuid id PK
        varchar usuario_id UK
        timestamp actualizado_en
        bigint version
    }
    ITEMS_CARRITO {
        uuid carrito_id FK
        uuid producto_id
        varchar nombre
        numeric precio_unitario
        int cantidad
    }

    PEDIDOS ||--o{ ITEMS_PEDIDO : contiene
    PEDIDOS {
        uuid id PK
        uuid carrito_id_origen
        varchar usuario_id
        numeric total
        varchar estado
    }
    ITEMS_PEDIDO {
        uuid pedido_id FK
        uuid producto_id
        varchar nombre
        numeric precio_unitario
        int cantidad
    }

    PAGOS {
        uuid id PK
        uuid pedido_id UK
        varchar usuario_id
        numeric monto
        varchar moneda
        varchar estado
        varchar motivo_rechazo
    }
    EVENTOS_SALIDA {
        uuid id PK
        varchar event_type
        uuid correlation_id
        text payload
        timestamp publicado_en
        int intentos
    }
    EVENTOS_PROCESADOS {
        uuid event_id PK
        timestamp procesado_en
    }
```

- Cada servicio tiene **su propia base**; `EVENTOS_PROCESADOS` existe en carrito, pedidos, pagos y productos (idempotencia) y `EVENTOS_SALIDA` en pagos y productos (outbox).
- **No hay claves foráneas entre servicios** (`carrito_id_origen`, `pedido_id`, `producto_id` son ids "por referencia", no relaciones de base): cada servicio es dueño de su dato.
- Los ítems guardan una **foto** de nombre y precio al momento de agregarlos, así un cambio posterior de precio no altera un carrito ni un pedido ya creado.

---

## 12. Dónde mirar cuando algo falla

| Síntoma | Dónde mirar |
|---|---|
| Un evento no tuvo efecto | La **DLQ** del consumidor (UI de RabbitMQ `http://localhost:15672`) y el log con su `eventId`. |
| Seguir una compra completa | Buscar el `checkoutId` (= `correlationId`) en los logs de los 4 servicios. |
| Un error en una petición HTTP | El header `X-Request-Id` de la respuesta → buscar ese `requestId` en el log. |
| Un pago aprobado que no llegó a pedidos o carrito | Tabla `eventos_salida` de pagos: ¿`publicado_en` es `NULL`? (ver sección 6). |
| Un pedido que sigue en `CREADO` | ¿Hubo `pago.rechazado`? (sección 3). ¿Hay mensajes en `pedidos.pago-aprobado.dlq`? |
| Un pedido en `SIN_STOCK` | La tabla `eventos_salida` de productos (¿qué faltó?) y el log de productos con el `pagoId`/`correlationId` (sección 3b). |
| Un pago aprobado cuyo stock no bajó | Cola `productos.pago-aprobado` y su DLQ; log de productos con el `eventId`. |
| Limpiar datos de prueba | El script de reinicio de datos del repo de infraestructura (privado) o, en la demo, `./demo-down.sh` |
