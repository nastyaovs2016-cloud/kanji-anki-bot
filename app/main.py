from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import ApplicationBuilder

from app.config import settings
from app.handlers import register

logger = logging.getLogger(__name__)


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


async def on_error(update: object, context) -> None:
    logger.error("Unhandled error while processing update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat is not None:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Ошибка сети. Попробуй ещё раз.",
            )
        except Exception:
            logger.exception("Failed to notify user about error")


def main() -> None:
    cfg = settings()
    if not cfg.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    _start_health()
    application = ApplicationBuilder().token(cfg.bot_token).build()
    register(application, cfg)
    application.add_error_handler(on_error)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
