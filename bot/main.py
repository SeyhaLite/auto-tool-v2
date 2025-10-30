import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

from .core.config import BOT_TOKEN
from .core.database import init_db
from .jobs import schedule_all_tasks

# Import handlers
from .handlers.start import start, show_profile, show_status, back_to_main_menu
from .handlers.settings import get_settings_conv_handler
from .handlers.admin import get_admin_conv_handler
from .handlers.test_forward import get_test_forward_conv_handler
from .handlers.forwarding import handle_new_post

logger = logging.getLogger(__name__)

def create_application() -> Application:
    """Creates and configures the bot Application."""
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"DATABASE FAILED TO INITIALIZE: {e}", exc_info=True)
        raise

    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Conversation Handlers ---
    settings_conv_handler = get_settings_conv_handler()
    admin_conv_handler = get_admin_conv_handler()
    test_forward_conv_handler = get_test_forward_conv_handler()
    
    application.add_handler(settings_conv_handler)
    application.add_handler(admin_conv_handler)
    application.add_handler(test_forward_conv_handler)

    # --- Main Command and Menu Handlers ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^ព័ត៌មាន Profile 👤$"), show_profile))
    application.add_handler(MessageHandler(filters.Regex("^ស្ថានភាព Bot 📊$"), show_status))

    # --- Channel Post Handler (for 'new_messages' tasks) ---
    # This is the new, correct way to handle "new_messages" tasks
    # block=False allows other handlers to run, just in case
    application.add_handler(MessageHandler(
        filters.ChatType.CHANNEL & ~filters.COMMAND, 
        handle_new_post, 
        block=False
    ))

    # --- Schedule background jobs (for 'id_range' tasks) ---
    # This will run once when the application starts
    application.job_queue.run_once(schedule_all_tasks, 1)

    logger.info("Bot application created and handlers registered.")
    
    return application
