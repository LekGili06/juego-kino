"""Servidor del agente de salud: recibe respuestas del iPad, avisa por Telegram y muestra el historial."""
import hmac
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory

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
    clave_revisar = ajustes.get("CLAVE_REVISAR") or ""
    if not clave_ipad or not clave_historial or not clave_revisar:
        raise RuntimeError("Faltan CLAVE_IPAD, CLAVE_HISTORIAL y/o CLAVE_REVISAR")
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
        if p is None or t - p >= VENTANA_PENDIENTE or db.respondida(conn, p):
            return None
        return p

    @app.after_request
    def privacidad(resp):
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/historial/"):
            resp.headers["Cache-Control"] = "private, no-store"
        return resp

    def leer_pregunta(texto, t):
        """La pregunta a la que responde el iPad; si no viene o es inválida, la actual."""
        try:
            p = datetime.fromisoformat(texto) if texto else None
        except (TypeError, ValueError):
            p = None
        if p is None or p.tzinfo is None or p > t or t - p > timedelta(days=2):
            return pregunta_actual(t, horario())
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
        uid = datos.get("uid") if isinstance(datos.get("uid"), str) else None
        if uid:
            previa = db.buscar_por_uid(conn, uid[:64])
            if previa:
                return jsonify(ok=True, id=previa["id"])
        t = ahora()
        pregunta = leer_pregunta(datos.get("pregunta"), t)
        tarde = bool(pregunta) and db.alertada(conn, pregunta)
        i = db.guardar_respuesta(conn, estado, t, tarde=tarde, pregunta=pregunta, uid=uid[:64] if uid else None)
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
        if not clave_ok(request.args.get("clave"), clave_revisar):
            abort(403)
        t, h = ahora(), horario()
        alertas = []
        vencida = pregunta_vencida(t, h)
        if (vencida and t - vencida <= VENTANA_PENDIENTE
                and not db.respondida(conn, vencida) and not db.alertada(conn, vencida)):
            db.guardar_respuesta(conn, "sin_respuesta", t, pregunta=vencida)
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

    # --- Historial (para el usuario) --------------------------------------

    def exigir_historial(clave):
        if not clave_ok(clave, clave_historial):
            abort(403)

    def estado_ipad(t):
        latido = db.ultimo_latido(conn)
        if latido is None:
            return "todavía no se ha conectado", False
        minutos = int((t - latido).total_seconds() // 60)
        if t - latido > MARGEN:
            return "Sin señal desde las " + _hhmm(latido.astimezone(zona)), False
        return "Conectado hace %d min" % max(minutos, 0), True

    def validar_horario(form):
        try:
            inicio = time.fromisoformat(form.get("inicio", ""))
            fin = time.fromisoformat(form.get("fin", ""))
            cada = int(form.get("cada_horas", ""))
        except ValueError:
            return None
        if not 1 <= cada <= 6 or inicio >= fin:
            return None
        return inicio.strftime("%H:%M"), fin.strftime("%H:%M"), str(cada)

    @app.route("/historial/<clave>", methods=["GET", "POST"])
    def historial(clave):
        exigir_historial(clave)
        error = None
        if request.method == "POST":
            valores = validar_horario(request.form)
            if valores:
                for k, v in zip(("inicio", "fin", "cada_horas"), valores):
                    db.guardar_ajuste(conn, k, v)
                return redirect(request.path)
            error = "No se pudo guardar: revisa que el inicio sea antes del fin y que la frecuencia sea de 1 a 6 horas."
        t, h = ahora(), horario()
        dias = []
        for r in db.listar_respuestas(conn, t - timedelta(days=14)):
            local = r["ts"].astimezone(zona)
            etiqueta = local.strftime("%d/%m/%Y")
            if not dias or dias[-1]["fecha"] != etiqueta:
                dias.append({"fecha": etiqueta, "respuestas": []})
            emoji, nombre = ESTADOS[r["estado"]]
            dias[-1]["respuestas"].append(dict(r, hora=_hhmm(local), emoji=emoji, nombre=nombre))
        texto_ipad, ok_ipad = estado_ipad(t)
        return render_template(
            "historial.html", dias=dias, clave=clave, error=error, texto_ipad=texto_ipad, ok_ipad=ok_ipad,
            inicio=h.inicio.strftime("%H:%M"), fin=h.fin.strftime("%H:%M"), cada_horas=h.cada_horas,
            proxima=_hhmm(proxima_pregunta(t, h)),
        )

    @app.route("/historial/<clave>/foto/<int:respuesta_id>")
    def historial_foto(clave, respuesta_id):
        exigir_historial(clave)
        r = db.obtener_respuesta(conn, respuesta_id)
        if r is None or not r["foto"]:
            abort(404)
        return send_from_directory(fotos_dir, r["foto"])

    return app


if os.environ.get("CLAVE_IPAD"):
    app = crear_app(os.environ)
