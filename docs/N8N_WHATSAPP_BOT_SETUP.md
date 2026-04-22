# Configuracion Del Primer Bot En n8n Para Cocobots

## Objetivo

Esta guia describe como montar el primer bot en `n8n` para que funcione con `WhatsApp` y quede alineado con la arquitectura del proyecto:

- `Django` administra usuarios, clientes, bots, conversaciones y mensajes.
- `n8n` recibe mensajes de WhatsApp, ejecuta el workflow del bot y envia respuestas.
- El dashboard de Cocobots es `solo lectura`.
- Los usuarios del dashboard `no responden manualmente` conversaciones.

El objetivo del primer bot no es construir toda la plataforma de una vez, sino dejar un flujo estable y claro que luego podamos replicar para otros bots.

## Arquitectura Final Deseada

Flujo principal:

1. Un usuario escribe por WhatsApp.
2. WhatsApp entrega el evento a `n8n`.
3. `n8n` normaliza el mensaje entrante.
4. `n8n` notifica a Django que llego un mensaje inbound.
5. `n8n` ejecuta el agente AI.
6. `n8n` envia la respuesta al usuario por WhatsApp.
7. `n8n` notifica a Django el mensaje outbound y el estado de entrega.
8. Django guarda todo para que el dashboard lo muestre en modo lectura.

Regla importante:

- `Django` es la fuente oficial de verdad.
- `n8n` no debe ser la base principal de conversaciones.
- El dashboard no envia mensajes.

## Decisiones Tecnicas Recomendadas

Para el primer bot, fija estas decisiones:

1. Un `Bot` en Django representa un bot del negocio.
2. Ese bot apunta a un workflow de `n8n`.
3. El canal inicial es `WhatsApp`.
4. `n8n` recibe y responde mensajes.
5. Django solo observa, registra y muestra.

## Proveedor De WhatsApp

Antes de empezar, define con cual proveedor vas a trabajar:

- `Meta WhatsApp Cloud API`
- `Twilio WhatsApp`

Recomendacion:

- Usa `Meta WhatsApp Cloud API` si quieres menos capas y control directo.
- Usa `Twilio` si ya tienes experiencia con Twilio o necesitas abstraer varios canales.

En esta guia, el flujo conceptual sirve para ambos. Si no tienes un motivo fuerte para Twilio, yo usaria `Meta WhatsApp Cloud API`.

## Paso 1. Crear El Bot En Django

Antes de construir el workflow, define el bot en la base de datos de Cocobots.

Campos minimos que deberia tener este bot:

- `name`
- `description`
- `status`
- `channel_type = whatsapp`
- `provider = meta_whatsapp` o `twilio_whatsapp`
- `n8n_workflow_id`
- `n8n_webhook_url`
- `external_phone_number_id`
- `config` JSON

Ejemplo conceptual:

```json
{
  "name": "Bot Ventas Datadicoco",
  "description": "Bot de atencion comercial por WhatsApp",
  "status": "ACTIVE",
  "channel_type": "whatsapp",
  "provider": "meta_whatsapp",
  "n8n_workflow_id": "wf_whatsapp_sales_01",
  "n8n_webhook_url": "https://tu-n8n/webhook/whatsapp-sales",
  "external_phone_number_id": "1234567890",
  "config": {
    "language": "es",
    "timezone": "America/Bogota"
  }
}
```

## Paso 2. Definir El Contrato Entre n8n Y Django

Antes de dibujar nodos, define el payload que `n8n` le va a mandar a Django.

### Evento inbound

Este se envia cuando llega un mensaje desde WhatsApp:

```json
{
  "bot_external_id": "sales-bot-01",
  "channel_type": "whatsapp",
  "provider": "meta_whatsapp",
  "external_thread_id": "573001112233",
  "external_message_id": "wamid.HBg...",
  "end_user": {
    "external_id": "573001112233",
    "display_name": "Juan Perez"
  },
  "message": {
    "content": "Hola, quiero informacion",
    "direction": "inbound",
    "message_type": "text"
  },
  "received_at": "2026-03-08T20:10:00Z",
  "raw_payload": {}
}
```

### Evento outbound

Este se envia cuando `n8n` genera y manda la respuesta:

```json
{
  "bot_external_id": "sales-bot-01",
  "external_thread_id": "573001112233",
  "external_message_id": "wamid.HBg...",
  "message": {
    "content": "Hola, con gusto te ayudo",
    "direction": "outbound",
    "message_type": "text"
  },
  "delivery_status": "sent",
  "sent_at": "2026-03-08T20:10:05Z",
  "raw_payload": {}
}
```

### Evento de error

```json
{
  "bot_external_id": "sales-bot-01",
  "external_thread_id": "573001112233",
  "error_code": "provider_send_failed",
  "message": "No fue posible enviar el mensaje",
  "detail": {},
  "created_at": "2026-03-08T20:10:06Z"
}
```

## Paso 3. Redisenar El Workflow De Ejemplo

Tu `Example_2.json` hoy hace esto:

1. Recibe Telegram
2. Pasa por AI Agent
3. Responde por Telegram
4. Guarda historial en Firebase

Para Cocobots, el workflow debe quedar asi:

1. Recibe WhatsApp
2. Normaliza el mensaje
3. Llama a Django para registrar el inbound
4. Ejecuta AI Agent
5. Envia la respuesta por WhatsApp
6. Llama a Django para registrar outbound y delivery
7. Si hay error, llama a Django para registrar error

Esto significa:

- quitar Telegram
- quitar Firebase como storage principal
- meter webhooks hacia Django

## Paso 4. Estructura Del Workflow En n8n

### Nodos recomendados

Workflow base:

1. `Webhook` o trigger del proveedor de WhatsApp
2. `Set` o `Code` para normalizar campos
3. `HTTP Request` a Django para registrar inbound
4. `If` para diferenciar texto, audio u otros tipos
5. `OpenAI Transcribe` si llega audio
6. `AI Agent`
7. `HTTP Request` al proveedor de WhatsApp para enviar respuesta
8. `HTTP Request` a Django para registrar outbound
9. `HTTP Request` a Django para registrar error si algo falla

### Nodos que ya no deberian quedar

Del ejemplo original, deberias eliminar:

- `Telegram Trigger`
- `Telegram`
- `Telegram1`
- escritura directa a Firebase como historial principal

## Paso 5. Construir El Trigger De WhatsApp

### Opcion Meta WhatsApp Cloud API

Normalmente usaras:

- un `Webhook` de `n8n`
- configurado en Meta Developers como callback

Ese webhook debe recibir eventos de:

- mensajes entrantes
- estados de entrega

### Opcion Twilio

Normalmente usaras:

- un `Webhook` de `n8n`
- configurado como `A message comes in`

### Resultado esperado del trigger

Independientemente del proveedor, el flujo debe sacar de ahi estos datos:

- numero del usuario final
- nombre del usuario final si viene disponible
- id externo del mensaje
- texto o referencia al audio
- id del numero de negocio
- timestamp

## Paso 6. Normalizar El Mensaje

Crea un nodo `Set` o `Code` que convierta el payload del proveedor a un formato comun.

Campos recomendados:

- `botExternalId`
- `provider`
- `channelType`
- `externalThreadId`
- `externalMessageId`
- `endUserExternalId`
- `endUserDisplayName`
- `messageType`
- `userMessage`
- `receivedAt`
- `rawPayload`

Ejemplo conceptual:

```json
{
  "botExternalId": "sales-bot-01",
  "provider": "meta_whatsapp",
  "channelType": "whatsapp",
  "externalThreadId": "573001112233",
  "externalMessageId": "wamid.HBg...",
  "endUserExternalId": "573001112233",
  "endUserDisplayName": "Juan Perez",
  "messageType": "text",
  "userMessage": "Hola",
  "receivedAt": "2026-03-08T20:10:00Z",
  "rawPayload": {}
}
```

## Paso 7. Registrar El Mensaje Inbound En Django

Despues de normalizar, agrega un `HTTP Request` hacia Django.

Endpoint sugerido:

- `POST /webhooks/whatsapp/inbound`

Ese endpoint debe:

1. identificar el bot
2. buscar o crear el usuario final
3. buscar o crear la conversacion
4. guardar el mensaje inbound
5. actualizar `last_activity_at`

Respuesta recomendada de Django:

```json
{
  "ok": true,
  "bot_id": 12,
  "conversation_id": 45,
  "message_id": 900
}
```

Ese `conversation_id` conviene conservarlo dentro del workflow para el resto de llamadas.

## Paso 8. Manejar Texto Y Audio

Tu ejemplo actual ya tiene una logica util para voz. Esa parte si puede mantenerse conceptualmente.

Regla:

- si el mensaje es texto, usarlo directo
- si el mensaje es audio, descargarlo y transcribirlo
- si es otro tipo no soportado, responder con fallback

Flujo recomendado:

1. `If messageType == text`
2. `If messageType == audio`
3. `Download Media`
4. `OpenAI Transcribe`
5. reconstruir `userMessage`

## Paso 9. Ejecutar El Agente

Aqui puedes reaprovechar gran parte del `AI Agent` del ejemplo.

Recomendaciones:

- mantener el `system prompt` versionado
- inyectar el nombre del bot y contexto del cliente desde Django si hace falta
- usar una `sessionKey` estable

`sessionKey` recomendada:

`<bot_id>:<externalThreadId>`

Ejemplo:

`12:573001112233`

Eso evita mezclar conversaciones de distintos bots con el mismo numero.

## Paso 10. Enviar La Respuesta Por WhatsApp

Luego del agente, usa un `HTTP Request` al proveedor.

Si usas Meta, sera una llamada al endpoint de envio de mensajes.
Si usas Twilio, sera el endpoint correspondiente de mensajes.

Antes de mandar el mensaje, guarda en variables:

- `conversation_id`
- `bot_id`
- `assistant_output`
- `sessionKey`

El envio debe devolver:

- `external_message_id`
- estado inicial del envio
- payload bruto del proveedor

## Paso 11. Registrar Outbound En Django

Despues del envio, agrega otro `HTTP Request` a Django.

Endpoint sugerido:

- `POST /webhooks/whatsapp/outbound`

Ese endpoint debe:

1. guardar el mensaje outbound
2. asociarlo a la conversacion
3. guardar `external_message_id`
4. guardar `delivery_status`
5. actualizar `last_activity_at`

Importante:

- el dashboard mostrara este mensaje como parte del historial
- el dashboard no lo enviara

## Paso 12. Registrar Estados De Entrega

WhatsApp puede mandar eventos como:

- sent
- delivered
- read
- failed

Conviene tener un workflow separado o una rama separada que reciba esos estados.

Endpoint sugerido en Django:

- `POST /webhooks/whatsapp/status`

Ese endpoint actualiza:

- `delivery_status`
- timestamps relevantes
- logs tecnicos si aplica

## Paso 13. Manejar Errores

Si el proveedor falla o el agente falla:

1. `n8n` captura el error
2. lo manda a Django
3. Django registra `ErrorLog`

Endpoint sugerido:

- `POST /webhooks/whatsapp/error`

Esto es clave para el dashboard de observabilidad futura.

## Paso 14. Como Debe Verse En El Dashboard

El dashboard debe ser solo lectura.

Eso significa:

- ver lista de bots asignados
- ver conversaciones del bot
- ver historial de mensajes
- ver ultima actividad
- ver estados de entrega
- ver errores si el rol lo permite

Y no debe hacer esto:

- no enviar mensajes
- no reabrir conversaciones
- no contestar manualmente por UI

La respuesta al usuario ocurre solo por:

- WhatsApp
- workflow `n8n`

## Paso 15. Primer MVP Real Del Bot

Para el primer bot, no intentes cubrir todo.

Haz solo este alcance:

1. recibir texto por WhatsApp
2. registrar inbound en Django
3. ejecutar AI Agent
4. enviar respuesta por WhatsApp
5. registrar outbound en Django
6. mostrar la conversacion en el dashboard

Deja para despues:

- audio
- adjuntos
- menus complejos
- handoff humano
- analitica avanzada

## Paso 16. Checklist De Implementacion

### En n8n

- crear webhook de entrada de WhatsApp
- normalizar payload
- llamar a Django inbound
- ejecutar AI Agent
- enviar mensaje a WhatsApp
- llamar a Django outbound
- crear rama de errores

### En Django

- definir modelo `Bot` orientado a integracion
- asociar `Conversation` a `client_account`
- agregar `external_thread_id`
- agregar `external_message_id`
- agregar `raw_payload`
- crear endpoints webhook
- dejar dashboard en solo lectura

## Paso 17. Workflow Minimo Recomendado

Secuencia minima:

1. `Webhook WhatsApp`
2. `Set Normalize Input`
3. `HTTP Django Inbound`
4. `AI Agent`
5. `HTTP Send WhatsApp`
6. `HTTP Django Outbound`

Con eso ya tienes el primer bot util y alineado con la plataforma.

## Paso 18. Lo Que No Hay Que Hacer

Evita estas decisiones:

- usar Firebase como base principal del producto
- dejar la conversacion oficial solo en la memoria de `n8n`
- permitir respuesta manual desde el dashboard
- poner permisos de usuarios internos dentro de workflows
- acoplar el bot a Telegram si el producto real es WhatsApp

## Paso 19. Siguiente Paso Despues De Esta Guia

Una vez aceptemos esta arquitectura, el siguiente trabajo tecnico en el repo deberia ser:

1. convertir el dashboard a solo lectura
2. adaptar modelos `Bot`, `Conversation` y `Message`
3. crear endpoints webhook para `n8n`
4. recien despues construir el workflow definitivo de WhatsApp

Si la arquitectura se aprueba, el siguiente documento util seria un segundo `.md` con el contrato exacto de endpoints Django para que el workflow de `n8n` quede implementable sin ambiguedad.
