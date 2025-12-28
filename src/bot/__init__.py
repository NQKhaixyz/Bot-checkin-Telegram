"""
Bot package initialization and application factory.

Creates and configures the Telegram bot application.
"""

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from src.config import config
from src.database import init_db


def create_application() -> Application:
    """
    Create and configure the Telegram bot application.
    
    This is the main application factory that:
    1. Initializes the database
    2. Creates the bot application
    3. Registers all handlers
    4. Configures error handling
    
    Returns:
        Application: Configured telegram bot application
    
    Usage:
        >>> app = create_application()
        >>> app.run_polling()
    """
    # Initialize database
    init_db(config.database.url)
    
    # Create application
    application = (
        Application.builder()
        .token(config.bot.token)
        .build()
    )
    
    # Register handlers (imported here to avoid circular imports)
    _register_handlers(application)
    
    # Register error handler
    _register_error_handler(application)
    
    return application


def _register_handlers(app: Application) -> None:
    """
    Register all message and command handlers.
    
    Handler registration order matters - more specific handlers
    should be registered before generic ones.
    
    Order:
    1. Conversation handlers (highest priority)
    2. Command handlers
    3. Message handlers
    4. Callback query handlers
    """
    # Import handlers here to avoid circular imports
    from src.bot.handlers.start import registration_conversation
    from src.bot.handlers.location import location_setup_conversation
    from src.bot.handlers.checkin import (
        checkin_conversation,
        checkout_command,
        status_command,
    )
    from src.bot.handlers.admin import (
        approve_command,
        reject_command,
        ban_command,
        unban_command,
        list_users_command,
        list_pending_command,
        broadcast_command,
        today_command,
        export_command,
        stats_command,
        help_admin_command,
        admin_callback_handler,
        list_locations_command,
        delete_location_command,
        delete_meeting_command,
        list_meetings_command,
        ranking_command,
        set_meeting_handler,
    )
    from src.bot.handlers.evidence import evidence_conversation
    from src.bot.handlers.help import help_command, ngocminh_command, ngocminh_callback_handler
    from src.bot.handlers.menu import text_message_handler
    
    # =========================================================================
    # CONVERSATION HANDLERS (must be first - highest priority)
    # =========================================================================
    
    # Registration conversation (handles /start and name input)
    app.add_handler(registration_conversation)
    
    # Location setup conversation (handles /set_location flow)
    app.add_handler(location_setup_conversation)
    
    # Check-in conversation (handles /checkin, "Diem danh" button, and location verification)
    app.add_handler(checkin_conversation)
    
    # Evidence conversation (handles /minhchung)
    app.add_handler(evidence_conversation)
    
    # Set meeting conversation (handles /set_meeting for admin)
    app.add_handler(set_meeting_handler)
    
    # =========================================================================
    # COMMAND HANDLERS - User commands
    # =========================================================================
    
    app.add_handler(CommandHandler("checkout", checkout_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ngocminh", ngocminh_command))
    
    # =========================================================================
    # COMMAND HANDLERS - Admin commands
    # =========================================================================
    
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("reject", reject_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("list_users", list_users_command))
    app.add_handler(CommandHandler("list_pending", list_pending_command))
    app.add_handler(CommandHandler("list_locations", list_locations_command))
    app.add_handler(CommandHandler("list_location", list_locations_command))  # Alias without 's'
    app.add_handler(CommandHandler("delete_location", delete_location_command))
    app.add_handler(CommandHandler("delete_meeting", delete_meeting_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("export_excel", export_command))
    app.add_handler(CommandHandler("exports", export_command))  # Common typo/alias
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("help_admin", help_admin_command))
    app.add_handler(CommandHandler("list_meetings", list_meetings_command))
    app.add_handler(CommandHandler("ranking", ranking_command))
    
    # =========================================================================
    # MESSAGE HANDLERS
    # =========================================================================
    
    # Text message handler for menu buttons
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        text_message_handler
    ))
    
    # =========================================================================
    # CALLBACK QUERY HANDLERS
    # =========================================================================
    
    # Ngocminh callback (must be before generic admin handler)
    app.add_handler(CallbackQueryHandler(ngocminh_callback_handler, pattern="^ngocminh_"))
    
    # Admin callback handler (generic - handles all other callbacks)
    app.add_handler(CallbackQueryHandler(admin_callback_handler))


def _register_error_handler(app: Application) -> None:
    """Register global error handler."""
    from src.bot.handlers.error import error_handler
    app.add_error_handler(error_handler)
