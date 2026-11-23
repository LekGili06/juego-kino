"""Servidor del agente de salud: recibe respuestas del iPad, avisa por Telegram y muestra el historial."""
import hmac
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, abort, jsonify, request, send_from_directory

import db
from alertas import MARGEN, Horario, en_horario, pregunta_actual, pregunta_vencida, proxima_pregunta
from telegram import Telegram, TelegramNulo

AQUI = os.path.dirname(os.path.abspath(__file__))
MAX_FOTO = 5 * 1024 * 1024
VENTANA_PENDIENTE = timedelta(hours=1)

ESTADOS = {
    "bien": ("😀", "Bien"),
    "regular": ("😐", "Más o menos"),
    "mal": ("😟", "Mal"),
    "sin_respuesta": ("⚠️", "Sin respuesta"),
}
DEFECTOS = {"inicio": "09:00", "fin": "21:00", "cada_horas": "2"}


def _hhmm(ts: datetime) -> str:
    return ts.strftime("%H:%M")


def _es_imagen(datos: bytes) -> bool:
    return datos.startswith(b"\xff\xd8") or datos.startswith(b"\x89PNG")


def crear_app(ajustes, telegram=None, reloj=None) -> Flask:
    app = Flask(__name__, static_folder=os.path.join(AQUI, "static"),
                template_folder=os.path.join(AQUI, "templates"))
    app.config["MAX_CONTENT_LENGTH"] = MAX_FOTO + 1024 * 1024

    zona = ZoneInfo(ajustes.get("ZONA") or "America/Santiago")
    clave_ipad = ajustes.get("CLAVE_IPAD") or ""
    clave_historial = ajustes.get("CLAVE_HISTORIAL") or ""
    if not clave_ipad or not clave_historial:
        raise RuntimeError("Faltan CLAVE_IPAD y/o CLAVE_HISTORIAL")
    datos_dir = ajustes.get("DATOS_DIR") or os.path.join(AQUI, "datos")
    fotos_dir = os.path.join(datos_dir, "fotos")
    os.makedirs(fotos_dir, exist_ok=True)

    conn = db.conectar(os.path.join(datos_dir, "agente.db"))
    app.config["DB"] = conn
    app.config["FOTOS_DIR"] = fotos_dir
    if telegram is None:
        token, chat = ajustes.get("TELEGRAM_TOKEN"), ajustes.get("TELEGRAM_CHAT_ID")
        telegram = Telegram(token, chat) if token and chat else TelegramNulo()
    ahora = reloj or (lambda: datetime.now(zona))

    def clave_ok(dada, esperada):
        return hmac.compare_digest((dada or "").encode(), esperada.encode())

    def exigir_ipad():
        if not clave_ok(request.args.get("clave"), clave_ipad):
            abort(403)

    def horario() -> Horario:
        a = {k: db.leer_ajuste(conn, k, v) for k, v in DEFECTOS.items()}
        return Horario(time.fromisoformat(a["inicio"]), time.fromisoformat(a["fin"]), int(a["cada_horas"]))

    def pendiente(t: datetime):
        p = pregunta_actual(t, horario())
        if p is None or t - p >= VENTANA_PENDIENTE or db.ultima_respuesta_desde(conn, p):
            return None
        return p

    # --- Páginas e iPad ---------------------------------------------------

    @app.route("/ipad/<clave>")
    def pagina_ipad(clave):
        if not clave_ok(clave, clave_ipad):
            abort(403)
        return send_from_directory(app.static_folder, "ipad.html")

    @app.route("/api/config")
    def api_config():
        exigir_ipad()
        t, h = ahora(), horario()
        p = pendiente(t)
        return jsonify(
            inicio=h.inicio.strftime("%H:%M"), fin=h.fin.strftime("%H:%M"), cada_horas=h.cada_horas,
            ahora=t.isoformat(), proxima=proxima_pregunta(t, h).isoformat(),
            pendiente=p.isoformat() if p else None,
        )

    @app.route("/api/latido", methods=["POST"])
    def api_latido():
        exigir_ipad()
        db.registrar_latido(conn, ahora())
        if db.leer_ajuste(conn, "alerta_senal", ""):
            db.guardar_ajuste(conn, "alerta_senal", "")
            telegram.texto("✅ El iPad de mamá volvió a conectarse")
        return jsonify(ok=True)

    @app.route("/api/respuesta", methods=["POST"])
    def api_respuesta():
        exigir_ipad()
        datos = request.get_json(silent=True) or {}
        estado = datos.get("estado")
        if estado not in ("bien", "regular", "mal"):
            abort(400)
        t = ahora()
        actual = pregunta_actual(t, horario())
        tarde = bool(actual) and db.leer_ajuste(conn, "alertado_pregunta", "") == actual.isoformat()
        i = db.guardar_respuesta(conn, estado, t, tarde=tarde)
        emoji, nombre = ESTADOS[estado]
        if estado == "mal":
            msg = "🚨 Mamá dice que se siente MAL — " + _hhmm(t)
        else:
            msg = emoji + " Mamá: " + nombre + " — " + _hhmm(t)
        telegram.texto(("(respondió tarde) " if tarde else "") + msg)
        return jsonify(ok=True, id=i)

    @app.route("/api/foto", methods=["POST"])
    def api_foto():
        exigir_ipad()
        archivo = request.files.get("foto")
        if archivo is None:
            abort(400)
        contenido = archivo.read(MAX_FOTO + 1)
        if len(contenido) > MAX_FOTO or not _es_imagen(contenido):
            abort(400)
        resp = db.obtener_respuesta(conn, request.args.get("id", type=int) or 0)
        if resp is None:
            abort(404)
        nombre = "%d.jpg" % resp["id"] if contenido.startswith(b"\xff\xd8") else "%d.png" % resp["id"]
        ruta = os.path.join(fotos_dir, nombre)
        with open(ruta, "wb") as f:
            f.write(contenido)
        db.adjuntar_foto(conn, resp["id"], nombre)
        nombre_estado = ESTADOS[resp["estado"]][1]
        telegram.foto(ruta, "📷 Mamá — " + nombre_estado + " — " + _hhmm(resp["ts"].astimezone(zona)))
        return jsonify(ok=True)

    # --- Revisión periódica (cron externo) -------------------------------

    @app.route("/revisar")
    def revisar():
        exigir_ipad()
        t, h = ahora(), horario()
        alertas = []
        vencida = pregunta_vencida(t, h)
        if (vencida and t - vencida <= VENTANA_PENDIENTE
                and db.leer_ajuste(conn, "alertado_pregunta", "") != vencida.isoformat()
                and not db.ultima_respuesta_desde(conn, vencida)):
            db.guardar_ajuste(conn, "alertado_pregunta", vencida.isoformat())
            db.guardar_respuesta(conn, "sin_respuesta", t)
            telegram.texto("⚠️ Mamá no respondió la pregunta de las " + _hhmm(vencida))
            alertas.append("sin_respuesta")
        latido = db.ultimo_latido(conn)
        if (en_horario(t, h) and not db.leer_ajuste(conn, "alerta_senal", "")
                and (latido is None or t - latido > MARGEN)):
            db.guardar_ajuste(conn, "alerta_senal", t.isoformat())
            if latido is None:
                telegram.texto("📵 El iPad de mamá todavía no se ha conectado")
            else:
                telegram.texto("📵 El iPad de mamá no se conecta desde las " + _hhmm(latido.astimezone(zona)))
            alertas.append("sin_senal")
        return jsonify(alertas=alertas)

    return app


if os.environ.get("CLAVE_IPAD"):
    app = crear_app(os.environ)
