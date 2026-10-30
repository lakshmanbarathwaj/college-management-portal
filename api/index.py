import mimetypes
from pathlib import Path
from urllib.parse import unquote

from config.wsgi import application as django_application


STATIC_DIR = Path(__file__).resolve().parent.parent / "accounts" / "static"


class StaticFilesMiddleware:
    def __init__(self, application):
        self.application = application
        self.static_root = STATIC_DIR.resolve()

    def __call__(self, environ, start_response):
        path_info = environ.get("PATH_INFO", "")
        if not path_info.startswith("/static/"):
            return self.application(environ, start_response)

        relative_path = unquote(path_info.removeprefix("/static/"))
        file_path = (self.static_root / relative_path).resolve()
        try:
            file_path.relative_to(self.static_root)
        except ValueError:
            return self._not_found(start_response)

        if not file_path.is_file():
            return self._not_found(start_response)

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        content = file_path.read_bytes()
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type),
                ("Content-Length", str(len(content))),
                ("Cache-Control", "public, max-age=3600"),
            ],
        )
        return [content]

    @staticmethod
    def _not_found(start_response):
        body = b"Not Found"
        start_response(
            "404 Not Found",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]


app = StaticFilesMiddleware(django_application)
