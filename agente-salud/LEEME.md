# Agente de salud para mamá 💛

El iPad 2 de mamá le pregunta cada cierto tiempo **"¿Cómo te sientes?"**.
Ella toca 😀 Bien, 😐 Más o menos o 😟 Mal y, si quiere, se saca una foto.
Tú recibes cada respuesta en **Telegram**, con alertas si dice "Mal", si no
responde en 30 minutos o si el iPad deja de conectarse. Además tienes una
**página de historial** con todas las respuestas y fotos.

Todo es gratis. Necesitas unos 45 minutos la primera vez.

---

## Paso 1 — Crear tu bot de Telegram

1. Instala **Telegram** en tu teléfono.
2. Busca **@BotFather**, escríbele `/newbot` y sigue las instrucciones
   (por ejemplo, nombre: `Mamá Salud`; usuario: `mama_salud_tuNombre_bot`).
3. BotFather te da un **token** parecido a `123456789:AAH...`. Guárdalo; es secreto.
4. Busca tu bot nuevo en Telegram y escríbele cualquier cosa, por ejemplo "hola".
5. En un navegador abre (cambiando `TU_TOKEN`):
   `https://api.telegram.org/botTU_TOKEN/getUpdates`
   Busca `"chat":{"id":` y copia ese número: es tu **chat_id**.

## Paso 2 — Crear tus dos claves

Son contraseñas largas que van dentro de los enlaces. Genera tres distintas
(ejecuta el comando tres veces):

```
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

- **CLAVE_IPAD**: va en el enlace del iPad.
- **CLAVE_HISTORIAL**: va en tu enlace del historial. No la compartas.
- **CLAVE_REVISAR**: solo para la revisión automática del Paso 5.

## Paso 3 — Publicar el servidor en PythonAnywhere

1. Crea una cuenta gratis en <https://www.pythonanywhere.com> (plan "Beginner").
   Tu sitio quedará en `http://TU_USUARIO.pythonanywhere.com`.
2. Pestaña **Files**: crea la carpeta `agente-salud` y sube estos archivos
   respetando las carpetas: `app.py`, `db.py`, `alertas.py`, `telegram.py`,
   `prueba.py`, `static/ipad.html`, `static/ipad.js`, `static/prueba.html`,
   `templates/historial.html`.
   (O, en una consola **Bash**: `git clone` de este repositorio.)
3. Pestaña **Web** → **Add a new web app** → **Manual configuration** → **Python 3.10** (o más nuevo).
4. En **Code**, abre el archivo **WSGI configuration file**, borra todo y pega
   (cambia los valores):

   ```python
   import os, sys
   sys.path.insert(0, "/home/TU_USUARIO/agente-salud")

   os.environ["TELEGRAM_TOKEN"] = "123456789:AAH..."
   os.environ["TELEGRAM_CHAT_ID"] = "123456789"
   os.environ["CLAVE_IPAD"] = "clave-larga-del-ipad"
   os.environ["CLAVE_HISTORIAL"] = "otra-clave-larga"
   os.environ["CLAVE_REVISAR"] = "tercera-clave-larga"
   os.environ["ZONA"] = "America/Santiago"
   os.environ["DATOS_DIR"] = "/home/TU_USUARIO/agente-salud/datos"

   from app import app as application
   ```

5. En **Security**, deja **Force HTTPS** en **desactivado** (el iPad 2 a veces
   no acepta conexiones seguras modernas; ver Paso 4). Solo el iPad usará
   `http`; tú abrirás tu historial con `https`.
6. Botón verde **Reload**.

### Primero: la prueba en el iPad (Paso 4)

Antes de configurar todo, comprueba que el iPad 2 se lleva bien con el servidor:

1. En el archivo WSGI, cambia temporalmente la última línea por
   `from prueba import app as application` y presiona **Reload**.
2. En el iPad abre Safari y entra a `http://TU_USUARIO.pythonanywhere.com`.
3. Toca los tres botones. Debes ver ✅ en **Conexión**, escuchar la **voz**
   y, en **Cámara**, sacar una foto y ver ✅.
   Cuando todo esté instalado, revisa también que la primera foto te llegue
   **derecha** a Telegram (el iPad 2 a veces las gira); si llega girada, avísame.
4. Prueba también con `https://` al inicio. Si `https` falla pero `http`
   funciona, usa siempre `http` en el iPad.
5. Vuelve a poner `from app import app as application` y **Reload**.

Si algo sale ❌, anota el mensaje y avísame antes de seguir.

## Paso 5 — Revisión automática cada 10 minutos

Esto es lo que detecta "no respondió" y "el iPad no se conecta".

1. Crea una cuenta gratis en <https://cron-job.org>.
2. **Create cronjob**:
   - URL: `https://TU_USUARIO.pythonanywhere.com/revisar?clave=CLAVE_REVISAR`
   - Horario: **cada 10 minutos**.
3. Guarda.

## Paso 6 — Preparar el iPad de mamá

1. Enchúfalo al cargador: debe quedar **siempre enchufado**.
2. **Ajustes → General → Bloqueo automático → Nunca.**
3. **Ajustes → General → Accesibilidad → Acceso guiado → Activar** y pon un código
   que solo tú sepas.
4. En Safari abre `http://TU_USUARIO.pythonanywhere.com/ipad/CLAVE_IPAD`.
5. Toca el botón de compartir → **Añadir a pantalla de inicio**. Ábrela desde ese ícono.
6. Toca **"Toca para empezar 💛"** (necesario para que funcione la voz).
7. Presiona **3 veces el botón de inicio** → **Iniciar** el Acceso guiado.
   Así el iPad queda fijo en la app.
8. Sube el volumen.

Si el iPad se reinicia o se corta la luz, repite los pasos 6 y 7.

## Paso 7 — Tu historial

Guarda en tu teléfono este enlace (agrégalo a la pantalla de inicio).
Usa siempre **https** (con la "s"): así nadie en la misma red Wi-Fi puede
ver tu clave ni las fotos de mamá.

`https://TU_USUARIO.pythonanywhere.com/historial/CLAVE_HISTORIAL`

Ahí ves si el iPad está conectado, las respuestas y fotos de los últimos
14 días, y puedes cambiar el horario (desde, hasta y cada cuántas horas).

## Mantenimiento

- **Cada 3 meses** PythonAnywhere te enviará un correo: entra a la pestaña **Web**
  y presiona **"Run until 3 months from today"**. Si no, el sitio se apaga.
- Las fotos quedan en `agente-salud/datos/fotos`. La cuenta gratis tiene 512 MB
  (alcanza para varios miles de fotos).

## Qué te llega a Telegram

| Situación | Mensaje |
|---|---|
| Responde bien | 😀 Mamá: Bien — 11:02 |
| Responde mal | 🚨 Mamá dice que se siente MAL — 11:02 |
| Se saca una foto | 📷 Mamá — Bien — 11:02 (con la foto) |
| No responde en 30 min | ⚠️ Mamá no respondió la pregunta de las 11:00 |
| Responde después de esa alerta | (respondió tarde) 😀 Mamá: Bien — 11:40 |
| El iPad no se conecta en 30 min | 📵 El iPad de mamá no se conecta desde las 10:15 |
| El iPad vuelve | ✅ El iPad de mamá volvió a conectarse |

La alerta de "sin señal" solo se envía dentro del horario de preguntas. La de
"no respondió" puede llegar hasta una hora después de la última pregunta
(por ejemplo, entre 21:30 y 22:00); después de eso, de noche no llega nada.

## Para desarrolladores

```
pip install -r requirements.txt
python -m pytest tests          # pruebas del servidor
sh tests/test_es5.sh            # el JS del iPad debe ser ES5 (Safari 9)
```
