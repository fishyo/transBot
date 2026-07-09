import asyncio
import traceback
import logging
from telegram.ext import ContextTypes
import bot.config as config
from bot.transmission import TransmissionWrapper
from bot.storage import Storage

logger = logging.getLogger(__name__)

# Singletons
transmission = TransmissionWrapper()
storage = Storage()

class CompletionPoller:
    def __init__(self):
        self.is_first_run = True

    async def poll_check(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Periodically checks torrents for completion.
        Registered as a job in the application's job_queue.
        """
        try:
            try:
                torrents = transmission.get_torrents()
            except Exception:
                # Silently skip if transmission is down or connection fails, to avoid flooding logs
                return
            
            for t in torrents:
                # Check if torrent is completed
                # In transmission-rpc, percent_done or progress is 1.0 (or close to it)
                # or left_until_done is 0.
                is_completed = (t.left_until_done == 0) or (t.progress >= 1.0)
                
                if is_completed:
                    torrent_hash = t.hashString
                    
                    if not storage.is_torrent_completed_notified(torrent_hash):
                        # If first run since bot start, mark as notified silently to avoid spamming
                        if self.is_first_run:
                            storage.add_completed_torrent(torrent_hash)
                            continue
                            
                        # Send notification to all allowed users
                        msg = (
                            f"🔔 **Download Completed!**\n\n"
                            f"📛 **Name:** {t.name}\n"
                            f"📁 **Location:** `{t.download_dir}`\n"
                            f"💾 **Size:** {t.format_size() if hasattr(t, 'format_size') else str(t.total_size)}"
                        )
                        
                        for user_id in config.ALLOWED_USER_IDS:
                            try:
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=msg,
                                    parse_mode="Markdown"
                                )
                            except Exception as e:
                                logger.error(f"Failed to send completion notification to user {user_id}: {e}")
                                
                        # Save in DB
                        storage.add_completed_torrent(torrent_hash)

            # After first check, set first run to False
            if self.is_first_run:
                self.is_first_run = False

        except Exception as e:
            logger.error(f"Error in completion poller: {e}")
            logger.error(traceback.format_exc())

# Create a singleton instance
poller = CompletionPoller()

async def poll_job(context: ContextTypes.DEFAULT_TYPE):
    """Entry point for python-telegram-bot job queue."""
    await poller.poll_check(context)
