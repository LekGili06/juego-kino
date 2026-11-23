# Agente de salud para mamá — Diseño

Fecha: 2026-11-23

## Intención

El usuario quiere cuidar a su mamá a distancia. Ella tiene un **iPad 2**; la
app le pregunta cada cierto tiempo cómo se siente, le pide una foto, y el
usuario se entera desde su teléfono (alerta inmediata) y puede revisar el
historial cuando quiera.

## Objetivos

- El iPad de la mamá pregunta "¿Cómo te sientes?" según un horario
  (por defecto cada 2 h entre 09:00 y 21:00), en pantalla y en voz alta.
- Ella responde con 3 botones grandes: 😀 Bien / 😐 Más o menos / 😟 Mal.
- Después de responder, se le ofrece "📷 Sacar foto" (opcional, puede omitir).
- Cada respuesta llega al usuario por **Telegram** (texto + foto).
- **Alertas**: si responde "Mal", o si no responde en 30 min, o si el iPad
  deja de conectarse (> 30 min sin señal en horario activo).
- **Página de historial** privada para el usuario: respuestas y fotos por
  día, estado del iPad (última conexión), y ajuste del horario/frecuencia.

## No-objetivos

- Video en vivo (el iPad 2 / iOS 9 no lo permite en web; para eso, FaceTime).
- Fotos automáticas sin que ella toque nada (iOS 9 Safari no lo permite;
  además, ella debe saber cuándo se toma una foto).
- Diagnóstico médico o análisis de expresión facial.
- Soporte del iPad 1 (no tiene cámara).

## Anti-objetivos (sería un fracaso aunque "funcione")

- Que la mamá se sienta vigilada o confundida: la interfaz debe ser
  muy simple, letra grande, sin menús ni texto técnico.
- Falsas alarmas constantes (p. ej. alertas de "sin respuesta" de noche).
- Fotos de la mamá accesibles públicamente.

## Restricciones

- **iPad 2 = iOS 9.3.5, Safari 9**: solo ES5 (sin `fetch`, sin funciones
  flecha, sin `let/const`), usar `XMLHttpRequest`. Sin `getUserMedia`;
  la foto se toma con `<input type="file" accept="image/*" capture>`.
- **TLS en iOS 9**: muchos certificados modernos (Let's Encrypt actual) no
  son confiables en iOS 9. La página del iPad debe poder servirse por
  **HTTP simple** como respaldo. Esto se verifica primero (paso 0).
- La página solo funciona mientras está abierta: el iPad queda enchufado,
  con Bloqueo automático = Nunca y Acceso guiado activado.
- Sin costo mensual.

## Enfoques considerados

1. **Telegram + página de historial con servidor Python (elegido, el
   usuario pidió "todo").** Un servidor pequeño recibe respuestas y fotos,
   las guarda, reenvía a Telegram y sirve la página de historial.
2. Solo Telegram, llamando a la API de Telegram directo desde el iPad:
   más simple, pero deja el token del bot dentro del iPad, depende de CORS
   y TLS modernos en iOS 9, y no da historial ni detección de "iPad apagado".
3. WhatsApp: ideal para el usuario, pero su API de mensajes automáticos
   es pagada y burocrática. Descartado.

## Decisiones de construcción (decididas por Claude, corregibles)

- **Servidor en Python + Flask** (el usuario ya conoce Python por
  `kino.py`), alojado gratis en **PythonAnywhere**: permite HTTP simple
  (resuelve el riesgo de TLS en iOS 9) y tiene `api.telegram.org` en su
  lista de sitios permitidos. Nota: la cuenta gratis pide entrar a
  "renovar" la app cada 3 meses.
- **Almacenamiento**: SQLite para respuestas/configuración; fotos como
  archivos en disco (reducidas en el iPad a ~640 px antes de subir).
- **Telegram**: el usuario crea un bot con @BotFather; token y chat_id
  quedan en variables de entorno del servidor, nunca en el iPad.
- **Revisiones periódicas** ("no respondió", "iPad sin señal"): un endpoint
  `/revisar` llamado cada 10 min por un servicio gratuito externo
  (cron-job.org). Además, el propio iPad avisa "sin respuesta" a los 30 min.
- **Privacidad**: la página del iPad usa una clave larga en la URL
  (`/ipad/<clave>`); la página de historial usa otra clave distinta
  (`/historial/<clave>`). Las fotos solo se sirven a través de rutas con clave.
- Código en la carpeta `agente-salud/` de este repositorio.

## Componentes

- `ipad.html` (+ JS ES5): pantalla de reposo (hora, "Todo bien 💛"),
  pantalla de pregunta con 3 botones, pantalla de foto, confirmación.
  Lee el horario desde el servidor; envía latido cada 5 min.
  Voz con `speechSynthesis` (es-ES/es-CL) + sonido; si iOS bloquea audio
  hasta un toque, se pide un toque inicial al abrir ("Toca para empezar").
- `servidor.py` (Flask): `/api/respuesta`, `/api/foto`, `/api/latido`,
  `/api/config`, `/revisar`, `/historial/<clave>`, `/ipad/<clave>`.
- `historial.html`: lista por día, miniaturas, estado del iPad,
  formulario de horario (inicio, fin, cada cuántas horas).
- `LEEME.md`: instrucciones paso a paso en español: crear bot, publicar en
  PythonAnywhere, configurar cron-job.org, preparar el iPad (Acceso guiado,
  Bloqueo automático, añadir a pantalla de inicio).

## Paso 0 (spike obligatorio)

Antes de todo: una página mínima en PythonAnywhere que, desde el iPad 2,
haga una petición XHR y suba una foto con `capture`. Confirma HTTP/TLS,
cámara y voz en el aparato real. Si falla, se vuelve a conversar.

## Pruebas

- Pruebas automáticas del servidor (pytest): guardar respuesta, foto,
  reglas de alertas (horario, "Mal", sin respuesta, sin señal), Telegram
  simulado.
- La página del iPad se prueba en un navegador moderno y se revisa que no
  use sintaxis posterior a ES5; la prueba final es en el iPad real (usuario).

## Queda al constructor

- Textos exactos y diseño visual (grande, alto contraste, amable).
- Formato exacto de los mensajes de Telegram.
