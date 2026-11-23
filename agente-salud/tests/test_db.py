from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import db

Z = ZoneInfo("America/Santiago")


def t(h, m=0):
    return datetime(2026, 11, 23, h, m, tzinfo=Z)


def test_guardar_y_listar():
    c = db.conectar(":memory:")
    db.guardar_respuesta(c, "bien", t(9))
    db.guardar_respuesta(c, "mal", t(11))
    filas = db.listar_respuestas(c, t(0))
    assert [f["estado"] for f in filas] == ["mal", "bien"]
    assert filas[0]["ts"] == t(11)
    assert filas[0]["tarde"] is False
    assert filas[0]["foto"] is None


def test_listar_respeta_desde():
    c = db.conectar(":memory:")
    db.guardar_respuesta(c, "bien", t(9) - timedelta(days=20))
    db.guardar_respuesta(c, "bien", t(9))
    assert len(db.listar_respuestas(c, t(0))) == 1


def test_adjuntar_foto():
    c = db.conectar(":memory:")
    i = db.guardar_respuesta(c, "bien", t(9))
    db.adjuntar_foto(c, i, "1.jpg")
    assert db.obtener_respuesta(c, i)["foto"] == "1.jpg"
    assert db.obtener_respuesta(c, 999) is None


def test_ultima_respuesta_ignora_sin_respuesta():
    c = db.conectar(":memory:")
    db.guardar_respuesta(c, "bien", t(9, 5))
    db.guardar_respuesta(c, "sin_respuesta", t(11, 30))
    assert db.ultima_respuesta_desde(c, t(9))["estado"] == "bien"
    assert db.ultima_respuesta_desde(c, t(11)) is None


def test_latido():
    c = db.conectar(":memory:")
    assert db.ultimo_latido(c) is None
    db.registrar_latido(c, t(9))
    db.registrar_latido(c, t(9, 5))
    assert db.ultimo_latido(c) == t(9, 5)


def test_ajustes_defecto_y_guardado():
    c = db.conectar(":memory:")
    assert db.leer_ajuste(c, "inicio", "09:00") == "09:00"
    db.guardar_ajuste(c, "inicio", "10:00")
    db.guardar_ajuste(c, "inicio", "08:00")
    assert db.leer_ajuste(c, "inicio", "09:00") == "08:00"
