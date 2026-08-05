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

def extract_torrents_from_text(text: str) -> list:
    """Extracts all magnet links and HTTP/HTTPS URLs from text."""
    if not text:
        return []
    pattern = r'(?:magnet:\?[^\s<>"\'`]+|https?://[^\s<>"\'`]+)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    results = []
    seen = set()
    for item in matches:
        item_clean = item.strip().rstrip('.,);:')
        if item_clean and item_clean not in seen:
            seen.add(item_clean)
            results.append(item_clean)
    return results

async def show_directory_browser(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    """Renders the directory browser inline keyboard."""
    current_path = context.user_data.get("current_browse_path", "/downloads")
    
    # Get subdirectories
    subdirs = get_subdirs(current_path)
    # Store subdirs in context for lookup
    context.user_data["browse_subdirs"] = subdirs
    
    pending_torrents = context.user_data.get("pending_torrents", [])
    if not pending_torrents and "pending_torrent" in context.user_data:
        pending_torrents = [context.user_data["pending_torrent"]]
    
    has_pending = len(pending_torrents) > 0
    pending_count = len(pending_torrents)

    # Header text
    escaped_path = html.escape(current_path)
    msg_lines = [
        "📂 <b>Directory Browser</b>\n",
        f"📍 <b>Current Path:</b> <code>{escaped_path}</code>"
    ]
    if has_pending:
        msg_lines.append(f"🔗 <b>Pending Downloads:</b> <code>{pending_count}</code> item(s)")
        
    msg_lines.append("\nSelect a folder below to navigate inside it, or choose one of the options:")
    msg = "\n".join(msg_lines)
    
    keyboard = []
    
    # List subdirectories (limit to 10 to keep menu readable)
    for idx, path in enumerate(subdirs[:10]):
        name = os.path.basename(path)
        keyboard.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"nav_sub:{idx}")])
        
    if len(subdirs) > 10:
        keyboard.append([InlineKeyboardButton(f"➕ ... and {len(subdirs) - 10} more folders", callback_data="noop")])

    # Confirmation and creation buttons
    confirm_text = f"✅ Download ({pending_count}) to Here" if (has_pending and pending_count > 1) else ("✅ Select for Download" if has_pending else "📌 Set as Default Path")
    keyboard.append([
        InlineKeyboardButton(confirm_text, callback_data="nav_confirm")
    ])
    keyboard.append([
        InlineKeyboardButton("🆕 Create Folder Here", callback_data="nav_create_dir")
    ])
    
    # Recent Directories section
    recent_dirs = storage.get_recent_dirs()
    if recent_dirs:
        for idx, rdir in enumerate(recent_dirs[:5]):
            rdir_display = rdir if len(rdir) <= 30 else f".../{os.path.basename(rdir)}"
            keyboard.append([InlineKeyboardButton(f"🕒 {rdir_display}", callback_data=f"nav_recent:{idx}")])
        keyboard.append([InlineKeyboardButton("🗑 Clear Recent History", callback_data="clear_recent")])

    # Navigation buttons (Back / Cancel)
    nav_row = []
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
    Invoked when user sends a text message that could contain magnet link(s)/URL(s) or uploads a document.
    """
    torrents = []
    file_name = ""

    if update.message.document:
        doc = update.message.document
        if doc.file_name.endswith(".torrent") or doc.mime_type == "application/x-bittorrent":
            file_name = doc.file_name
            telegram_file = await doc.get_file()
            torrent_bytes = await telegram_file.download_as_bytearray()
            torrents.append(bytes(torrent_bytes))
        else:
            await update.message.reply_text("❌ Provided file is not a torrent file.")
            return ConversationHandler.END
    elif update.message.text:
        text = update.message.text.strip()
        torrents = extract_torrents_from_text(text)
        if not torrents:
            await update.message.reply_text(
                "❌ Please send valid magnet link(s), HTTP/HTTPS torrent URL(s), or upload a `.torrent` file."
            )
            return ConversationHandler.END

    if not torrents:
        return ConversationHandler.END

    # Store the input in user data
    context.user_data["pending_torrents"] = torrents
    context.user_data["pending_filename"] = file_name
    
    # Initialize the browse path to /downloads
    context.user_data["current_browse_path"] = "/downloads"

    # Start directory browsing
    await show_directory_browser(update, context)
    return WAITING_FOR_DIR

async def process_torrent_addition(update: Update, context: ContextTypes.DEFAULT_TYPE, download_dir: str):
    """Helper function to add torrent(s) to Transmission and reply."""
    pending_torrents = context.user_data.get("pending_torrents", [])
    if not pending_torrents and "pending_torrent" in context.user_data:
        pending_torrents = [context.user_data["pending_torrent"]]

    if not pending_torrents:
        await update.effective_message.reply_text("❌ No pending torrent found. Please try again.")
        return

    success_items = []
    failed_items = []

    for idx, item in enumerate(pending_torrents, start=1):
        try:
            torrent = transmission.add_torrent(item, download_dir=download_dir)
            success_items.append((idx, torrent))
        except Exception as e:
            logger.error(f"Error adding torrent item {idx}: {e}")
            failed_items.append((idx, str(e)))

    # Save directory to recent directories if at least one download succeeded or directory was specified
    if download_dir and (success_items or not failed_items):
        storage.add_recent_dir(download_dir)

    # Clear pending state
    context.user_data.pop("pending_torrents", None)
    context.user_data.pop("pending_torrent", None)
    context.user_data.pop("pending_filename", None)
    context.user_data.pop("current_browse_path", None)

    escaped_dir = html.escape(download_dir)

    if len(pending_torrents) == 1:
        if success_items:
            _, torrent = success_items[0]
            escaped_name = html.escape(torrent.name)
            msg = (
                f"✅ <b>Torrent Added Successfully!</b>\n\n"
                f"📛 <b>Name:</b> {escaped_name}\n"
                f"📂 <b>Directory:</b> <code>{escaped_dir}</code>\n"
                f"🆔 <b>ID:</b> <code>{torrent.id}</code>"
            )
        else:
            _, err_msg = failed_items[0]
            msg = f"❌ Error adding torrent: {html.escape(err_msg)}"
    else:
        if len(success_items) == len(pending_torrents):
            msg_lines = [
                f"✅ <b>All {len(success_items)} Torrents Added Successfully!</b>\n",
                f"📂 <b>Directory:</b> <code>{escaped_dir}</code>\n"
            ]
            for idx, torrent in success_items:
                escaped_name = html.escape(torrent.name)
                msg_lines.append(f"{idx}. 📛 <b>{escaped_name}</b> (ID: <code>{torrent.id}</code>)")
            msg = "\n".join(msg_lines)
        elif success_items:
            msg_lines = [
                f"⚠️ <b>{len(success_items)} of {len(pending_torrents)} Torrents Added</b>\n",
                f"📂 <b>Directory:</b> <code>{escaped_dir}</code>\n",
                "<b>Added:</b>"
            ]
            for idx, torrent in success_items:
                escaped_name = html.escape(torrent.name)
                msg_lines.append(f"✅ {idx}. 📛 <b>{escaped_name}</b> (ID: <code>{torrent.id}</code>)")
            msg_lines.append("\n<b>Failed:</b>")
            for idx, err_msg in failed_items:
                msg_lines.append(f"❌ {idx}. {html.escape(err_msg)}")
            msg = "\n".join(msg_lines)
        else:
            msg_lines = [f"❌ <b>Failed to add all {len(pending_torrents)} torrents:</b>\n"]
            for idx, err_msg in failed_items:
                msg_lines.append(f"❌ {idx}. {html.escape(err_msg)}")
            msg = "\n".join(msg_lines)

    keyboard = [[InlineKeyboardButton("📊 Check Status", callback_data="status_refresh")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)


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
        has_pending = ("pending_torrents" in context.user_data and len(context.user_data["pending_torrents"]) > 0) or ("pending_torrent" in context.user_data)
        if has_pending:
            pending_count = len(context.user_data.get("pending_torrents", [])) or 1
            await query.edit_message_text(f"⏳ Adding {pending_count} torrent(s) to `{selected_dir}`...", parse_mode="Markdown")
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

    elif data.startswith("nav_recent:"):
        idx = int(data.split(":")[1])
        recent_dirs = storage.get_recent_dirs()
        if 0 <= idx < len(recent_dirs):
            selected_dir = recent_dirs[idx]
            has_pending = ("pending_torrents" in context.user_data and len(context.user_data["pending_torrents"]) > 0) or ("pending_torrent" in context.user_data)
            if has_pending:
                pending_count = len(context.user_data.get("pending_torrents", [])) or 1
                await query.edit_message_text(f"⏳ Adding {pending_count} torrent(s) to `{selected_dir}`...", parse_mode="Markdown")
                await process_torrent_addition(update, context, selected_dir)
                return ConversationHandler.END
            else:
                context.user_data["current_browse_path"] = selected_dir
                await show_directory_browser(update, context, query=query)
                return WAITING_FOR_DIR

    elif data == "clear_recent" or data == "dirset_clear_all":
        storage.clear_recent_dirs()
        await query.answer("🗑 Recent directory history cleared.", show_alert=True)
        if "pending_torrents" in context.user_data or "pending_torrent" in context.user_data or context.user_data.get("current_browse_path"):
            await show_directory_browser(update, context, query=query)
        else:
            await display_dirs(update, context, is_callback=True)
        return WAITING_FOR_DIR

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
        context.user_data.pop("pending_torrents", None)
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
        context.user_data.pop("pending_torrents", None)
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
                storage.remove_recent_dir(selected_dir)
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
        
        has_pending = ("pending_torrents" in context.user_data and len(context.user_data["pending_torrents"]) > 0) or ("pending_torrent" in context.user_data)
        if has_pending:
            await update.message.reply_text(f"📁 Created folder: `{new_dir_path}`\n⏳ Adding torrent(s)...")
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
        has_pending = ("pending_torrents" in context.user_data and len(context.user_data["pending_torrents"]) > 0) or ("pending_torrent" in context.user_data)
        if has_pending:
            await update.message.reply_text(
                f"⚠️ Failed to create folder ({e}).\n"
                f"Attempting to add torrent(s) anyway (Transmission daemon might create it)..."
            )
            await process_torrent_addition(update, context, new_dir_path)
        else:
            await update.message.reply_text(f"❌ Failed to create folder or set default: {e}")
        return ConversationHandler.END

@check_user
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels custom directory input dialog."""
    context.user_data.pop("pending_torrents", None)
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
    context.user_data.pop("pending_torrents", None)
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
        keyboard.append([
            InlineKeyboardButton("🗑 Clear All Recent History", callback_data="dirset_clear_all")
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
                (filters.TEXT & (filters.Regex(re.compile(r'magnet:\?', re.IGNORECASE)) | filters.Regex(re.compile(r'https?://', re.IGNORECASE)))) | 
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
