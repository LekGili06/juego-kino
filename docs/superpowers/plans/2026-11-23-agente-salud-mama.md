# Agente de salud para mamá — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un servidor Flask + página para iPad 2 que pregunta a la mamá cómo se siente, recibe foto opcional, avisa al usuario por Telegram y muestra un historial privado.

**Architecture:** Flask con SQLite (`db.py`), reglas de horario/alertas como funciones puras (`alertas.py`), cliente Telegram inyectable (`telegram.py`), y `app.py` que une todo. La página del iPad es HTML + JS ES5 estático que habla con la API por XHR. Un cron externo llama `/revisar` cada 10 min.

**Tech Stack:** Python 3.10+, Flask 3, requests, pytest; JS ES5 (verificado con acorn `ecmaVersion: 5`).

**Spec:** `docs/superpowers/specs/2026-11-23-agente-salud-mama-design.md`

## Global Constraints

- Todo vive en `agente-salud/`. Textos visibles en español.
- JS del iPad: **solo ES5** (sin `let/const`, flechas, `fetch`, template strings, `class`). Peticiones con `XMLHttpRequest`. Foto con `<input type="file" accept="image/*" capture="user">`.
- El iPad nunca conoce el token de Telegram.
- Zona horaria: `America/Santiago` (configurable por variable `ZONA`).
- Horario por defecto: inicio `09:00`, fin `21:00`, cada `2` horas → preguntas a 09,11,13,15,17,19,21.
- Estados de respuesta: `"bien"`, `"regular"`, `"mal"`, `"sin_respuesta"`.
- Alertas: "mal" inmediata; sin respuesta 30 min después de una pregunta; sin señal si último latido > 30 min dentro del horario (una sola alerta hasta que vuelva la señal).
- Variables de entorno: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `CLAVE_IPAD`, `CLAVE_HISTORIAL`, `ZONA`, `DATOS_DIR`.
- Fotos reducidas en el iPad a máx. 640 px de lado (canvas, JPEG 0.7) antes de subir.

**Desviación respecto del spec (decisión del planificador):** la alerta "sin respuesta" la decide solo el servidor en `/revisar` (no el iPad), para evitar alertas duplicadas.

## Review Focus

1. Respuesta que llega justo después de los 30 min (la mamá contestó tarde) → no debe quedar marcada "sin_respuesta" *y* respondida sin aviso; se registra la respuesta y Telegram dice "respondió tarde".
2. `/revisar` llamado varias veces seguidas → nunca repite la misma alerta.
3. Fuera de horario (noche) → ninguna alerta de sin respuesta ni sin señal.
4. Telegram caído / token inválido → la respuesta igual se guarda y la API responde 200 al iPad.
5. Foto enorme o no-imagen subida → se rechaza con 400 sin romper; respuesta previa intacta.

---

### Task 0: Página de prueba para el iPad 2 (spike)

**Files:**
- Create: `agente-salud/prueba.py`, `agente-salud/static/prueba.html`, `agente-salud/requirements.txt`

Throwaway, sin tests. `prueba.py` es un Flask mínimo: `GET /` sirve `prueba.html`; `POST /eco` devuelve JSON `{"ok": true, "bytes": <tamaño del cuerpo>}`. `prueba.html` (ES5) muestra tres botones: "Probar conexión" (XHR a `/eco`), "Probar voz" (`speechSynthesis` dice "Hola, ¿cómo te sientes?"), "Probar cámara" (input capture → redimensiona en canvas → POST a `/eco`), y escribe en pantalla el resultado de cada uno en letra grande.

- [ ] **Step 1:** Escribir `requirements.txt` (`flask>=3`, `requests`, `pytest`), `prueba.py`, `prueba.html`.
- [ ] **Step 2:** `cd agente-salud && python prueba.py` y abrir con Playwright; los tres botones no lanzan errores de JS. `npx acorn --ecma5 --silent` sobre el `<script>` extraído: sin errores.
- [ ] **Step 3:** Commit `spike: página de prueba para iPad 2`. **El usuario la publica y la prueba en el iPad (HTTP y HTTPS); se decide con eso.**

### Task 1: Base de datos

**Files:** Create `agente-salud/db.py`, `agente-salud/tests/test_db.py`

**Interfaces — Produces:**
- `conectar(ruta: str) -> sqlite3.Connection` (crea tablas `respuestas(id, ts, estado, foto, tarde)`, `latidos(ts)`, `ajustes(clave, valor)`; `row_factory = sqlite3.Row`)
- `guardar_respuesta(conn, estado: str, ts: datetime, tarde: bool=False) -> int`
- `adjuntar_foto(conn, respuesta_id: int, nombre_archivo: str) -> None`
- `listar_respuestas(conn, desde: datetime) -> list[dict]` (más recientes primero)
- `ultima_respuesta_desde(conn, desde: datetime) -> dict | None` (excluye `sin_respuesta`)
- `registrar_latido(conn, ts: datetime) -> None`; `ultimo_latido(conn) -> datetime | None`
- `leer_ajuste(conn, clave: str, defecto: str) -> str`; `guardar_ajuste(conn, clave: str, valor: str) -> None`
- Fechas guardadas como ISO 8601 con zona.

- [ ] **Step 1:** Tests: `test_guardar_y_listar` (2 respuestas, orden desc, campos `estado`, `ts`), `test_adjuntar_foto`, `test_ultima_respuesta_ignora_sin_respuesta`, `test_latido`, `test_ajustes_defecto_y_guardado`. Usar `conectar(":memory:")`.
- [ ] **Step 2:** `pytest agente-salud/tests/test_db.py -v` → FAIL (módulo no existe).
- [ ] **Step 3:** Implementar `db.py`.
- [ ] **Step 4:** Tests PASS. Commit `feat: base de datos del agente de salud`.

### Task 2: Reglas de horario y alertas

**Files:** Create `agente-salud/alertas.py`, `agente-salud/tests/test_alertas.py`

**Interfaces — Produces:**
- `Horario` (dataclass): `inicio: time`, `fin: time`, `cada_horas: int`
- `horas_de_pregunta(dia: date, h: Horario, zona: ZoneInfo) -> list[datetime]`
- `en_horario(ahora: datetime, h: Horario) -> bool`
- `pregunta_vencida(ahora: datetime, h: Horario) -> datetime | None` — la pregunta más reciente de hoy cuya hora + 30 min ≤ ahora, o None.
- `proxima_pregunta(ahora: datetime, h: Horario) -> datetime` (puede ser mañana)
- `MARGEN = timedelta(minutes=30)`

- [ ] **Step 1:** Tests: `horas_de_pregunta` con defecto → `[9,11,13,15,17,19,21]`; con `cada_horas=3` → `[9,12,15,18,21]`; `en_horario` a las 08:59 False / 09:00 True / 21:30 False; `pregunta_vencida` a 11:29 → 09:00, a 11:30 → 11:00, a 08:00 → None; `proxima_pregunta` a 21:10 → mañana 09:00.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS. Commit `feat: reglas de horario`.

### Task 3: Cliente Telegram

**Files:** Create `agente-salud/telegram.py`, `agente-salud/tests/test_telegram.py`

**Interfaces — Produces:**
- `class Telegram(token: str, chat_id: str, post=requests.post)`
  - `texto(mensaje: str) -> bool` → `POST https://api.telegram.org/bot<token>/sendMessage` con `chat_id`, `text`
  - `foto(ruta: str, leyenda: str) -> bool` → `sendPhoto` multipart
  - Nunca lanza: cualquier excepción o status ≠ 200 → `False` (y se registra con `logging`).
- `class TelegramNulo` con los mismos métodos, devuelve `True` (para cuando no hay token).

- [ ] **Step 1:** Tests con `post` falso: URL y datos correctos; status 500 → False; excepción → False.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS. Commit `feat: cliente Telegram`.

### Task 4: API del servidor

**Files:** Create `agente-salud/app.py`, `agente-salud/tests/test_app.py`, `agente-salud/tests/conftest.py`

**Interfaces — Consumes:** Tasks 1–3. **Produces:**
- `crear_app(ajustes: dict, telegram=None, reloj=None) -> Flask` — `ajustes` con `CLAVE_IPAD`, `CLAVE_HISTORIAL`, `ZONA`, `DATOS_DIR`; `reloj()` devuelve `datetime` aware (por defecto ahora en `ZONA`). Al final del archivo: `app = crear_app(os.environ)` para PythonAnywhere.
- Rutas (todas las de API exigen `?clave=<CLAVE_IPAD>`, si no → 403):
  - `GET /ipad/<clave>` → `static/ipad.html` (Task 5)
  - `GET /api/config` → `{"inicio":"09:00","fin":"21:00","cada_horas":2,"ahora":"<iso>","proxima":"<iso>"}`
  - `POST /api/latido` → `{"ok":true}`; si había alerta de sin señal activa, envía "✅ El iPad volvió a conectarse" y la limpia.
  - `POST /api/respuesta` JSON `{"estado":"bien|regular|mal"}` → `{"ok":true,"id":N}`; estado inválido → 400. Telegram: `"😀 Mamá: Bien — 10:32"` / `"😐 … Más o menos"` / `"🚨 Mamá dice que se siente MAL — 10:32"`. Si ya se había alertado sin respuesta para la pregunta actual → guarda `tarde=True` y antepone "(respondió tarde) ".
  - `POST /api/foto?id=N` multipart campo `foto` → guarda `DATOS_DIR/fotos/<id>.jpg`, envía foto a Telegram con leyenda del estado. Máx. 5 MB, debe empezar con bytes JPEG/PNG; si no → 400. `id` inexistente → 404.
  - `GET /revisar?clave=<CLAVE_IPAD>` → aplica: (a) `pregunta_vencida` sin respuesta desde esa hora y no alertada (ajuste `alertado_pregunta` = iso) → guarda `sin_respuesta`, Telegram "⚠️ Mamá no respondió la pregunta de las 11:00"; (b) `en_horario` y último latido > 30 min (o nunca) y ajuste `alerta_senal` vacío → Telegram "📵 El iPad de mamá no se conecta desde las HH:MM", marca ajuste. Responde `{"alertas":[...]}`.
  - `GET|POST /historial/<clave>` → Task 6. `GET /historial/<clave>/foto/<id>` → la foto o 404.

- [ ] **Step 1:** Tests (con `reloj` fijo y `Telegram` falso que registra mensajes): clave incorrecta → 403; respuesta válida guarda y envía texto; "mal" envía 🚨; estado inválido → 400; Telegram que devuelve False → igual 200 (Review Focus 4); foto válida se guarda y se envía; foto no-imagen o > 5 MB → 400 (Review Focus 5); `/revisar` a las 11:30 sin respuesta → 1 alerta, segunda llamada → 0 alertas (Review Focus 2); `/revisar` a las 23:00 sin latido → 0 alertas (Review Focus 3); respuesta a las 11:40 tras alerta → `tarde=True` y mensaje "respondió tarde" (Review Focus 1); latido limpia alerta de señal y avisa reconexión.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS. Commit `feat: API del agente de salud`.

### Task 5: Página del iPad

**Files:** Create `agente-salud/static/ipad.html`, `agente-salud/static/ipad.js`, `agente-salud/tests/test_es5.sh`

**Interfaces — Consumes:** rutas de Task 4. La clave se lee de la URL (`/ipad/<clave>`).

Pantallas (una visible a la vez, letra ≥ 40 px, alto contraste, fondo cálido):
1. **Inicio:** "Toca para empezar 💛" (desbloquea voz/sonido en iOS).
2. **Reposo:** hora grande, "Todo bien 💛", "Próxima pregunta: 11:00".
3. **Pregunta:** "¿Cómo te sientes?" + botones 😀 Bien / 😐 Más o menos / 😟 Mal. Se dice en voz alta (`es-CL`, si no `es-ES`, si no cualquiera) y se repite cada 5 min mientras no conteste.
4. **Foto:** "¿Te sacas una foto?" botones "📷 Sacar foto" / "Ahora no".
5. **Gracias:** "¡Gracias! 💛" 5 s → Reposo.

Lógica: `GET /api/config` al iniciar y cada 30 min; latido cada 5 min; un `setInterval` de 30 s compara la hora con `proxima` y muestra Pregunta. Errores de red: reintentar cada 30 s guardando la respuesta pendiente en `localStorage`; mostrar un punto rojo pequeño en la esquina (sin texto alarmante).

- [ ] **Step 1:** `test_es5.sh`: `npx --yes acorn@8 --ecma5 --silent static/ipad.js` → exit 0.
- [ ] **Step 2:** Implementar. **Step 3:** test ES5 PASS; con Playwright y `reloj` del servidor de prueba, simular: pregunta aparece, tocar "Mal" → POST correcto; subir foto → POST correcto. Captura de pantalla de cada pantalla para revisión. Commit `feat: página del iPad`.

### Task 6: Página de historial

**Files:** Create `agente-salud/templates/historial.html`; Modify `agente-salud/app.py`; Test `agente-salud/tests/test_historial.py`

- `GET /historial/<CLAVE_HISTORIAL>`: estado del iPad ("Conectado hace 3 min" / "Sin señal desde 10:15"), últimos 14 días agrupados por día con hora, emoji, "(tarde)", miniatura de foto; formulario de horario.
- `POST /historial/<clave>` con `inicio`, `fin`, `cada_horas` (1–6, inicio < fin) → guarda ajustes y redirige; inválido → mensaje de error en la página.
- Diseño moderno simple, apto para teléfono.

- [ ] **Step 1:** Tests: clave mala → 403; muestra respuestas y emoji; guarda horario válido y `/api/config` lo refleja; `cada_horas=0` o `inicio>=fin` → error, horario sin cambio.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS. Commit `feat: historial`.

### Task 7: Instrucciones de instalación

**Files:** Create `agente-salud/LEEME.md`

Paso a paso en español, para alguien que no es experto: (1) crear bot con @BotFather y obtener `chat_id`; (2) crear cuenta PythonAnywhere, subir carpeta, crear web app Flask, variables de entorno, desactivar "Force HTTPS"; (3) generar claves largas (`python -c "import secrets;print(secrets.token_urlsafe(16))"`); (4) cron-job.org cada 10 min a `/revisar`; (5) preparar el iPad: abrir `/ipad/<clave>`, "Añadir a pantalla de inicio", Ajustes → Pantalla → Bloqueo automático: Nunca, Accesibilidad → Acceso guiado; dejar enchufado; (6) renovar PythonAnywhere cada 3 meses.

- [ ] **Step 1:** Escribir. **Step 2:** Correr toda la suite `pytest agente-salud -v` → PASS. Commit `docs: instrucciones`.
