"""Página de prueba (desechable) para comprobar el iPad 2: conexión, voz y cámara."""
import os

from flask import Flask, jsonify, request, send_from_directory

AQUI = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)


@app.route("/")
def inicio():
    return send_from_directory(os.path.join(AQUI, "static"), "prueba.html")


@app.route("/eco", methods=["POST"])
def eco():
    return jsonify(ok=True, bytes=len(request.get_data()))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
