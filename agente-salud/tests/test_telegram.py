import telegram


class Resp:
    def __init__(self, status):
        self.status_code = status


class PostFalso:
    def __init__(self, status=200, error=None):
        self.llamadas = []
        self.status = status
        self.error = error

    def __call__(self, url, **kw):
        self.llamadas.append((url, kw))
        if self.error:
            raise self.error
        return Resp(self.status)


def test_texto_envia_mensaje():
    post = PostFalso()
    assert telegram.Telegram("TOK", "42", post=post).texto("hola") is True
    url, kw = post.llamadas[0]
    assert url == "https://api.telegram.org/botTOK/sendMessage"
    assert kw["data"] == {"chat_id": "42", "text": "hola"}
    assert kw["timeout"] > 0


def test_foto_envia_archivo(tmp_path):
    f = tmp_path / "1.jpg"
    f.write_bytes(b"\xff\xd8abc")
    post = PostFalso()
    assert telegram.Telegram("TOK", "42", post=post).foto(str(f), "😀 Bien") is True
    url, kw = post.llamadas[0]
    assert url == "https://api.telegram.org/botTOK/sendPhoto"
    assert kw["data"] == {"chat_id": "42", "caption": "😀 Bien"}
    assert "photo" in kw["files"]


def test_error_http_devuelve_false():
    assert telegram.Telegram("T", "1", post=PostFalso(status=500)).texto("x") is False


def test_excepcion_devuelve_false():
    assert telegram.Telegram("T", "1", post=PostFalso(error=OSError("red"))).texto("x") is False


def test_nulo():
    assert telegram.TelegramNulo().texto("x") is True
    assert telegram.TelegramNulo().foto("a", "b") is True
