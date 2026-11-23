import io
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import db
from app import crear_app

Z = ZoneInfo("America/Santiago")
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


class TelegramFalso:
    def __init__(self, ok=True):
        self.textos, self.fotos, self.ok = [], [], ok

    def texto(self, m):
        self.textos.append(m)
        return self.ok

    def foto(self, ruta, leyenda):
        self.fotos.append((ruta, leyenda))
        return self.ok


class Reloj:
    def __init__(self):
        self.ahora = datetime(2026, 11, 23, 10, 32, tzinfo=Z)

    def poner(self, h, m=0):
        self.ahora = datetime(2026, 11, 23, h, m, tzinfo=Z)

    def __call__(self):
        return self.ahora


@pytest.fixture
def entorno(tmp_path):
    tg, reloj = TelegramFalso(), Reloj()
    app = crear_app(
        {"CLAVE_IPAD": "ki", "CLAVE_HISTORIAL": "kh", "ZONA": "America/Santiago", "DATOS_DIR": str(tmp_path)},
        telegram=tg, reloj=reloj,
    )
    return app.test_client(), tg, reloj, app


def responder(c, estado):
    return c.post("/api/respuesta?clave=ki", json={"estado": estado})


def test_clave_incorrecta(entorno):
    c, *_ = entorno
    assert c.post("/api/respuesta?clave=mala", json={"estado": "bien"}).status_code == 403
    assert c.get("/api/config").status_code == 403
    assert c.get("/ipad/mala").status_code == 403


def test_pagina_ipad(entorno):
    c, *_ = entorno
    assert c.get("/ipad/ki").status_code == 200


def test_config_por_defecto(entorno):
    c, _, reloj, _ = entorno
    reloj.poner(9, 20)
    j = c.get("/api/config?clave=ki").get_json()
    assert (j["inicio"], j["fin"], j["cada_horas"]) == ("09:00", "21:00", 2)
    assert j["proxima"].startswith("2026-11-23T11:00")
    reloj.poner(10, 32)
    assert c.get("/api/config?clave=ki").get_json()["pendiente"] is None
    reloj.poner(9, 20)
    j = c.get("/api/config?clave=ki").get_json()
    assert j["pendiente"].startswith("2026-11-23T09:00")


def test_respuesta_limpia_pendiente(entorno):
    c, _, reloj, _ = entorno
    reloj.poner(9, 20)
    responder(c, "bien")
    assert c.get("/api/config?clave=ki").get_json()["pendiente"] is None


def test_pendiente_dura_una_hora(entorno):
    c, _, reloj, _ = entorno
    reloj.poner(22, 1)
    assert c.get("/api/config?clave=ki").get_json()["pendiente"] is None
    reloj.poner(21, 59)
    assert c.get("/api/config?clave=ki").get_json()["pendiente"].startswith("2026-11-23T21:00")


def test_respuesta_bien(entorno):
    c, tg, _, app = entorno
    r = responder(c, "bien")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert tg.textos == ["😀 Mamá: Bien — 10:32"]


def test_respuesta_mal_alerta(entorno):
    c, tg, *_ = entorno
    responder(c, "mal")
    assert tg.textos == ["🚨 Mamá dice que se siente MAL — 10:32"]


def test_estado_invalido(entorno):
    c, tg, *_ = entorno
    assert responder(c, "feliz").status_code == 400
    assert c.post("/api/respuesta?clave=ki", data="x").status_code == 400
    assert tg.textos == []


def test_telegram_caido_igual_guarda(entorno):
    c, tg, *_ = entorno
    tg.ok = False
    r = responder(c, "regular")
    assert r.status_code == 200
    assert c.get("/api/config?clave=ki").get_json()["pendiente"] is None


def test_foto_valida(entorno, tmp_path):
    c, tg, *_ = entorno
    i = responder(c, "bien").get_json()["id"]
    r = c.post(f"/api/foto?clave=ki&id={i}", data={"foto": (io.BytesIO(JPEG), "f.jpg")})
    assert r.status_code == 200
    assert (tmp_path / "fotos" / f"{i}.jpg").read_bytes() == JPEG
    assert tg.fotos[0][1] == "📷 Mamá — Bien — 10:32"


def test_foto_invalida(entorno, tmp_path):
    c, tg, *_ = entorno
    i = responder(c, "bien").get_json()["id"]
    assert c.post(f"/api/foto?clave=ki&id={i}", data={"foto": (io.BytesIO(b"hola"), "f.jpg")}).status_code == 400
    grande = b"\xff\xd8" + b"0" * (5 * 1024 * 1024)
    assert c.post(f"/api/foto?clave=ki&id={i}", data={"foto": (io.BytesIO(grande), "f.jpg")}).status_code == 400
    assert c.post(f"/api/foto?clave=ki&id={i}").status_code == 400
    assert c.post(f"/api/foto?clave=ki&id=999", data={"foto": (io.BytesIO(JPEG), "f.jpg")}).status_code == 404
    assert tg.fotos == []


def test_revisar_sin_respuesta_una_vez(entorno):
    c, tg, reloj, _ = entorno
    c.post("/api/latido?clave=ki")
    reloj.poner(9, 30)
    assert c.get("/revisar?clave=ki").get_json()["alertas"] == ["sin_respuesta"]
    assert tg.textos == ["⚠️ Mamá no respondió la pregunta de las 09:00"]
    assert c.get("/revisar?clave=ki").get_json()["alertas"] == []
    assert len(tg.textos) == 1


def test_revisar_con_respuesta_no_alerta(entorno):
    c, tg, reloj, _ = entorno
    reloj.poner(9, 5)
    c.post("/api/latido?clave=ki")
    responder(c, "bien")
    reloj.poner(9, 31)
    assert c.get("/revisar?clave=ki").get_json()["alertas"] == []


def test_revisar_de_noche_no_alerta(entorno):
    c, tg, reloj, _ = entorno
    reloj.poner(23, 0)
    assert c.get("/revisar?clave=ki").get_json()["alertas"] == []
    assert tg.textos == []


def test_respuesta_tarde(entorno):
    c, tg, reloj, app = entorno
    reloj.poner(11, 0)
    c.post("/api/latido?clave=ki")
    reloj.poner(11, 30)
    c.get("/revisar?clave=ki")
    reloj.poner(11, 40)
    responder(c, "bien")
    assert tg.textos[-1] == "(respondió tarde) 😀 Mamá: Bien — 11:40"
    with app.app_context():
        filas = db.listar_respuestas(app.config["DB"], datetime(2026, 11, 23, tzinfo=Z))
    assert [(f["estado"], f["tarde"]) for f in filas] == [("bien", True), ("sin_respuesta", False)]


def test_sin_senal_y_reconexion(entorno):
    c, tg, reloj, _ = entorno
    reloj.poner(9, 0)
    c.post("/api/latido?clave=ki")
    responder(c, "bien")
    reloj.poner(9, 31)
    assert c.get("/revisar?clave=ki").get_json()["alertas"] == ["sin_senal"]
    assert tg.textos[-1] == "📵 El iPad de mamá no se conecta desde las 09:00"
    assert c.get("/revisar?clave=ki").get_json()["alertas"] == []
    c.post("/api/latido?clave=ki")
    assert tg.textos[-1] == "✅ El iPad de mamá volvió a conectarse"
    c.post("/api/latido?clave=ki")
    assert tg.textos.count("✅ El iPad de mamá volvió a conectarse") == 1
