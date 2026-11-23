"""Envío de mensajes y fotos al Telegram del usuario. Nunca lanza excepciones."""
import logging

import requests

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, token: str, chat_id: str, post=requests.post):
        self.base = "https://api.telegram.org/bot" + token + "/"
        self.chat_id = chat_id
        self.post = post

    def _enviar(self, metodo, data, files=None) -> bool:
        try:
            r = self.post(self.base + metodo, data=data, files=files, timeout=15)
            if r.status_code != 200:
                log.warning("Telegram %s respondió %s", metodo, r.status_code)
                return False
            return True
        except Exception as e:  # noqa: BLE001 - nunca romper la respuesta al iPad
            log.warning("Telegram %s falló: %s", metodo, e)
            return False

    def texto(self, mensaje: str) -> bool:
        return self._enviar("sendMessage", {"chat_id": self.chat_id, "text": mensaje})

    def foto(self, ruta: str, leyenda: str) -> bool:
        try:
            with open(ruta, "rb") as f:
                return self._enviar(
                    "sendPhoto", {"chat_id": self.chat_id, "caption": leyenda}, files={"photo": f}
                )
        except OSError as e:
            log.warning("No se pudo leer la foto %s: %s", ruta, e)
            return False


class TelegramNulo:
    """Se usa cuando no hay token configurado: no envía nada."""

    def texto(self, mensaje: str) -> bool:
        return True

    def foto(self, ruta: str, leyenda: str) -> bool:
        return True
