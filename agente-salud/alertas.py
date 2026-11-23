"""Reglas puras de horario: a qué horas preguntar y cuándo una pregunta venció."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MARGEN = timedelta(minutes=30)


@dataclass
class Horario:
    inicio: time
    fin: time
    cada_horas: int


def horas_de_pregunta(dia: date, h: Horario, zona: ZoneInfo) -> list:
    actual = datetime.combine(dia, h.inicio, tzinfo=zona)
    fin = datetime.combine(dia, h.fin, tzinfo=zona)
    horas = []
    while actual <= fin:
        horas.append(actual)
        actual += timedelta(hours=h.cada_horas)
    return horas


def en_horario(ahora: datetime, h: Horario) -> bool:
    return h.inicio <= ahora.timetz().replace(tzinfo=None) <= h.fin


def pregunta_actual(ahora: datetime, h: Horario):
    """La pregunta más reciente de hoy cuya hora ya llegó, o None."""
    pasadas = [x for x in horas_de_pregunta(ahora.date(), h, ahora.tzinfo) if x <= ahora]
    return pasadas[-1] if pasadas else None


def pregunta_vencida(ahora: datetime, h: Horario):
    """La pregunta más reciente de hoy cuyo plazo de respuesta (MARGEN) ya pasó, o None."""
    return pregunta_actual(ahora - MARGEN, h) if (ahora - MARGEN).date() == ahora.date() else None


def proxima_pregunta(ahora: datetime, h: Horario) -> datetime:
    for x in horas_de_pregunta(ahora.date(), h, ahora.tzinfo):
        if x >= ahora:
            return x
    return horas_de_pregunta(ahora.date() + timedelta(days=1), h, ahora.tzinfo)[0]
