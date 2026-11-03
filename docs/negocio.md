# Caso de negocio: plataforma de supermercado online para tiendas de barrio

> **Naturaleza del documento:** proyecto de portafolio con un caso de negocio realista pero **simulado**. Las decisiones de base están en la sección 1. Toda cifra marcada con 🔶 es una **hipótesis o un ejemplo ilustrativo**, no un dato de mercado: se valida con entrevistas y datos reales antes de defenderla como cierta. Lo no marcado se deriva de lo que el sistema ya hace.
>
> Documento vivo. Es el "por qué" del proyecto; el "cómo" técnico está en [flujo-completo.md](flujo-completo.md) y en los README de cada servicio.

---

## 1. Decisiones de base

| Decisión | Elección | Consecuencia |
|---|---|---|
| Naturaleza | Portafolio / aprendizaje, caso realista simulado | Cifras como supuestos explícitos; foco en razonamiento, no en investigación de mercado exhaustiva |
| Cliente que paga | Supermercado de barrio o cadena pequeña (1 a 5 sucursales) | Modelo **B2B2C**: se vende a la tienda, que atiende al cliente final |
| Entrega | Despacho a domicilio **y** retiro en tienda | Hace falta un servicio de entregas (futuro) y flujo de retiro |
| Mercado | Chile, zona urbana | CLP, medios de pago locales, boleta electrónica, competidores locales |

---

## 2. Resumen en 30 segundos

**Qué es:** el sistema de ventas online de un supermercado de barrio: catálogo, carrito, pedido, pago y entrega, sin que la tienda tenga que construir ni arrendar una plataforma enorme.

**Para quién:** el dueño o la dueña de un supermercado de barrio que hoy pierde ventas frente a las grandes cadenas y a las apps de reparto, y a sus clientes de siempre, que ya compran todo desde el celular.

**Qué problema resuelve:** permite vender online con el catálogo y los precios de la tienda, cobrar con un pago confiable y saber qué se vendió, sin pagar una comisión por cada pedido a un intermediario y sin atender pedidos a mano por WhatsApp.

**Cómo entrega valor:** el cliente arma su compra en pocos pasos, el pago se confirma en segundos, el pedido llega a la tienda ya pagado y con el detalle completo, y el carrito no se pierde si algo falla.

---

## 3. Para quién es (segmentos y personas)

> ⚠️ **Sin validar.** Las personas son **ficticias**, construidas para razonar. Nadie con experiencia en el rubro las ha revisado todavía: se reemplazan por entrevistas reales (sección 12) antes de usarlas como argumento.

### 3.1 Quien paga: la tienda (B2B)

**Persona: Marcela, 48 años, dueña de un supermercado de barrio con 2 sucursales** 🔶
- Tiene 6 a 15 empleados; vende por mostrador y recibe algunos pedidos por WhatsApp o teléfono.
- Conoce a sus clientes y su stock "de memoria"; no tiene un equipo de tecnología.
- Le preocupa perder a los clientes jóvenes y a las familias que ya piden en las apps de las grandes cadenas.
- Quiere vender online **sin** regalar un porcentaje alto de cada venta ni depender de un tercero que controla a sus clientes.

### 3.2 Quien compra: el cliente final (B2C)

**Persona A: Camila, 34 años, trabaja y tiene dos hijos** 🔶
- Compra la reposición semanal; tiene poco tiempo y le molesta ir a la tienda por cosas que ya sabe que necesita.
- Valora: que el precio sea el real, que lo pedido esté disponible y que el despacho llegue en la ventana que eligió.

**Persona B: Don Jorge, 67 años, vive cerca de la tienda** 🔶
- Prefiere la tienda de siempre, pero le cuesta cargar bolsas pesadas.
- Valora: la confianza en la tienda y la simplicidad. Retira o recibe en casa.

### 3.3 Quienes operan el sistema (usuarios internos, hoy sin interfaz)

| Rol | Qué necesita | Estado |
|---|---|---|
| Administrador del catálogo | Cargar productos, precios y fotos | API existe (`app-productos`), sin interfaz |
| Preparador de pedidos / bodeguero | Ver qué armar y marcarlo listo | No existe |
| Repartidor | Ver su ruta y confirmar entrega | No existe |

---

## 4. Qué problemas resuelve

Formulados como "trabajos" que el cliente quiere cumplir (*jobs to be done*).

### Para la tienda
| Problema actual 🔶 | Consecuencia | Cómo lo aborda el sistema |
|---|---|---|
| No tiene canal online propio | Pierde ventas frente a cadenas y apps de reparto | Catálogo, carrito, pedido y pago propios |
| Pedidos por WhatsApp o teléfono | Errores de transcripción, tiempo perdido, sin registro | El pedido nace estructurado y trazable (`pedido.creado`) |
| Cobra "a la entrega" o por transferencia manual | Pedidos que se caen, conciliación manual | Pago confirmado **antes** de preparar el pedido (`PAGADO`) |
| No sabe qué se vende ni cuándo | Compra mal, tiene quiebres | Cada paso emite un evento medible (sección 7) |
| Las apps intermediarias cobran comisión y se quedan con el cliente | Margen bajo y sin relación directa | Canal propio: el cliente es de la tienda |

### Para el cliente final
| Problema actual 🔶 | Cómo lo aborda el sistema |
|---|---|
| Ir a la tienda por la reposición semanal toma tiempo | Armar el carrito desde el celular y recibirlo en casa |
| Incertidumbre: "¿tendrán lo que busco, al precio que vi?" | El carrito toma nombre y precio **del catálogo en vivo** al agregar |
| Miedo a que se cobre y el pedido no exista | El pedido solo pasa a `PAGADO` con un pago aprobado verificado (usuario y monto coinciden) |
| Perder el carrito si algo falla | El carrito **no se vacía al hacer checkout**: solo se descuenta lo pagado, y si el pago falla el cliente conserva todo |
| Que un doble clic cobre dos veces | `Idempotency-Key` en el checkout y un solo pago por pedido |

---

## 5. Propuesta de valor

**Enunciado:**
> Para dueños de supermercados de barrio que quieren vender online sin entregar su margen ni sus clientes a un intermediario, esta plataforma es un sistema de ventas propio —catálogo, carrito, pago y entrega— que confirma cada pago antes de preparar el pedido y mantiene el carrito del cliente a salvo. A diferencia de las apps de reparto, la tienda conserva la relación con su cliente y el control de sus precios.

| Para la tienda | Para el cliente |
|---|---|
| Canal propio sin comisión por pedido a un marketplace 🔶 | Compra rápida desde el celular |
| Pedidos ya pagados, completos y trazables | Precio y disponibilidad coherentes con la tienda |
| Datos propios de ventas | Pago seguro y sin cobros dobles |
| Operación fiable aun si un componente falla (sin pérdida de pedidos) | Carrito que no se pierde |

### Diferenciadores (hipótesis a contrastar con la competencia)
1. **Confiabilidad de punta a punta:** un pago aprobado nunca se pierde ni se duplica (outbox, idempotencia, reintentos, DLQ). Es una ventaja *técnica* que se traduce en confianza: "no se cobra dos veces y no se pierde un pedido".
2. **Propiedad del cliente y de los datos:** la tienda es dueña de sus pedidos y de su relación con el cliente.
3. **Pensado para supermercado, no para tienda genérica:** carritos con muchas unidades, reposición recurrente y, a futuro, sustituciones y stock por sucursal.

---

## 6. Cómo se entrega el valor: del negocio al sistema

El recorrido del cliente, y qué componente lo hace posible:

| Momento del cliente | Valor que percibe | Componente | Estado |
|---|---|---|---|
| Ver productos y precios | "Lo que veo es lo que hay" | `app-productos` | ✅ (sin interfaz ni autenticación) |
| Armar el carrito | Rapidez, total siempre visible | `carrito-service` | ✅ |
| Confirmar la compra | "Ya está, me avisarán" | `POST /checkout` (202, idempotente) | ✅ |
| Que se registre el pedido | Pedido estructurado, trazable | `pedidos-service` | ✅ |
| Pagar | Pago confirmado en segundos, sin cobros dobles | `pagos-service` (**simulado**) | 🟡 simulado, sin pasarela real |
| Que el carrito refleje lo comprado | Sin ítems "fantasma" | `carrito-service` (`pago.aprobado`) | ✅ |
| Saber en qué estado va | Transparencia | `GET /api/pedidos` | 🟡 solo `CREADO` y `PAGADO` |
| Recibir o retirar | Cumplimiento de la promesa | `entregas-service` (futuro) | ❌ |
| Que haya stock de verdad | Sin quiebres sorpresa | `app-productos` (carga de stock, descuento al pagar) + aviso en `carrito-service` | 🟡 descuenta al pagar; sin reserva ni reposición automática |

### Brechas para que el valor sea real (de mayor a menor impacto)
1. **Stock confiable (parcialmente cerrada, 2026-10-10):** ya se carga, se avisa al agregar y se descuenta al pagar; si no alcanza el pedido queda `SIN_STOCK`. Faltan la reserva (hay sobreventa acotada), el reembolso y la gestión del pedido sin stock.
2. **Pago real:** pasarela (en Chile, p. ej. Webpay Plus, Flow, Mercado Pago) y, más adelante, devoluciones.
3. **Entrega y retiro:** el valor del pedido se completa recién cuando llega a la persona.
4. **Interfaz (en curso, 2026-10-12):** tienda online para el cliente y panel para administrar catálogo y pedidos. Hecho: catálogo web de solo lectura (`tienda-web`, React + TypeScript). Faltan login, carrito, checkout, mis pedidos y el panel de administración.
5. **Seguridad y operación:** autenticación en productos, credenciales no por defecto (ver [riesgos-conocidos.md](riesgos-conocidos.md)).
6. **Documento tributario:** boleta electrónica (SII) para operar de verdad.
7. **Fechas de vencimiento (pendiente, sin fecha; anotada 2026-10-10):** hoy el stock es un número por producto, sin
   lotes ni fechas. En un supermercado de alimentos importa para no vender vencido, rotar primero lo que vence antes
   (FEFO), y mermas. Tocaría: lotes con cantidad y fecha en `app-productos` (el descuento al pagar tomaría del lote que
   vence antes), una regla de "no vender a menos de N días del vencimiento" y un aviso de próximos a vencer para el
   panel de administración. Decisión de diseño aún abierta: lotes completos vs. una sola fecha por producto.
   Conviene hacerlo **después** de la interfaz de administración y antes de operar con una tienda real; cambia el
   modelo de stock recién cerrado, así que se planifica en Plan Mode.

---

## 7. Métricas de éxito (KPIs)

Buena parte se puede medir **con los eventos que el sistema ya emite**, usando el `correlationId` (= `checkoutId`) para seguir un intento de compra.

### Embudo de compra
| Métrica | Definición | Fuente |
|---|---|---|
| Conversión a checkout | Checkouts iniciados ÷ carritos con ítems | `carrito.checkout-iniciado` ÷ carritos activos |
| Pedidos creados | Eventos `pedido.creado` por día | `pedidos-service` |
| **Tasa de pago aprobado** | `pago.aprobado` ÷ `pedido.creado` | `pagos-service` |
| Tasa de rechazo de pago | `pago.rechazado` ÷ `pedido.creado` (+ motivo) | `pagos-service` |
| Abandono tras rechazo | Pedidos que quedan en `CREADO` sin nuevo intento | `pedidos` (requiere reintento de pago) |

### Valor del negocio
| Métrica | Definición |
|---|---|
| **Ticket promedio** | Total pagado ÷ pedidos pagados |
| Unidades por pedido | Suma de cantidades ÷ pedidos pagados |
| **Recompra** | Clientes con 2 o más pedidos pagados en 30 días ÷ clientes con 1 o más |
| Ventas por canal propio | Monto pagado en la plataforma (frente al total de la tienda) |

### Calidad de servicio (el diferenciador)
| Métrica | Meta ilustrativa 🔶 |
|---|---|
| Tiempo `checkout → PAGADO` (p95) | menos de 5 s |
| Pagos duplicados | 0 (garantizado por diseño: `pedido_id` único) |
| Eventos en DLQ sin revisar | 0 al cierre del día |
| Disponibilidad del checkout | 99,5 % 🔶 |
| Pedidos pagados sin entregar en la ventana prometida | menos de 2 % 🔶 (requiere entregas) |

> **Métrica norte propuesta:** *pedidos pagados y entregados a tiempo por semana.* Une todo el valor: que el cliente compre, que se cobre bien y que se cumpla.

---

## 8. Modelo de negocio (lienzo simplificado)

| Bloque | Hipótesis 🔶 |
|---|---|
| **Segmento de clientes** | Supermercados de barrio y cadenas pequeñas (1 a 5 sucursales) en zonas urbanas de Chile; usuarios finales: hogares |
| **Propuesta de valor** | Sección 5 |
| **Canales** | Venta directa a tiendas (visitas, referidos, gremios), demostración con un piloto; tienda online del cliente final bajo la marca de la tienda |
| **Relación con clientes** | Onboarding acompañado (carga de catálogo), soporte por WhatsApp/correo |
| **Ingresos** | Opción A: suscripción mensual por tienda. Opción B: suscripción baja + comisión pequeña por pedido pagado. Opción C: implementación inicial + mantención. **Recomendado para validar:** A o B |
| **Recursos clave** | Plataforma (estos servicios), un catálogo cargado, relación con la tienda |
| **Actividades clave** | Desarrollo, operación y monitoreo, soporte, incorporación de tiendas |
| **Socios clave** | Pasarela de pago, proveedor de nube, proveedor de boleta electrónica, (futuro) servicio de reparto |
| **Estructura de costos** | Nube (servicios, bases de datos, RabbitMQ, Keycloak), comisión de la pasarela de pago (la paga la tienda o el cliente), soporte, desarrollo, cumplimiento legal |

### Ejemplo ilustrativo de economía por tienda 🔶
Sólo para mostrar **cómo** se razona; se reemplaza con números reales.

```
Ingresos por tienda / mes  =  suscripción  +  (pedidos pagados × comisión por pedido)
Costo por tienda / mes     =  nube compartida / n.º de tiendas  +  soporte  +  comisión de pasarela (la paga la tienda)
Margen por tienda          =  Ingresos − Costo
Punto de equilibrio        =  costos fijos mensuales ÷ margen por tienda
```
Palancas: más tiendas sobre la misma infraestructura (el costo marginal baja), más pedidos por tienda, menor costo de soporte por tienda.

---

## 9. Competencia y alternativas

Cada una es una alternativa que la tienda tiene **hoy**; el sistema compite contra ellas, no solo contra otro software.

> ⚠️ **Sin validar.** Esta tabla es un primer borrador hecho sin investigar el mercado. Las fortalezas y debilidades son hipótesis; hay que contrastarlas con las apps reales y con lo que dicen los dueños de tiendas antes de afirmarlas.

| Alternativa | Fortaleza | Debilidad frente a esta propuesta 🔶 |
|---|---|---|
| **No hacer nada / mostrador** | Cero costo, relación personal | Pierde a los clientes que ya compran online |
| **WhatsApp y teléfono** | Inmediato, conocido | Manual, errores, sin cobro integrado ni registro |
| **Apps de reparto / marketplaces** (p. ej. PedidosYa, Rappi, Cornershop) | Demanda ya existente, logística | Comisión por pedido y la relación con el cliente queda en la app |
| **Apps de las grandes cadenas** (Líder, Jumbo, Unimarc, Santa Isabel) | Marca, surtido, escala | La tienda de barrio no puede competir en precio ni surtido, pero sí en cercanía |
| **Plataformas de tienda online genéricas** (Shopify, Jumpseller, WooCommerce) | Rápidas de levantar | No están pensadas para el supermercado (muchos ítems, reposición, stock) y la tienda arma todo |

**Dónde ganaría el producto:** tiendas que quieren canal propio, con foco en confiabilidad y sin comisión por pedido a un tercero.
**Dónde no:** quien busca demanda nueva y logística ya resuelta (ahí gana el marketplace).

---

## 10. Alcance: MVP y después

### MVP (lo mínimo para que un piloto tenga valor real)
- ✅ Catálogo, carrito, pedido, pago (simulado), descuento del carrito.
- ✅ **Descuento de stock** al pagar (todo o nada); si no alcanza, el pedido queda `SIN_STOCK`. 🔜 Falta gestionarlo (reponer, sustituir o devolver el dinero).
- 🔜 **Pasarela de pago real** (una) y reintento de pago.
- 🔜 **Retiro en tienda** (más simple que el despacho): estados `DESPACHADO`/`ENTREGADO` o `LISTO_PARA_RETIRO`.
- 🔜 **Interfaz** mínima: tienda para el cliente y panel de pedidos para la tienda.
- 🔜 Autenticación en `app-productos` y credenciales no por defecto.

### Después
- Despacho a domicilio (zonas, ventanas horarias, costo de envío, repartidor).
- Stock por sucursal; sustituciones ("si no hay, ¿qué te envío?").
- "Repetir mi última compra" y listas favoritas (recompra).
- Promociones y descuentos (el dominio ya tiene `Precio.aplicarDescuento`).
- Notificaciones al cliente (estado del pedido).
- Boleta electrónica, reportes de ventas, multi-tienda.

### Fuera de alcance por ahora
Marketplace con varios vendedores, programa de puntos, pagos recurrentes, app móvil nativa.

---

## 11. Supuestos y riesgos

### Supuestos principales a validar 🔶
1. Las tiendas de barrio **quieren** un canal online propio y están dispuestas a pagar por él.
2. Sus clientes ya compran el súper desde el celular y aceptarían hacerlo en la tienda de siempre.
3. Una comisión menor que la de un marketplace es un argumento de venta suficiente.
4. El catálogo se puede cargar con un esfuerzo razonable para la tienda.

### Riesgos
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Que la tienda no tenga logística de despacho | No puede cumplir la promesa | Empezar solo con retiro en tienda |
| Stock descuadrado entre tienda física y online | Pedidos que no se pueden cumplir | Descuento de stock + ajuste manual + margen de seguridad |
| Fallas en el pago (doble cobro, cobro sin pedido) | Pérdida de confianza | Ya mitigado por diseño (outbox, idempotencia, `pedido_id` único); falta probar con pasarela real |
| Dependencia de un proveedor de pago | Caída del cobro | Interfaz de pago intercambiable (puerto y adaptador) |
| **Cumplimiento legal en Chile** | Multas, bloqueo | Revisar protección de datos personales (nueva ley, verificar su fecha de vigencia), derechos del consumidor (SERNAC), boleta electrónica (SII) |
| Seguridad (datos de clientes y pagos) | Fuga o fraude | No almacenar datos de tarjeta (lo hace la pasarela); pendientes en [riesgos-conocidos.md](riesgos-conocidos.md) |
| Adopción baja por falta de interfaz | Sin uso | Priorizar la interfaz mínima del MVP |

---

## 12. Cómo validar el caso (siguiente paso del negocio, no del código)

1. **5 entrevistas** con dueños de supermercados de barrio: cómo reciben pedidos hoy, qué pierden, cuánto pagarían.
2. **5 entrevistas** con clientes finales: qué compran online, qué los frena.
3. **Prototipo clicable** de la tienda online (sin código) y probarlo con ellos.
4. **Piloto** con una tienda: medir las métricas de la sección 7 durante 4 semanas.
5. Corregir los supuestos 🔶 de este documento con lo aprendido.

---
