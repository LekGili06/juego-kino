import io

from test_app import JPEG, entorno, responder  # noqa: F401 (fixture)


def test_historial_clave_mala(entorno):
    c, *_ = entorno
    assert c.get("/historial/ki").status_code == 403
    assert c.get("/historial/mala/foto/1").status_code == 403


def test_historial_muestra_respuestas(entorno):
    c, *_ = entorno
    i = responder(c, "mal").get_json()["id"]
    c.post(f"/api/foto?clave=ki&id={i}", data={"foto": (io.BytesIO(JPEG), "f.jpg")})
    html = c.get("/historial/kh").get_data(as_text=True)
    assert "😟" in html and "10:32" in html
    assert f"/historial/kh/foto/{i}" in html
    assert c.get(f"/historial/kh/foto/{i}").data == JPEG
    assert c.get("/historial/kh/foto/999").status_code == 404


def test_historial_estado_ipad(entorno):
    c, _, reloj, _ = entorno
    assert "todavía no se ha conectado" in c.get("/historial/kh").get_data(as_text=True)
    c.post("/api/latido?clave=ki")
    reloj.poner(10, 35)
    assert "Conectado hace 3 min" in c.get("/historial/kh").get_data(as_text=True)
    reloj.poner(11, 30)
    assert "Sin señal desde las 10:32" in c.get("/historial/kh").get_data(as_text=True)


def test_guardar_horario(entorno):
    c, *_ = entorno
    r = c.post("/historial/kh", data={"inicio": "08:00", "fin": "20:00", "cada_horas": "3"})
    assert r.status_code == 302
    j = c.get("/api/config?clave=ki").get_json()
    assert (j["inicio"], j["fin"], j["cada_horas"]) == ("08:00", "20:00", 3)


def test_horario_invalido(entorno):
    c, *_ = entorno
    for datos in ({"inicio": "09:00", "fin": "21:00", "cada_horas": "0"},
                  {"inicio": "21:00", "fin": "09:00", "cada_horas": "2"},
                  {"inicio": "xx", "fin": "21:00", "cada_horas": "2"},
                  {"inicio": "09:00", "fin": "21:00", "cada_horas": "7"}):
        r = c.post("/historial/kh", data=datos)
        assert r.status_code == 200
        assert "No se pudo guardar" in r.get_data(as_text=True)
    j = c.get("/api/config?clave=ki").get_json()
    assert (j["inicio"], j["fin"], j["cada_horas"]) == ("09:00", "21:00", 2)
