from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram.ext import ApplicationBuilder

from app.config import settings
from app.handlers import register


class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def _start_health(port: int = 7860) -> None:
    server = HTTPServer(("0.0.0.0", port), _Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def main() -> None:
    cfg = settings()
    if not cfg.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    _start_health()
    application = ApplicationBuilder().token(cfg.bot_token).build()
    register(application, cfg)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
