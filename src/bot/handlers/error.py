"""
Global error handler for the Telegram bot.

Catches and logs all unhandled exceptions from handlers.
"""

import logging
import html
import traceback

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src.config import config
from src.constants import Messages

logger = logging.getLogger(__name__)


async def error_handler(
    update: object, 
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle errors that occur during update processing.
    
    Logs the error and optionally notifies admins.
    
    Args:
        update: The update that caused the error
        context: The context containing error info
    """
    # Log the error
    logger.error(
        "Exception while handling an update:",
        exc_info=context.error
    )
    
    # Build error message for admins
    tb_list = traceback.format_exception(
        None, 
        context.error, 
        context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    
    # Truncate if too long
    if len(tb_string) > 4000:
        tb_string = tb_string[:4000] + "..."
    
    # Format update info
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    
    error_message = (
        f"An exception was raised while handling an update\n\n"
        f"<pre>update = {html.escape(str(update_str)[:1000])}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    
    # Notify super admins
    for admin_id in config.admin.super_admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=error_message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    # Send user-friendly message to the user
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                Messages.ERROR_GENERIC
            )
        except Exception:
            pass  # Ignore if we can't send message
