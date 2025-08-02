import datetime
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegramify_markdown import markdownify

from src import create_app  # Import your app factory
from src.config.database import db
from src.config.app_config import AppConfig
from src.models import User, Analysis
from src.services.telegram_bot import send_analysis


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and len(args) > 0:
        user_id = args[0]

        user = User.query.filter_by(id=user_id).first()

        # check if user exists
        if user:
            # check if link has expired
            if (
                user.tele_link_expires_at
                and user.tele_link_expires_at < datetime.datetime.now()
            ):
                return await update.message.reply_text(
                    markdownify(
                        "Your link has expired. Please generate a new link on the PostureX website."
                    ),
                    parse_mode="MarkdownV2",
                )

            # set telegram id
            user.telegram_id = update.message.from_user.id

            # expire the link
            user.tele_link_expires_at = None

            db.session.commit()

            return await update.message.reply_text(
                markdownify(
                    f"Hello {user.name}! You have successfully linked this telegram account to your PostureX account. You will now receive updates about your gun posture analysis results. Use /unlink if you wish to unlink.",
                ),
                parse_mode="MarkdownV2",
            )

    return await update.message.reply_text(
        markdownify(f"Hello {update.message.from_user.first_name}! "),
        parse_mode="MarkdownV2",
    )


async def unlink(update: Update):
    user = User.query.filter_by(telegram_id=update.message.from_user.id).first()
    if user:
        user.telegram_id = None
        db.session.commit()
        return await update.message.reply_text(
            markdownify(
                "You have successfully unlinked your telegram account from your PostureX account.",
            ),
            parse_mode="MarkdownV2",
        )
    return await update.message.reply_text(
        markdownify("You are not linked to any PostureX account."),
        parse_mode="MarkdownV2",
    )

async def get_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = User.query.filter_by(telegram_id=update.message.from_user.id).first()
    if not user:
        return await update.message.reply_text(
            markdownify("You are not linked to any PostureX account."),
            parse_mode="MarkdownV2",
        )

    args = context.args
    if args and len(args) > 0:
        try:
            analysis_id = int(args[0])
            analysis = Analysis.query.filter_by(id=analysis_id, user_id=user.id).first()
            if not analysis:
                return await update.message.reply_text(
                    markdownify("Analysis not found."),
                    parse_mode="MarkdownV2",
                )
        except ValueError:
            return await update.message.reply_text(
                markdownify("Invalid analysis ID."),
                parse_mode="MarkdownV2",
            )
    else:
        # Fetch the latest analysis for the user
        analysis = Analysis.query.filter_by(user_id=user.id).order_by(Analysis.created_at.desc()).first()
        if not analysis:
            return await update.message.reply_text(
                markdownify("No analysis found."),
                parse_mode="MarkdownV2",
            )

    await send_analysis(user.id, analysis)

if __name__ == "__main__":
    flask_app = create_app()
    with flask_app.app_context():
        config = AppConfig()
        TELEGRAM_TOKEN = config.telegram_bot_token

        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("unlink", unlink))
        app.add_handler(CommandHandler("analysis", get_analysis))
        app.run_polling()
