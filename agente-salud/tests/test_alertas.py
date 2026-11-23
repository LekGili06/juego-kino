from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from alertas import Horario, en_horario, horas_de_pregunta, pregunta_vencida, proxima_pregunta

Z = ZoneInfo("America/Santiago")
H = Horario(time(9), time(21), 2)


def t(h, m=0, d=23):
    return datetime(2026, 11, d, h, m, tzinfo=Z)


def test_horas_por_defecto():
    assert [x.hour for x in horas_de_pregunta(date(2026, 11, 23), H, Z)] == [9, 11, 13, 15, 17, 19, 21]


def test_horas_cada_3():
    h = Horario(time(9), time(21), 3)
    assert [x.hour for x in horas_de_pregunta(date(2026, 11, 23), h, Z)] == [9, 12, 15, 18, 21]


def test_en_horario():
    assert not en_horario(t(8, 59), H)
    assert en_horario(t(9), H)
    assert en_horario(t(21), H)
    assert not en_horario(t(21, 30), H)


def test_pregunta_vencida():
    assert pregunta_vencida(t(11, 29), H) == t(9)
    assert pregunta_vencida(t(11, 30), H) == t(11)
    assert pregunta_vencida(t(8), H) is None
    assert pregunta_vencida(t(9, 10), H) is None


def test_proxima_pregunta():
    assert proxima_pregunta(t(10), H) == t(11)
    assert proxima_pregunta(t(11), H) == t(11)
    assert proxima_pregunta(t(21, 10), H) == t(9, d=24)
    assert proxima_pregunta(t(7), H) == t(9)


def test_pregunta_actual():
    from alertas import pregunta_actual
    assert pregunta_actual(t(8), H) is None
    assert pregunta_actual(t(9), H) == t(9)
    assert pregunta_actual(t(10, 59), H) == t(9)
    assert pregunta_actual(t(23), H) == t(21)
