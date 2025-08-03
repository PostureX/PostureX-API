import json
from datetime import datetime

from telegram import Bot
from telegramify_markdown import markdownify

from src.config.app_config import AppConfig
from src.models import Analysis, User

CONFIG = AppConfig()
TELEGRAM_TOKEN = CONFIG.telegram_bot_token
bot = Bot(token=TELEGRAM_TOKEN)


def format_analysis_message(analysis):
    posture_result = json.loads(analysis["posture_result"])
    feedback = json.loads(analysis["feedback"])
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
        f"**Status:** `{analysis['status']}`",
    ]

    # Collect scores for easy lookup
    scores = posture_result.get("front", {}).get("score", {})

    msg.append("\n**📝 Feedback**")

    for section_key, section_data in feedback.get("front", {}).items():
        section_title = section_key.replace("_", " ").title()
        score_value = scores.get(section_key)
        score_str = (
            f"`| {round(score_value * 100, 1)}% optimal`"
            if score_value is not None
            else ""
        )
        msg.append(f"\n**{section_title}**")

        if score_str:
            msg.append(f"{score_str}")

        msg.append("---")

        if section_data.get("commendation"):
            msg.append(f"\n✅ **Commendations**\n{section_data['commendation']}")

        if section_data.get("critique"):
            msg.append(f"\n⚠️ **Critiques**\n{section_data['critique']}")

        suggestions = section_data.get("suggestions", [])
        if suggestions:
            msg.append("\nℹ️ **Suggestions**")
            for suggestion in suggestions:
                msg.append(f"{suggestion}\n")

    markdownified_text = markdownify("\n".join(msg), max_line_length=20)
    print(markdownified_text)
    return markdownified_text


async def send_analysis(user_id: int, analysis: Analysis, parse_mode="MarkdownV2"):
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
            text=markdownify(f"An error occured while trying to process your analysis with ID `{analysis.id}`. Please try again."),
            parse_mode=parse_mode,
        )

    formatted_message = format_analysis_message(analysis_dict)

    await bot.send_message(
        chat_id=user.telegram_id, text=formatted_message, parse_mode=parse_mode
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
