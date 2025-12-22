"""
Main entry point for Telegram Attendance Bot.

This module initializes and runs the bot application.

Usage:
    python -m src.main
    
    or
    
    python src/main.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bot import create_application
from src.config import config


def setup_logging() -> None:
    """
    Configure application logging.
    
    Sets up logging to both stdout and a file (bot.log).
    Reduces noise from httpx library.
    """
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )
    
    # Reduce noise from httpx (used by python-telegram-bot)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Log startup info
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("Starting Telegram Attendance Bot...")
    logger.info(f"Database: {config.database.url}")
    logger.info(f"Timezone: {config.timezone.timezone}")
    logger.info(f"Work start: {config.attendance.work_start_hour:02d}:{config.attendance.work_start_minute:02d}")
    logger.info(f"Late threshold: {config.attendance.late_threshold_minutes} minutes")
    logger.info(f"Geofence radius: {config.attendance.geofence_default_radius}m")
    logger.info(f"Super admins: {config.admin.super_admin_ids}")
    logger.info("=" * 50)


def main() -> None:
    """
    Main function to run the bot.
    
    Creates the application and starts polling for updates.
    """
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Create application
        logger.info("Creating bot application...")
        app = create_application()
        
        # Run the bot with polling
        logger.info("Bot is running. Press Ctrl+C to stop.")
        app.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True  # Ignore updates while bot was offline
        )
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("Bot shutdown complete.")


if __name__ == "__main__":
    main()
