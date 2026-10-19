import os
import re
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================ CONFIGURATION ================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL_ID = os.getenv("SOURCE_CHANNEL_ID")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")

MAIN_CHANNEL_LINK = "https://t.me/+0-lEIs0SmuM4ZGE1"
ANT_ANIMES_LINK = "https://t.me/addlist/2SVHy42H1fJkZGI1"
ANIME_CHANNEL = "https://t.me/AnimeNetworkTamil"

FILETOLINK_DOMAIN = "filetolink.omgxserver4.workers.dev"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ================ WEB SERVER ================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ANT Auto Caption Bot is running!")

    def log_message(self, format, *args):
        pass


def run_web_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# ================ START COMMAND ================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "Welcome to ANT Auto Caption Bot! 🤖\n\n"
        "I automatically process anime videos from your "
        "configured source channel and publish them "
        "to your destination channel."
    )


# ================ HELPERS ================

def get_file_name(message):
    if message.document:
        return message.document.file_name or "Anime Episode"

    if message.video:
        return message.video.file_name or "Anime Episode"

    return "Anime Episode"


def get_quality(text, file_name):
    combined = f"{text} {file_name}"

    match = re.search(
        r"(?<!\d)(2160p|1440p|1080p|720p|480p|360p)(?!\d)",
        combined,
        re.IGNORECASE,
    )

    return match.group(1).lower() if match else "Unknown"


def get_download_link(text):
    pattern = (
        r"https?://"
        + re.escape(FILETOLINK_DOMAIN)
        + r"/[^\s<>]+"
    )

    match = re.search(pattern, text or "", re.IGNORECASE)

    if not match:
        return None

    return match.group(0).rstrip(".,;!?)\"]'")


def escape_html(value):
    import html
    return html.escape(value, quote=True)


def build_caption(file_name, quality, link):
    safe_file_name = escape_html(file_name)
    safe_quality = escape_html(quality)
    safe_link = escape_html(link)

    return (
        f'<blockquote><a href="{ANIME_CHANNEL}">'
        f'@AnimeNetworkTamil</a>\n'
        f'{safe_file_name}\n\n'
        f'🎥 Quality : {safe_quality}\n'
        f'💬 Subtitles : English\n'
        f'🔊 Audio : Tamil\n'
        f'</blockquote>\n\n'
        f'➪ <a href="{safe_link}">Fast Download</a>\n'
        f'➪ <a href="{MAIN_CHANNEL_LINK}">Main Channel</a>\n'
        f'➪ <a href="{ANT_ANIMES_LINK}">ANT ANIMES</a>'
    )


# ================ SOURCE CHANNEL HANDLER ================

async def process_channel_post(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.channel_post

    if not message:
        return

    if str(message.chat_id) != str(SOURCE_CHANNEL_ID):
        return

    if not (message.video or message.document):
        logger.info("Ignoring a post without a video or document.")
        return

    if message.document:
        mime_type = message.document.mime_type or ""

        if not mime_type.startswith("video/"):
            logger.info("Ignoring a non-video document.")
            return

    original_caption = message.caption or ""
    file_name = get_file_name(message)
    quality = get_quality(original_caption, file_name)
    link = get_download_link(original_caption)

    if not link:
        logger.warning(
            "No supported FileToLink URL found in source post %s",
            message.message_id,
        )
        return

    caption = build_caption(file_name, quality, link)

    try:
        await context.bot.copy_message(
            chat_id=int(TARGET_CHANNEL_ID),
            from_chat_id=message.chat_id,
            message_id=message.message_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )

        logger.info(
            "Successfully copied source post %s",
            message.message_id,
        )

    except Exception:
        logger.exception(
            "Failed to copy source post %s",
            message.message_id,
        )


# ================ MAIN ================

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing!")

    if not SOURCE_CHANNEL_ID:
        raise ValueError("SOURCE_CHANNEL_ID is missing!")

    if not TARGET_CHANNEL_ID:
        raise ValueError("TARGET_CHANNEL_ID is missing!")

    web_thread = Thread(
        target=run_web_server,
        daemon=True,
    )
    web_thread.start()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            filters.UpdateType.CHANNEL_POST
            & (filters.VIDEO | filters.Document.ALL),
            process_channel_post,
        )
    )

    logger.info("ANT Auto Caption Bot is starting...")

    application.run_polling(
        allowed_updates=[
            "message",
            "channel_post",
        ]
    )


if __name__ == "__main__":
    main()
