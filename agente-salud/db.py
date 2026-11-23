"""Almacenamiento en SQLite: respuestas, latidos del iPad y ajustes."""
import sqlite3
from datetime import datetime, timezone


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


ESQUEMA = """
CREATE TABLE IF NOT EXISTS respuestas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    estado TEXT NOT NULL,
    foto TEXT,
    tarde INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS latidos (ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
"""


def conectar(ruta: str) -> sqlite3.Connection:
    conn = sqlite3.connect(ruta, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(ESQUEMA)
    return conn


def _fila(f):
    if f is None:
        return None
    return {
        "id": f["id"],
        "ts": datetime.fromisoformat(f["ts"]),
        "estado": f["estado"],
        "foto": f["foto"],
        "tarde": bool(f["tarde"]),
    }


def guardar_respuesta(conn, estado: str, ts: datetime, tarde: bool = False) -> int:
    cur = conn.execute(
        "INSERT INTO respuestas (ts, estado, tarde) VALUES (?, ?, ?)",
        (_iso(ts), estado, int(tarde)),
    )
    conn.commit()
    return cur.lastrowid


def adjuntar_foto(conn, respuesta_id: int, nombre_archivo: str) -> None:
    conn.execute("UPDATE respuestas SET foto = ? WHERE id = ?", (nombre_archivo, respuesta_id))
    conn.commit()


def obtener_respuesta(conn, respuesta_id: int):
    return _fila(conn.execute("SELECT * FROM respuestas WHERE id = ?", (respuesta_id,)).fetchone())


def listar_respuestas(conn, desde: datetime) -> list:
    filas = conn.execute(
        "SELECT * FROM respuestas WHERE ts >= ? ORDER BY ts DESC, id DESC", (_iso(desde),)
    ).fetchall()
    return [_fila(f) for f in filas]


def ultima_respuesta_desde(conn, desde: datetime):
    f = conn.execute(
        "SELECT * FROM respuestas WHERE ts >= ? AND estado != 'sin_respuesta' "
        "ORDER BY ts DESC LIMIT 1",
        (_iso(desde),),
    ).fetchone()
    return _fila(f)


def registrar_latido(conn, ts: datetime) -> None:
    conn.execute("DELETE FROM latidos")
    conn.execute("INSERT INTO latidos (ts) VALUES (?)", (_iso(ts),))
    conn.commit()


def ultimo_latido(conn):
    f = conn.execute("SELECT ts FROM latidos ORDER BY ts DESC LIMIT 1").fetchone()
    return datetime.fromisoformat(f["ts"]) if f else None


def leer_ajuste(conn, clave: str, defecto: str) -> str:
    f = conn.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
    return f["valor"] if f else defecto


def guardar_ajuste(conn, clave: str, valor: str) -> None:
    conn.execute(
        "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, valor),
    )
    conn.commit()
