import logging
import sys
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
import bot.config as config
from bot.handlers import (
    start,
    help_command,
    status_command,
    dirs_command,
    manage_command,
    turtle_command,
    get_conversation_handler,
    handle_callback_query
)
from bot.poller import poll_job
from bot.transmission import TransmissionWrapper

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def on_startup(application):
    """Callback run when the bot starts up."""
    logger.info("Bot starting up...")
    
    # Verify Transmission connection
    transmission = TransmissionWrapper()
    if transmission.test_connection():
        logger.info("Successfully connected to Transmission RPC server!")
    else:
        logger.warning(
            "Could not connect to Transmission RPC server. "
            "Please ensure Transmission is running and RPC is enabled."
        )
        
    # Check if ALLOWED_USER_IDS is set
    if not config.ALLOWED_USER_IDS:
        logger.warning(
            "ALLOWED_USER_IDS is empty! "
            "The bot will not respond to any users for security reasons. "
            "Please configure ALLOWED_USER_IDS in your .env file."
        )
    else:
        logger.info(f"Authorized users: {config.ALLOWED_USER_IDS}")

def main():
    """Main application runner."""
    # Ensure config can load (will throw ValueError if TELEGRAM_TOKEN missing)
    try:
        token = config.TELEGRAM_TOKEN
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Initialize the application
    application = ApplicationBuilder().token(token).post_init(on_startup).build()

    # Register conversation handler for adding torrents (magnet / files)
    application.add_handler(get_conversation_handler())

    # Register commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("dirs", dirs_command))
    application.add_handler(CommandHandler("manage", manage_command))
    application.add_handler(CommandHandler("turtle", turtle_command))

    # Register global callback query handler for status refreshes and controls
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Register background polling job
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(
            poll_job,
            interval=config.POLL_INTERVAL,
            first=5,
            name="completion_poll"
        )
        logger.info(f"Registered completion poller to run every {config.POLL_INTERVAL} seconds.")
    else:
        logger.error("JobQueue is not available! Background polling will not work.")

    # Start the bot
    logger.info("Starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
