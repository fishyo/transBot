import os
import re
import math
import html
import shutil
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
import bot.config as config
from bot.transmission import TransmissionWrapper
from bot.storage import Storage

logger = logging.getLogger(__name__)

# Conversation states for directory browser
WAITING_FOR_DIR = 1
WAITING_FOR_NEW_DIR_NAME = 2
WAITING_FOR_RENAME = 3

# Instantiate singletons/helpers
transmission = TransmissionWrapper()
storage = Storage()

def check_user(func):
    """Decorator to restrict access to allowed users only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if config.ALLOWED_USER_IDS and user_id not in config.ALLOWED_USER_IDS:
            logger.warning(f"Unauthorized access attempt by user_id: {user_id}")
            if update.message:
                await update.message.reply_text("⛔️ You are not authorized to use this bot.")
            elif update.callback_query:
                await update.callback_query.answer("⛔️ Unauthorized.", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def get_progress_bar(percent: float) -> str:
    """Generates a visual progress bar. 0.0 <= percent <= 100.0"""
    bar_length = 10
    # Clip percent to [0.0, 100.0] defensively to prevent formatting overflow
    percent = max(0.0, min(100.0, percent))
    filled_length = int(round(bar_length * percent / 100))
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    return bar

def format_size(bytes_size: int) -> str:
    """Formats bytes into human readable format."""
    if not bytes_size:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(bytes_size, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_size / p, 2)
    return f"{s} {size_name[i]}"

def format_speed(bytes_per_sec: int) -> str:
    """Formats speed in bytes/sec into human readable format."""
    if not bytes_per_sec:
        return "0 B/s"
    return f"{format_size(bytes_per_sec)}/s"

def format_eta(eta) -> str:
    """Formats ETA in seconds or timedelta into a friendly format."""
    if not eta:
        return "Unknown"
        
    if hasattr(eta, "total_seconds"):
        seconds = int(eta.total_seconds())
    elif isinstance(eta, (int, float)):
        seconds = int(eta)
    else:
        return str(eta)
        
    if seconds < 0:
        return "Unknown"
    if seconds > 86400 * 7:
        return "Inf"
    
    parts = []
    days, remain = divmod(seconds, 86400)
    if days > 0:
        parts.append(f"{days}d")
    hours, remain = divmod(remain, 3600)
    if hours > 0:
        parts.append(f"{hours}h")
    minutes, remain = divmod(remain, 60)
    if minutes > 0:
        parts.append(f"{minutes}m")
    seconds = remain
    if seconds > 0 or not parts:
        parts.append(f"{int(seconds)}s")
    
    return " ".join(parts)

@check_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends start message."""
    welcome_text = (
        "👋 <b>Welcome to Transmission Telegram Bot!</b>\n\n"
        "Send me a magnet link, a torrent URL, or upload a `.torrent` file, "
        "and I will help you download it directly to your Transmission client.\n\n"
        "<b>Available Commands:</b>\n"
        "📊 /status - View real-time download progress and disk space\n"
        "🎛️ /manage - Interactive center to pause, resume, delete, or rename torrents\n"
        "📂 /dirs - Set default path or browse directory structure\n"
        "🐢 /turtle - Toggle Alternative Speed Limits (Turtle Mode) ON/OFF\n"
        "❌ /cancel - Reset and abort any active input or directory navigation\n"
        "❓ /help - View detailed user guide"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

@check_user
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends help instructions."""
    help_text = (
        "💡 <b>How to Download:</b>\n"
        "1. Send or paste a magnet link (starts with <code>magnet:?</code>)\n"
        "2. Send a link to a <code>.torrent</code> file\n"
        "3. Upload a <code>.torrent</code> file as a Document\n\n"
        "After receiving the link/file, the bot will open a directory browser. "
        "You can click directories to navigate, download directly, or create subfolders on the fly!\n\n"
        "🛠️ <b>Command Guide:</b>\n"
        "• <b>/status</b> - Show read-only real-time download status, speeds, active seeds/peers, Turtle Mode status, and OMV Passport drive space.\n"
        "• <b>/manage</b> - The interactive control center. Click on any torrent to open its details card, allowing you to:\n"
        "  - ⏸ Pause or ▶️ Resume a download\n"
        "  - 🗑 Delete a torrent (with option to keep or delete data files)\n"
        "  - ✏️ <b>Rename</b> the torrent folder/file name directly\n"
        "• <b>/dirs</b> - View default download folder and recently used directories. You can click to set default paths or browse the download storage folders.\n"
        "• <b>/turtle</b> - Instantly toggle Transmission's Alternative Speed Limits (Turtle Mode) ON or OFF.\n"
        "• <b>/cancel</b> - Abort directory browsing, new folder creation, or torrent renaming at any point.\n\n"
        "🔔 <b>Notifications:</b>\n"
        "The bot will automatically notify you in chat when a torrent completes downloading."
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

def get_subdirs(parent_dir: str) -> list:
    """Lists subdirectories inside parent_dir, ignoring hidden ones."""
    try:
        if not os.path.exists(parent_dir):
            return []
        subdirs = []
        for name in os.listdir(parent_dir):
            full_path = os.path.join(parent_dir, name).replace("\\", "/")
            if os.path.isdir(full_path):
                # Ignore hidden folders and system folders like lost+found
                if not name.startswith('.') and name != "lost+found":
                    subdirs.append(full_path)
        return sorted(subdirs)
    except Exception as e:
        logger.error(f"Error listing subdirectories of {parent_dir}: {e}")
        return []

async def show_directory_browser(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    """Renders the directory browser inline keyboard."""
    current_path = context.user_data.get("current_browse_path", "/downloads")
    
    # Get subdirectories
    subdirs = get_subdirs(current_path)
    # Store subdirs in context for lookup
    context.user_data["browse_subdirs"] = subdirs
    
    # Header text
    escaped_path = html.escape(current_path)
    msg = (
        f"📂 <b>Directory Browser</b>\n\n"
        f"📍 <b>Current Path:</b> <code>{escaped_path}</code>\n\n"
        f"Select a folder below to navigate inside it, or choose one of the options:"
    )
    
    keyboard = []
    
    # List subdirectories (limit to 10 to keep menu readable)
    for idx, path in enumerate(subdirs[:10]):
        name = os.path.basename(path)
        keyboard.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"nav_sub:{idx}")])
        
    if len(subdirs) > 10:
        keyboard.append([InlineKeyboardButton(f"➕ ... and {len(subdirs) - 10} more folders", callback_data="noop")])

    # Confirmation and creation buttons
    has_pending = "pending_torrent" in context.user_data
    confirm_text = "✅ Select for Download" if has_pending else "📌 Set as Default Path"
    keyboard.append([
        InlineKeyboardButton(confirm_text, callback_data="nav_confirm")
    ])
    keyboard.append([
        InlineKeyboardButton("🆕 Create Folder Here", callback_data="nav_create_dir")
    ])
    
    # Navigation buttons (Back / Cancel)
    nav_row = []
    # Only allow going back if we are deeper than /downloads
    # Comparing lowercase paths to prevent case sensitivity issues on Windows/Linux mounts
    if current_path.strip("/").lower() != "downloads":
        nav_row.append(InlineKeyboardButton("↩️ Back", callback_data="nav_parent"))
    nav_row.append(InlineKeyboardButton("❌ Cancel", callback_data="dir_cancel"))
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(msg, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

@check_user
async def handle_torrent_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Invoked when user sends a text message that could be a magnet link/URL or uploads a document.
    """
    magnet_or_url = ""
    torrent_bytes = None
    file_name = ""

    if update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(".torrent") or doc.mime_type == "application/x-bittorrent":
            file_name = doc.file_name
            telegram_file = await doc.get_file()
            torrent_bytes = await telegram_file.download_as_bytearray()
            torrent_bytes = bytes(torrent_bytes)
        else:
            await update.message.reply_text("❌ Provided file is not a torrent file.")
            return ConversationHandler.END
    else:
        text = update.message.text.strip()
        if text.startswith("magnet:") or re.match(r'^https?://', text):
            magnet_or_url = text
        else:
            await update.message.reply_text(
                "❌ Please send a valid magnet link, HTTP/HTTPS torrent URL, or upload a `.torrent` file."
            )
            return ConversationHandler.END

    # Store the input in user data
    context.user_data["pending_torrent"] = torrent_bytes or magnet_or_url
    context.user_data["pending_filename"] = file_name
    
    # Initialize the browse path to /downloads
    context.user_data["current_browse_path"] = "/downloads"

    # Start directory browsing
    await show_directory_browser(update, context)
    return WAITING_FOR_DIR

async def process_torrent_addition(update: Update, context: ContextTypes.DEFAULT_TYPE, download_dir: str):
    """Helper function to add the torrent to Transmission and reply."""
    pending = context.user_data.get("pending_torrent")
    if not pending:
        await update.effective_message.reply_text("❌ No pending torrent found. Please try again.")
        return
    try:
        # Add torrent
        torrent = transmission.add_torrent(pending, download_dir=download_dir)
        
        # Save directory to recent directories
        if download_dir:
            storage.add_recent_dir(download_dir)

        # Clear state
        context.user_data.pop("pending_torrent", None)
        context.user_data.pop("pending_filename", None)
        context.user_data.pop("current_browse_path", None)

        escaped_name = html.escape(torrent.name)
        escaped_dir = html.escape(download_dir)
        msg = (
            f"✅ <b>Torrent Added Successfully!</b>\n\n"
            f"📛 <b>Name:</b> {escaped_name}\n"
            f"📂 <b>Directory:</b> <code>{escaped_dir}</code>\n"
            f"🆔 <b>ID:</b> <code>{torrent.id}</code>"
        )
        keyboard = [[InlineKeyboardButton("📊 Check Status", callback_data="status_refresh")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.effective_message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        await update.effective_message.reply_text(f"❌ Error adding torrent: {str(e)}")

@check_user
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles directory selection button clicks."""
    query = update.callback_query
    logger.debug(f"handle_callback_query data={query.data}")
    await query.answer()

    data = query.data

    # 1. Directory Navigation Callbacks
    if data.startswith("nav_sub:"):
        idx = int(data.split(":")[1])
        subdirs = context.user_data.get("browse_subdirs", [])
        if 0 <= idx < len(subdirs):
            context.user_data["current_browse_path"] = subdirs[idx]
            await show_directory_browser(update, context, query=query)
        return WAITING_FOR_DIR

    elif data == "nav_parent":
        current_path = context.user_data.get("current_browse_path", "/downloads")
        parent_path = os.path.dirname(current_path).replace("\\", "/")
        # Prevent escaping /downloads for safety
        if "downloads" in parent_path.lower() or parent_path == "/downloads" or parent_path == "/":
            if parent_path == "/":
                parent_path = "/downloads"
            context.user_data["current_browse_path"] = parent_path
            await show_directory_browser(update, context, query=query)
        return WAITING_FOR_DIR

    elif data == "nav_confirm":
        selected_dir = context.user_data.get("current_browse_path", "/downloads")
        if "pending_torrent" in context.user_data:
            await query.edit_message_text(f"⏳ Adding torrent to `{selected_dir}`...")
            await process_torrent_addition(update, context, selected_dir)
        else:
            try:
                client = transmission.get_client()
                client.set_session(download_dir=selected_dir)
                storage.add_recent_dir(selected_dir)
                await query.edit_message_text(
                    f"✅ **Transmission Default Path Updated!**\n\n"
                    f"📍 New default: `{selected_dir}`",
                    parse_mode="Markdown"
                )
            except Exception as e:
                await query.edit_message_text(f"❌ Failed to set default directory: {e}")
        return ConversationHandler.END

    elif data == "nav_create_dir":
        current_path = context.user_data.get("current_browse_path", "/downloads")
        await query.edit_message_text(
            f"📁 **Create Folder inside** `{current_path}`\n\n"
            f"Please type and send the name of the new folder.\n"
            f"Type `/cancel` to abort.",
            parse_mode="Markdown"
        )
        return WAITING_FOR_NEW_DIR_NAME

    elif data == "noop":
        await query.answer("Too many directories. Navigate into specific folders to view subdirs.", show_alert=True)
        return WAITING_FOR_DIR

    elif data == "dir_cancel":
        context.user_data.pop("pending_torrent", None)
        context.user_data.pop("pending_filename", None)
        context.user_data.pop("current_browse_path", None)
        await query.edit_message_text("❌ Download canceled.")
        return ConversationHandler.END

    # 2. Status & Controls Callbacks
    elif data == "status_refresh":
        await display_status(update, context, is_callback=True)

    elif data.startswith("t_"):
        parts = data.split("_")
        action = parts[1]
        torrent_id = int(parts[2])
        
        t = transmission.get_torrent(torrent_id)
        if not t:
            await query.answer("❌ Torrent not found.", show_alert=True)
            return

        if action == "pause":
            transmission.pause_torrent(torrent_id)
            await query.answer(f"⏸ Paused: {t.name[:20]}")
        elif action == "resume":
            transmission.resume_torrent(torrent_id)
            await query.answer(f"▶️ Resumed: {t.name[:20]}")
        elif action == "delete":
            keyboard = [
                [
                    InlineKeyboardButton("🗑 Keep Data", callback_data=f"tdel_keep_{torrent_id}"),
                    InlineKeyboardButton("🔥 Delete Data", callback_data=f"tdel_all_{torrent_id}")
                ],
                [InlineKeyboardButton("↩️ Back", callback_data="status_refresh")]
            ]
            await query.edit_message_text(
                f"🗑 **Confirm Delete**\n\nAre you sure you want to remove:\n`{t.name}`?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        await display_status(update, context, is_callback=True)

    elif data.startswith("tdel_"):
        parts = data.split("_")
        mode = parts[1]
        torrent_id = int(parts[2])
        
        t = transmission.get_torrent(torrent_id)
        name = t.name if t else "Torrent"
        
        if mode == "keep":
            transmission.remove_torrent(torrent_id, delete_data=False)
            await query.answer(f"Removed (kept files): {name[:20]}")
        elif mode == "all":
            transmission.remove_torrent(torrent_id, delete_data=True)
            await query.answer(f"Removed (deleted files): {name[:20]}")
            
        await display_status(update, context, is_callback=True)

    elif data == "m_refresh_list":
        await display_manage_list(update, context, is_callback=True)

    elif data == "m_close":
        await query.edit_message_text("🎛️ Management center closed.")

    elif data.startswith("m_select:"):
        torrent_id = int(data.split(":")[1])
        await display_torrent_detail(update, context, torrent_id)

    elif data.startswith("m_action:"):
        parts = data.split(":")
        action = parts[1]
        torrent_id = int(parts[2])
        
        t = transmission.get_torrent(torrent_id)
        if not t:
            await query.answer("❌ Torrent not found.", show_alert=True)
            await display_manage_list(update, context, is_callback=True)
            return

        if action == "resume":
            transmission.resume_torrent(torrent_id)
            await query.answer(f"▶️ Resumed: {t.name[:20]}")
            await display_torrent_detail(update, context, torrent_id)
        elif action == "pause":
            transmission.pause_torrent(torrent_id)
            await query.answer(f"⏸ Paused: {t.name[:20]}")
            await display_torrent_detail(update, context, torrent_id)
        elif action == "delete_confirm":
            await display_delete_confirm(update, context, torrent_id)
        elif action == "rename_start":
            context.user_data["rename_torrent_id"] = torrent_id
            await query.edit_message_text(
                f"✏️ <b>Rename Torrent</b>\n\n"
                f"Current Name: <code>{html.escape(t.name)}</code>\n\n"
                f"Please type and send the new name for this torrent.\n"
                f"Type `/cancel` to abort.",
                parse_mode="HTML"
            )
            return WAITING_FOR_RENAME
        elif action == "del_keep":
            transmission.remove_torrent(torrent_id, delete_data=False)
            await query.answer(f"Removed (kept files): {t.name[:20]}")
            await display_manage_list(update, context, is_callback=True)
        elif action == "del_all":
            transmission.remove_torrent(torrent_id, delete_data=True)
            await query.answer(f"Removed (deleted files): {t.name[:20]}")
            await display_manage_list(update, context, is_callback=True)

    elif data == "nav_start":
        context.user_data["current_browse_path"] = "/downloads"
        context.user_data.pop("pending_torrent", None)  # Ensure not adding torrent
        await show_directory_browser(update, context, query=query)
        return WAITING_FOR_DIR

    elif data.startswith("dirset_"):
        parts = data.split(":")
        action_parts = parts[0].split("_")
        action = action_parts[1]  # "default" or "forget"
        idx = int(parts[1])
        recent_dirs = storage.get_recent_dirs()
        
        if 0 <= idx < len(recent_dirs):
            selected_dir = recent_dirs[idx]
            if action == "default":
                try:
                    client = transmission.get_client()
                    client.set_session(download_dir=selected_dir)
                    await query.answer(f"📌 Set default path to: {selected_dir}", show_alert=True)
                except Exception as e:
                    await query.answer(f"❌ Failed to set default: {e}", show_alert=True)
            elif action == "forget":
                recent_dirs.pop(idx)
                storage.save()
                await query.answer(f"🗑 Forgot path: {selected_dir}")
                
        await display_dirs(update, context, is_callback=True)
        return WAITING_FOR_DIR

def validate_new_dir_path(current_path: str, folder_name: str) -> tuple[bool, str]:
    """
    Validates and constructs the new directory path.
    Prevents path traversal attacks and checks constraints.
    Returns (is_valid, resolved_path).
    """
    if not folder_name:
        return False, ""
        
    sanitized_name = re.sub(r'[\\/*?:"<>|]', "", folder_name)
    if not sanitized_name:
        return False, ""

    # Path traversal check: ensure current_path itself starts with /downloads
    current_path = os.path.normpath(current_path).replace("\\", "/")
    if not current_path.startswith("/downloads"):
        current_path = "/downloads"
        
    new_dir_path = os.path.normpath(os.path.join(current_path, sanitized_name)).replace("\\", "/")
    
    # Ensure the new path is strictly a subfolder of current_path and still starts with /downloads
    try:
        common_path = os.path.commonpath([current_path, new_dir_path]).replace("\\", "/")
    except ValueError:
        common_path = ""
        
    if common_path != current_path or new_dir_path == current_path or not new_dir_path.startswith("/downloads"):
        return False, ""
        
    return True, new_dir_path

@check_user
async def handle_new_dir_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives folder name, creates it on host (via container mount), and adds the torrent."""
    folder_name = update.message.text.strip()
    current_path = context.user_data.get("current_browse_path", "/downloads")
    
    is_valid, new_dir_path = validate_new_dir_path(current_path, folder_name)
    if not is_valid:
        await update.message.reply_text("❌ Invalid folder name. Path traversal or invalid folder structure detected.")
        return WAITING_FOR_NEW_DIR_NAME

    try:
        # Create directory on the host (since host drive is mounted to /downloads)
        os.makedirs(new_dir_path, exist_ok=True)
        
        if "pending_torrent" in context.user_data:
            await update.message.reply_text(f"📁 Created folder: `{new_dir_path}`\n⏳ Adding torrent...")
            await process_torrent_addition(update, context, new_dir_path)
        else:
            client = transmission.get_client()
            client.set_session(download_dir=new_dir_path)
            storage.add_recent_dir(new_dir_path)
            await update.message.reply_text(
                f"📁 Created folder: `{new_dir_path}`\n"
                f"✅ **Transmission Default Path Updated!**",
                parse_mode="Markdown"
            )
        return ConversationHandler.END
    except Exception as e:
        if "pending_torrent" in context.user_data:
            await update.message.reply_text(
                f"⚠️ Failed to create folder ({e}).\n"
                f"Attempting to add torrent anyway (Transmission daemon might create it)..."
            )
            await process_torrent_addition(update, context, new_dir_path)
        else:
            await update.message.reply_text(f"❌ Failed to create folder or set default: {e}")
        return ConversationHandler.END

@check_user
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels custom directory input dialog."""
    context.user_data.pop("pending_torrent", None)
    context.user_data.pop("pending_filename", None)
    context.user_data.pop("current_browse_path", None)
    await update.message.reply_text("❌ Canceled.", reply_markup=None)
    return ConversationHandler.END

async def display_status(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    """Displays active and recent torrent status."""
    try:
        torrents = transmission.get_torrents()
    except Exception as e:
        logger.error(f"Error fetching torrents: {e}")
        msg = "❌ Cannot connect to Transmission RPC server."
        if is_callback:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    if not torrents:
        msg = "📭 No torrents in Transmission."
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="status_refresh")]]
        if is_callback:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    active_statuses = ["downloading", "seeding", "verifying", "checking"]
    sorted_torrents = sorted(
        torrents,
        key=lambda x: (x.status in active_statuses, x.added_date),
        reverse=True
    )
    
    disk_info = get_disk_space_info()
    msg_lines = ["📊 <b>Transmission Status:</b>\n", disk_info + "\n"]
    keyboard = []
    
    display_limit = 10
    for idx, t in enumerate(sorted_torrents[:display_limit]):
        # transmission-rpc v7+ progress property is already in 0-100% scale
        progress = t.progress
        
        status_emoji = "⏳"
        if t.status == "downloading":
            status_emoji = "📥"
        elif t.status == "seeding":
            status_emoji = "📤"
        elif t.status == "stopped" or t.status == "paused":
            status_emoji = "⏸"
        elif t.status == "check pending" or t.status == "checking":
            status_emoji = "🔍"

        # Shorten torrent name for conciseness
        short_name = t.name
        if len(short_name) > 35:
            short_name = short_name[:32] + "..."

        escaped_name = html.escape(short_name)
        t_msg = f"{status_emoji} <b>{escaped_name}</b> | <code>{progress:.1f}%</code>"
        
        # Details row
        details = []
        if t.status == "downloading":
            details.append(f"↓ {format_speed(t.rate_download)}")
            details.append(f"👥 {t.peers_connected}(↓{t.peers_sending_to_us})")
        elif t.status == "seeding":
            details.append(f"↑ {format_speed(t.rate_upload)}")
            details.append(f"👥 {t.peers_connected}(↑{t.peers_getting_from_us})")
            
        folder = os.path.basename(t.download_dir) or t.download_dir
        escaped_folder = html.escape(folder)
        details.append(f"📁 {escaped_folder}")
        
        t_msg += "\n  " + " | ".join(details) + "\n"
        msg_lines.append(t_msg)

    if len(sorted_torrents) > display_limit:
        msg_lines.append(f"\n<i>... and {len(sorted_torrents) - display_limit} more torrents.</i>")

    keyboard.append([InlineKeyboardButton("🔄 Refresh Status", callback_data="status_refresh")])

    full_msg = "\n".join(msg_lines)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        try:
            await update.callback_query.edit_message_text(
                full_msg, 
                parse_mode="HTML", 
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error updating status: {e}")
    else:
        await update.message.reply_text(
            full_msg, 
            parse_mode="HTML", 
            reply_markup=reply_markup
        )

@check_user
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for /status command."""
    await display_status(update, context, is_callback=False)

@check_user
async def dirs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays recently used and default download directories with interactive options."""
    # Initialize browse path to /downloads
    context.user_data["current_browse_path"] = "/downloads"
    # Ensure there's no pending torrent (since we started from /dirs)
    context.user_data.pop("pending_torrent", None)
    await display_dirs(update, context, is_callback=False)
    return WAITING_FOR_DIR

async def display_dirs(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    recent_dirs = storage.get_recent_dirs()
    
    msg = ["📂 <b>Transmission Download Directories:</b>\n"]
    keyboard = []
    
    default_dir = ""
    try:
        client = transmission.get_client()
        session = client.get_session()
        default_dir = session.download_dir
        escaped_default = html.escape(default_dir)
        msg.append(f"🏠 <b>Default Session Path:</b>\n<code>{escaped_default}</code>\n")
    except Exception as e:
        msg.append(f"⚠️ Could not load default: {html.escape(str(e))}\n")

            
    msg.append("🕒 <b>Recently Used Folders:</b>")
    if recent_dirs:
        for idx, d in enumerate(recent_dirs):
            escaped_d = html.escape(d)
            msg.append(f"{idx+1}. <code>{escaped_d}</code>")
            # Create interactive controls for this directory
            keyboard.append([
                InlineKeyboardButton(f"📌 Set Default {idx+1}", callback_data=f"dirset_default:{idx}"),
                InlineKeyboardButton(f"🗑 Forget {idx+1}", callback_data=f"dirset_forget:{idx}")
            ])
    else:
        msg.append("<i>No recently used folders yet.</i>")
        
    # Add buttons to start browsing all folders and cancel the conversation
    keyboard.append([
        InlineKeyboardButton("🔍 Browse Directories", callback_data="nav_start")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Cancel", callback_data="dir_cancel")
    ])
        
    full_msg = "\n".join(msg)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        try:
            await update.callback_query.edit_message_text(
                full_msg,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error updating dirs: {e}")
    else:
        await update.message.reply_text(
            full_msg,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

def get_conversation_handler():
    """Returns the ConversationHandler for handling torrent files and custom directories."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(
                (filters.TEXT & (filters.Regex(re.compile(r'^magnet:\?', re.IGNORECASE)) | filters.Regex(re.compile(r'^https?://', re.IGNORECASE)))) | 
                filters.Document.ALL,
                handle_torrent_input
            ),
            CommandHandler("dirs", dirs_command),
            CommandHandler("manage", manage_command)
        ],
        states={
            WAITING_FOR_DIR: [
                CallbackQueryHandler(handle_callback_query)
            ],
            WAITING_FOR_NEW_DIR_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_dir_name),
                CallbackQueryHandler(handle_callback_query)
            ],
            WAITING_FOR_RENAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rename_input),
                CallbackQueryHandler(handle_callback_query)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(handle_callback_query)
        ],
        per_message=False
    )

def get_disk_space_info():
    """Reads OMV host /downloads directory disk usage and alt speed (turtle) status."""
    try:
        # Check alternative speeds status (Turtle Mode)
        client = transmission.get_client()
        session = client.get_session()
        turtle_status = "ON 🐢" if session.alt_speed_enabled else "OFF ⚡"
        
        # Read mounted downloads directory usage
        total, used, free = shutil.disk_usage("/downloads")
        total_gb = total / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        percent = (used / total) * 100
        
        if total_gb >= 1000:
            disk_str = f"💾 <b>Disk Space:</b> {used_gb/1024:.2f} TB / {total_gb/1024:.2f} TB ({percent:.1f}% used, {free_gb/1024:.2f} TB free)"
        else:
            disk_str = f"💾 <b>Disk Space:</b> {used_gb:.1f} GB / {total_gb:.1f} GB ({percent:.1f}% used, {free_gb:.1f} GB free)"
            
        return f"{disk_str}\n🐢 <b>Turtle Mode:</b> {turtle_status}"
    except Exception as e:
        return f"⚠️ <b>Disk Space:</b> Error reading ({e})"

@check_user
async def manage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for /manage command."""
    await display_manage_list(update, context, is_callback=False)

async def display_manage_list(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    """Displays list of torrents as buttons for management."""
    try:
        torrents = transmission.get_torrents()
    except Exception as e:
        logger.error(f"Error fetching torrents: {e}")
        msg = "❌ Cannot connect to Transmission RPC server."
        if is_callback:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    if not torrents:
        msg = "📭 No torrents to manage."
        if is_callback:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    # Sort torrents
    active_statuses = ["downloading", "seeding", "verifying", "checking"]
    sorted_torrents = sorted(
        torrents,
        key=lambda x: (x.status in active_statuses, x.added_date),
        reverse=True
    )

    msg = "🎛️ <b>Transmission Manage Center</b>\n\nSelect a torrent below to control it:"
    keyboard = []

    for t in sorted_torrents[:15]:  # Show top 15
        status_emoji = "⏳"
        if t.status == "downloading":
            status_emoji = "📥"
        elif t.status == "seeding":
            status_emoji = "📤"
        elif t.status == "stopped" or t.status == "paused":
            status_emoji = "⏸"
            
        short_name = t.name
        if len(short_name) > 25:
            short_name = short_name[:22] + "..."
            
        btn_text = f"{status_emoji} {short_name} ({t.progress:.0f}%)"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"m_select:{t.id}")])

    if len(sorted_torrents) > 15:
        msg += f"\n\n<i>Showing top 15 out of {len(sorted_torrents)} torrents.</i>"

    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="m_close")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        try:
            await update.callback_query.edit_message_text(
                msg,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Error updating manage list: {e}")
    else:
        await update.message.reply_text(
            msg,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

async def display_torrent_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, torrent_id: int):
    """Displays detailed controls for a single selected torrent."""
    query = update.callback_query
    t = transmission.get_torrent(torrent_id)
    if not t:
        await query.answer("❌ Torrent not found.", show_alert=True)
        await display_manage_list(update, context, is_callback=True)
        return

    progress = t.progress
    pbar = get_progress_bar(progress)
    
    status_emoji = "⏳"
    if t.status == "downloading":
        status_emoji = "📥"
    elif t.status == "seeding":
        status_emoji = "📤"
    elif t.status == "stopped" or t.status == "paused":
        status_emoji = "⏸"
    elif t.status == "checking" or t.status == "verifying":
        status_emoji = "🔍"

    escaped_name = html.escape(t.name)
    escaped_dir = html.escape(t.download_dir)
    
    msg = (
        f"📛 <b>Name:</b> {escaped_name}\n"
        f"🚦 <b>Status:</b> {status_emoji} {t.status.capitalize()}\n"
        f"📊 <b>Progress:</b> {pbar} <code>{progress:.1f}%</code>\n"
        f"💾 <b>Size:</b> {format_size(t.have_valid)} / {format_size(t.have_valid + t.left_until_done)}\n"
        f"📁 <b>Save Dir:</b> <code>{escaped_dir}</code>\n"
    )

    if t.status == "downloading":
        msg += f"🚀 <b>Speed:</b> ↓ {format_speed(t.rate_download)} | <b>ETA:</b> {format_eta(t.eta)}\n"
        msg += f"👥 <b>Peers:</b> {t.peers_connected} connected (↓ {t.peers_sending_to_us})\n"
    elif t.status == "seeding":
        msg += f"🚀 <b>Speed:</b> ↑ {format_speed(t.rate_upload)}\n"
        msg += f"👥 <b>Peers:</b> {t.peers_connected} connected (↑ {t.peers_getting_from_us})\n"

    keyboard = []
    control_row = []
    if t.status in ["stopped", "paused"]:
        control_row.append(InlineKeyboardButton("▶️ Resume", callback_data=f"m_action:resume:{torrent_id}"))
    else:
        control_row.append(InlineKeyboardButton("⏸ Pause", callback_data=f"m_action:pause:{torrent_id}"))
    
    control_row.append(InlineKeyboardButton("🗑 Delete", callback_data=f"m_action:delete_confirm:{torrent_id}"))
    keyboard.append(control_row)
    
    # Add Rename and Back buttons
    keyboard.append([
        InlineKeyboardButton("✏️ Rename", callback_data=f"m_action:rename_start:{torrent_id}"),
        InlineKeyboardButton("↩️ Back to List", callback_data="m_refresh_list")
    ])

    await query.edit_message_text(
        msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def display_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, torrent_id: int):
    """Displays deletion options (keep data vs delete files) for a torrent."""
    query = update.callback_query
    t = transmission.get_torrent(torrent_id)
    if not t:
        await query.answer("❌ Torrent not found.", show_alert=True)
        await display_manage_list(update, context, is_callback=True)
        return

    escaped_name = html.escape(t.name)
    msg = (
        f"🗑 <b>Confirm Delete</b>\n\n"
        f"Are you sure you want to delete:\n"
        f"<code>{escaped_name}</code>?"
    )

    keyboard = [
        [
            InlineKeyboardButton("🗑 Keep Data", callback_data=f"m_action:del_keep:{torrent_id}"),
            InlineKeyboardButton("🔥 Delete Data", callback_data=f"m_action:del_all:{torrent_id}")
        ],
        [InlineKeyboardButton("↩️ Back", callback_data=f"m_select:{torrent_id}")]
    ]

    await query.edit_message_text(
        msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@check_user

async def turtle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggles Transmission alternative speed limits (Turtle Mode)."""
    try:
        client = transmission.get_client()
        session = client.get_session()
        current = session.alt_speed_enabled
        new_state = not current
        client.set_session(alt_speed_enabled=new_state)
        
        alt_dl = session.alt_speed_down
        alt_ul = session.alt_speed_up
        
        if new_state:
            await update.message.reply_text(
                f"🐢 <b>Turtle Mode is now: ON</b>\n"
                f"Alternative Speed Limits active:\n"
                f"↓ {alt_dl} KB/s | ↑ {alt_ul} KB/s",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"⚡ <b>Turtle Mode is now: OFF</b>\n"
                f"Standard speed limits restored.",
                parse_mode="HTML"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to toggle Turtle Mode: {e}")

@check_user
async def handle_rename_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives new name text, renames the torrent in Transmission, and ends the sub-dialog."""
    new_name = update.message.text.strip()
    torrent_id = context.user_data.get("rename_torrent_id")
    
    if not new_name:
        await update.message.reply_text("❌ Name cannot be empty. Please send a valid name.")
        return WAITING_FOR_RENAME
        
    if not torrent_id:
        await update.message.reply_text("❌ Session lost. Please restart management.")
        return ConversationHandler.END
        
    try:
        client = transmission.get_client()
        t = client.get_torrent(torrent_id)
        if not t:
            await update.message.reply_text("❌ Torrent not found in Transmission.")
            return ConversationHandler.END
            
        # Execute rename
        client.rename_torrent_path(torrent_id, t.name, new_name)
        
        escaped_new_name = html.escape(new_name)
        await update.message.reply_text(
            f"✅ <b>Torrent Renamed Successfully!</b>\n\n"
            f"🆕 New Name: <code>{escaped_new_name}</code>",
            parse_mode="HTML"
        )
        
        # Clean session
        context.user_data.pop("rename_torrent_id", None)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to rename: {e}")
        return ConversationHandler.END
