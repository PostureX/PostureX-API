from datetime import datetime
import asyncio

from telegram import Bot
from telegramify_markdown import markdownify

from src.config.app_config import AppConfig
from src.models import Analysis, User
from src.services.analysis_bucket_minio import get_pdf_report_as_bytes

CONFIG = AppConfig()
TELEGRAM_TOKEN = CONFIG.telegram_bot_token
bot = Bot(token=TELEGRAM_TOKEN)


STATUS_EMOJI = {
    "in_progress": "⏳",
    "completed": "✅",
    "failed": "❌"
}


def format_analysis_message(analysis):
    created_at = analysis["created_at"]

    # Parse and format created_at to human readable string
    try:
        dt = datetime.fromisoformat(created_at)
        created_at_str = dt.strftime("%A, %d %B %Y %I:%M %p")
    except Exception:
        created_at_str = str(created_at)

    msg = [
        "**🔫 Gun Posture Analysis Result**",
        f"[Click here to view the full detailed analysis]({CONFIG.frontend_url}/uploads/{analysis['id']})",
        f"**Analysis ID: `{analysis['id']}`**",
        f"**Session ID:** `{analysis['session_id']}`",
        f"**Date:** `{created_at_str}`",
        f"**Model Used:** `{analysis['model_name']}`",
        f"**Status:** `{STATUS_EMOJI.get(analysis['status'], '')} {analysis['status']}`",
    ]

    markdownified_text = markdownify("\n".join(msg))
    return markdownified_text


def send_alert_sync(user_id, analysis: Analysis):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            send_analysis(user_id, analysis, is_alert=True)
        )
        loop.close()

    except Exception as e:
        print(f"Error sending alert to user {user_id}: {str(e)}")


async def send_analysis(
    user_id: int, analysis: Analysis, parse_mode="MarkdownV2", is_alert=False
):
    """
    Send a message to a Telegram user or group by chat_id.
    Usage: send_analysis(123456789, "Hello from PostureX!")
    """
    user = User.query.filter_by(id=user_id).first()

    if not user:
        return

    if not user.telegram_id:
        return

    analysis_dict = analysis.to_dict()

    # check analysis status
    if analysis_dict["status"] == "in_progress":
        return await bot.send_message(
            chat_id=user.telegram_id,
            text="Your analysis is still in progress. Please check back later.",
        )

    if analysis_dict["status"] == "failed":
        return await bot.send_message(
            chat_id=user.telegram_id,
            text=markdownify(
                f"An error occured while trying to process your analysis with ID `{analysis.id}`. You may try again [here]({CONFIG.frontend_url}/analysis/{analysis.id})."
            ),
            parse_mode=parse_mode,
        )

    msg = format_analysis_message(analysis_dict)

    if is_alert:
        msg = markdownify(f"Your gun posture analysis is ready!\n\n{msg}")

    pdf_report_bytes = get_pdf_report_as_bytes(analysis.user_id, analysis.session_id)

    await bot.send_document(
        chat_id=user.telegram_id,
        caption=msg,
        document=pdf_report_bytes,
        filename=f"{analysis.session_id}_report.pdf",
        parse_mode=parse_mode,
    )


async def send_analysis_error(user_id: int, analysis: Analysis):
    """
    Send an error message to a Telegram user or group by chat_id.
    """
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return

    if not user.telegram_id:
        return

    analysis_link = f"[here]({CONFIG.frontend_url}/analysis/)"

    await bot.send_message(
        chat_id=user.telegram_id,
        parse_mode="MarkdownV2",
        text=markdownify(
            f"An error occurred when trying to process your latest upload with ID `{analysis.id}`. Please try again {analysis_link}."
        ),
    )
