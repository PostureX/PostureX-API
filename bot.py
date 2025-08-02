import datetime
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegramify_markdown import markdownify

from src import create_app  # Import your app factory
from src.config.database import db
from src.models.user import User

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Set your bot token in environment variable


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


async def unlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


if __name__ == "__main__":
    flask_app = create_app()
    with flask_app.app_context():
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("unlink", unlink))
        app.run_polling()
