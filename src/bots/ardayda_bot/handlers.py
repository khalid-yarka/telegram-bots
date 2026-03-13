# src/bots/ardayda_bot/handlers.py
"""
Updated message handlers with:
- Rate limit integration
- Admin broadcast commands
- SQLite state management
- Better error handling
"""

from telebot.types import Message, CallbackQuery
from src.bots.ardayda_bot.helpers import safe_edit_message
from src.bots.ardayda_bot import (
    database,
    buttons,
    text,
    registration,
    upload_flow,
    search_flow,
    profile,
    admin_sql,
)
from src.bots.ardayda_bot.state_manager import (
    get_state_manager,
    get_user_status,
    set_user_status,
    clear_user_status,
    set_last_message
)
from src.bots.ardayda_bot.rate_limiter import can_upload, can_search, get_rate_limiter
from src.bots.ardayda_bot.conflict_manager import (
    check_and_resolve_conflict, 
    clear_previous_operation,
    save_message_id,
    operation_ended,
    broadcast_to_users,
    send_direct_message,
    warn_user,
    get_user_list_for_admin
)
from src.bots.ardayda_bot.admin import is_admin
from src.bots.ardayda_bot.admin_handlers import (
    show_admin_panel,
    show_users_list,
    show_user_details,
    show_user_pdfs,
    handle_warn_user,
    handle_suspend_user,
    handle_unsuspend_user,
    handle_make_admin,
    handle_remove_admin,
    show_pdfs_list,
    show_pdf_details,
    handle_delete_pdf,
    handle_pdf_user,
    handle_pdf_stats,
    show_stats,
    show_user_stats,
    show_pdf_stats,
    show_logs,
    handle_clear_logs,
    handle_confirmation,
    handle_cancellation
)

import logging

logger = logging.getLogger(__name__)


# ---------- FIRST MESSAGE (NEW USER) ----------
def handle_first_message(bot, message: Message):
    """Handle first message from a new user - start registration"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Add user to database
    database.add_user(user_id)
    
    # Start registration flow
    registration.start(bot, user_id, chat_id)
    
    logger.info(f"New user {user_id} started registration")


# ---------- TEXT MESSAGES ----------
def handle_message(bot, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text_msg = message.text.strip()
    
    # Check suspension
    if database.get_user_suspended(user_id):
        bot.send_message(
            chat_id, 
            "🚫 Your account has been suspended. Contact an admin for assistance."
        )
        return
    
    # Get current status from state manager
    status = get_user_status(user_id)
    
    # New user
    if not status and not database.user_exists(user_id):
        handle_first_message(bot, message)
        return
    
    # Handle admin SQL commands first (special case)
    if text_msg.startswith('/sql ') and is_admin(user_id):
        from src.bots.ardayda_bot.admin_sql import handle_sql_command
        handle_sql_command(bot, message)
        return
    
    # Handle admin broadcast commands
    if text_msg.startswith('/broadcast ') and is_admin(user_id):
        _handle_broadcast_command(bot, message)
        return
    
    if text_msg.startswith('/dm ') and is_admin(user_id):
        _handle_dm_command(bot, message)
        return
    
    if text_msg.startswith('/warn ') and is_admin(user_id):
        _handle_warn_command(bot, message)
        return
    
    # Check for cancel
    if text_msg in ["/cancel", "❌ Cancel"]:
        handle_cancel(bot, message)
        return
    
    # Route based on status
    if status and status.startswith("reg:"):
        registration.handle_message(bot, message)
    elif status and status.startswith("upload:"):
        bot.send_message(
            chat_id, 
            "📤 Please send the PDF file, or tap ❌ Cancel to exit.", 
            reply_markup=buttons.cancel_button()
        )
    elif status and status.startswith("search:"):
        bot.send_message(
            chat_id, 
            "🔍 Please use the buttons below, or tap ❌ Cancel to exit.",
            reply_markup=buttons.cancel_button()
        )
    elif status == database.STATUS_MENU_HOME or not status:
        handle_menu_selection(bot, message)
    else:
        # Unknown status - reset
        clear_user_status(user_id)
        bot.send_message(
            chat_id, 
            "🔄 Session reset. Returning to main menu.",
            reply_markup=buttons.main_menu(user_id)
        )


# ---------- DOCUMENTS (PDF FILES) ----------
def handle_document(bot, message: Message):
    """Route document messages based on user status"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check if user is suspended
    if database.get_user_suspended(user_id):
        bot.send_message(
            chat_id,
            "🚫 Your account has been suspended. Please contact an admin."
        )
        return
    
    # Get current user status
    status = get_user_status(user_id)
    
    # Check if user is in upload flow
    if status and status.startswith("upload:"):
        upload_flow.handle_pdf_upload(bot, message)
        return
    
    # If user is in search flow but sends a document
    if status and status.startswith("search:"):
        bot.send_message(
            chat_id,
            "🔍 You're in search mode. Please use the buttons to search.\n\n"
            "To upload a PDF, please go back to main menu and select 'Upload'.",
            reply_markup=buttons.main_menu(user_id)
        )
        return
    
    # Not in upload flow - suggest starting upload
    bot.send_message(
        chat_id,
        "⚠️ Please start upload from the menu first.\n\n"
        "Tap '📤 Upload' in the main menu to begin.",
        reply_markup=buttons.main_menu(user_id)
    )


# ---------- CALLBACK QUERIES (INLINE BUTTONS) ----------
def handle_callback(bot, call: CallbackQuery):
    """Route all callback queries based on user status"""
    user_id = call.from_user.id
    data = call.data
    
    # Get current user status
    status = get_user_status(user_id)
    
    if not status and not database.user_exists(user_id):
        # New user - should not have callbacks
        bot.answer_callback_query(call.id, "Please start with /start")
        return
    
    # ==================== ADMIN CALLBACKS ====================
    if data.startswith("admin_"):
        # Verify user is admin
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Admin access required!")
            return
        
        # Admin Panel Main
        if data == "admin_panel":
            show_admin_panel(bot, call)
        
        # User Management
        elif data.startswith("admin_users:"):
            page = int(data.split(":")[1])
            show_users_list(bot, call, page)
        
        elif data.startswith("admin_view_user:"):
            parts = data.split(":")
            target_user_id = int(parts[1])
            page = int(parts[2]) if len(parts) > 2 else 1
            show_user_details(bot, call, target_user_id, page)
        
        elif data.startswith("admin_user_pdfs:"):
            parts = data.split(":")
            target_user_id = int(parts[1])
            page = int(parts[2]) if len(parts) > 2 else 1
            show_user_pdfs(bot, call, target_user_id, page)
        
        elif data.startswith("admin_warn:"):
            target_user_id = int(data.split(":")[1])
            handle_warn_user(bot, call, target_user_id)
        
        elif data.startswith("admin_suspend:"):
            target_user_id = int(data.split(":")[1])
            if is_admin(target_user_id) or user_id == target_user_id:
                bot.answer_callback_query(call.id, "⛔ Action Denied!")
                return 
            handle_suspend_user(bot, call, target_user_id)
        
        elif data.startswith("admin_unsuspend:"):
            target_user_id = int(data.split(":")[1])
            handle_unsuspend_user(bot, call, target_user_id)
        
        elif data.startswith("admin_makeadmin:"):
            target_user_id = int(data.split(":")[1])
            handle_make_admin(bot, call, target_user_id)
        
        elif data.startswith("admin_removeadmin:"):
            target_user_id = int(data.split(":")[1])
            if target_user_id == 2094426161:  # Super admin protection
                bot.answer_callback_query(call.id, "Action Denied")
                return
            handle_remove_admin(bot, call, target_user_id)
        
        # PDF Management
        elif data.startswith("admin_pdfs:"):
            page = int(data.split(":")[1])
            show_pdfs_list(bot, call, page)
        
        elif data.startswith("admin_view_pdf:"):
            parts = data.split(":")
            pdf_id = int(parts[1])
            page = int(parts[2]) if len(parts) > 2 else 1
            show_pdf_details(bot, call, pdf_id, page)
        
        elif data.startswith("admin_delete_pdf:"):
            pdf_id = int(data.split(":")[1])
            handle_delete_pdf(bot, call, pdf_id)
        
        elif data.startswith("admin_pdf_user:"):
            pdf_id = int(data.split(":")[1])
            handle_pdf_user(bot, call, pdf_id)
        
        elif data.startswith("admin_pdf_stats:"):
            pdf_id = int(data.split(":")[1])
            handle_pdf_stats(bot, call, pdf_id)
        
        # Statistics
        elif data == "admin_stats":
            show_stats(bot, call)
        
        elif data == "admin_stats_users":
            show_user_stats(bot, call)
        
        elif data == "admin_stats_pdfs":
            show_pdf_stats(bot, call)
        
        elif data == "admin_stats_subjects":
            bot.answer_callback_query(call.id, "Coming soon!")
        
        elif data == "admin_stats_tags":
            bot.answer_callback_query(call.id, "Coming soon!")
        
        elif data == "admin_stats_daily":
            bot.answer_callback_query(call.id, "Coming soon!")
        
        # Logs
        elif data.startswith("admin_logs:"):
            page = int(data.split(":")[1])
            show_logs(bot, call, page)
        
        elif data == "admin_clear_logs":
            handle_clear_logs(bot, call)
        
        # Rate Limit Management
        elif data.startswith("admin_reset_upload:"):
            target_user_id = int(data.split(":")[1])
            _handle_reset_upload_limit(bot, call, target_user_id)
        
        elif data.startswith("admin_reset_search:"):
            target_user_id = int(data.split(":")[1])
            _handle_reset_search_limit(bot, call, target_user_id)
        
        # Confirmations
        elif data.startswith("admin_confirm_"):
            parts = data.replace("admin_confirm_", "").split(":")
            action = parts[0]
            target_id = int(parts[1])
            handle_confirmation(bot, call, action, target_id)
        
        elif data.startswith("admin_cancel_"):
            parts = data.replace("admin_cancel_", "").split(":")
            action = parts[0]
            target_id = int(parts[1])
            handle_cancellation(bot, call, action, target_id)
        
        # Back button
        elif data == "admin_back":
            try:
                logger.info(f"Admin {user_id} returning to main menu")
                clear_user_status(user_id)
                
                safe_edit_message(
                    bot=bot,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text.HOME_WELCOME,
                    reply_markup=buttons.main_menu(user_id),
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                logger.error(f"Error in admin_back: {e}")
                try:
                    bot.send_message(
                        call.message.chat.id,
                        text.HOME_WELCOME,
                        reply_markup=buttons.main_menu(user_id),
                        parse_mode="Markdown"
                    )
                except:
                    pass
            
            bot.answer_callback_query(call.id)
            return
        else:
            bot.answer_callback_query(call.id, "Unknown admin action")
        
        return
    
    # ==================== REGULAR CALLBACKS ====================
    
    # ----- REGISTRATION CALLBACKS -----
    if status and status.startswith("reg:"):
        registration.handle_callback(bot, call)
        return
    
    # ----- UPLOAD CALLBACKS -----
    if status and status.startswith("upload:") and data.startswith("upload_"):
        upload_flow.handle_callback(bot, call)
        return
    
    # ----- SEARCH CALLBACKS -----
    if status and status.startswith("search:") and data.startswith(("search_", "pdf_page:", "pdf_send:")):
        search_flow.handle_callback(bot, call)
        return
    
    # ----- SQL CONFIRMATION -----
    if data.startswith("sql_confirm:"):
        query = data[12:].strip()
        chat_id = call.message.chat.id
        admin_sql.execute_and_send_result(bot, chat_id, query)
        return
    
    # ----- STALE BUTTON -----
    bot.answer_callback_query(
        call.id, 
        "❌ This action is no longer available. Please start over."
    )


# ---------- MENU SELECTION ----------
def handle_menu_selection(bot, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text_msg = message.text.strip()
    
    # Map menu options to operations
    op_map = {
        "📤 Upload": "upload",
        "📤 Upload PDF": "upload",
        "🔍 Search": "search",
        "🔍 Search PDF": "search"
    }
    
    # Profile doesn't need conflict check
    if text_msg == "👤 Profile":
        profile.show(bot, message)
        return
    
    # Admin Panel
    if text_msg == "⚙️ Admin Panel" and is_admin(user_id):
        show_admin_panel(bot, message)
        return
    
    # Check for conflicts if starting an operation
    if text_msg in op_map:
        can_proceed, conflict_msg = check_and_resolve_conflict(
            bot, user_id, chat_id, op_map[text_msg]
        )
        
        if not can_proceed:
            bot.send_message(
                chat_id, 
                conflict_msg, 
                reply_markup=buttons.cancel_button()
            )
            return
        
        # Clear previous operation
        clear_previous_operation(bot, user_id, chat_id)
    
    # Route to appropriate flow
    if text_msg in ["📤 Upload", "📤 Upload PDF"]:
        set_user_status(user_id, database.STATUS_UPLOAD_WAIT_PDF)
        msg = bot.send_message(
            chat_id, 
            text.UPLOAD_START, 
            reply_markup=buttons.cancel_button()
        )
        save_message_id(user_id, msg.message_id)
        upload_flow.start(bot, message)
        
    elif text_msg in ["🔍 Search", "🔍 Search PDF"]:
        set_user_status(user_id, database.STATUS_SEARCH_SUBJECT)
        msg = bot.send_message(
            chat_id,
            text.SEARCH_START,
            reply_markup=buttons.search_subject_buttons(text.SUBJECTS),
            parse_mode="Markdown"
        )
        save_message_id(user_id, msg.message_id)
        search_flow.start(bot, message)


# ---------- CANCEL HANDLER ----------
def handle_cancel(bot, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    status = get_user_status(user_id)
    
    # Registration cannot be cancelled mid-way
    if status and status.startswith("reg:"):
        bot.send_message(
            chat_id, 
            "❌ Registration cannot be cancelled. Please complete it to use the bot."
        )
        return
    
    # Clean up and end operation
    operation_ended(bot, user_id, chat_id)
    
    bot.send_message(
        chat_id,
        text.CANCELLED,
        reply_markup=buttons.main_menu(user_id),
        parse_mode="Markdown"
    )
    
    logger.info(f"User {user_id} cancelled operation")


# ==================== ADMIN COMMAND HANDLERS ====================

def _handle_broadcast_command(bot, message: Message):
    """Handle /broadcast command for admins"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not is_admin(user_id):
        bot.send_message(chat_id, "⛔ Admin access required!")
        return
    
    # Parse command: /broadcast [filter] [value] message
    parts = message.text.split(maxsplit=3)
    
    if len(parts) < 2:
        bot.send_message(
            chat_id,
            "📢 *Broadcast Help*\n\n"
            "Usage:\n"
            "• `/broadcast all Your message` - Send to all users\n"
            "• `/broadcast region Bari Your message` - Send to region\n"
            "• `/broadcast school 'Bandar Qasim' Your message` - Send to school\n"
            "• `/broadcast class F4 Your message` - Send to class\n\n"
            "Example: `/broadcast all Hello everyone!`",
            parse_mode="Markdown"
        )
        return
    
    if len(parts) == 2:
        # /broadcast all message
        filter_type = "all"
        filter_value = None
        message_text = parts[1]
    elif len(parts) == 3:
        # /broadcast type message
        filter_type = parts[1].lower()
        filter_value = None
        message_text = parts[2]
    else:
        # /broadcast type value message
        filter_type = parts[1].lower()
        filter_value = parts[2]
        message_text = parts[3]
    
    # Send confirmation
    confirm_msg = bot.send_message(
        chat_id,
        f"📢 *Broadcast Preview*\n\n"
        f"Filter: {filter_type}\n"
        f"{f'Value: {filter_value}\n' if filter_value else ''}\n"
        f"Message:\n{message_text}\n\n"
        f"Send this broadcast?",
        reply_markup=buttons.yes_no_buttons('broadcast', f"{filter_type}:{filter_value or ''}")
    )
    
    set_last_message(user_id, confirm_msg.message_id)


def _handle_dm_command(bot, message: Message):
    """Handle /dm command for direct messages"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not is_admin(user_id):
        bot.send_message(chat_id, "⛔ Admin access required!")
        return
    
    # Parse: /dm user_id message
    parts = message.text.split(maxsplit=2)
    
    if len(parts) < 3:
        bot.send_message(
            chat_id,
            "📨 *Direct Message Help*\n\n"
            "Usage: `/dm 123456789 Your message here`\n\n"
            "Example: `/dm 2094426161 Hello there!`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(parts[1])
        message_text = parts[2]
        
        result = send_direct_message(bot, user_id, target_user_id, message_text)
        
        if result['success']:
            bot.send_message(chat_id, f"✅ {result['message']}")
        else:
            bot.send_message(chat_id, f"❌ {result['error']}")
            
    except ValueError:
        bot.send_message(chat_id, "❌ Invalid user ID. Must be a number.")


def _handle_warn_command(bot, message: Message):
    """Handle /warn command"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not is_admin(user_id):
        bot.send_message(chat_id, "⛔ Admin access required!")
        return
    
    # Parse: /warn user_id reason
    parts = message.text.split(maxsplit=2)
    
    if len(parts) < 3:
        bot.send_message(
            chat_id,
            "⚠️ *Warn User Help*\n\n"
            "Usage: `/warn 123456789 Reason for warning`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(parts[1])
        reason = parts[2]
        
        result = warn_user(bot, user_id, target_user_id, reason)
        
        if result['success']:
            bot.send_message(chat_id, f"✅ {result['message']}")
        else:
            bot.send_message(chat_id, f"❌ {result['error']}")
            
    except ValueError:
        bot.send_message(chat_id, "❌ Invalid user ID. Must be a number.")


def _handle_reset_upload_limit(bot, call: CallbackQuery, target_user_id):
    """Reset upload limits for a user"""
    from src.bots.ardayda_bot.upload_flow import admin_override_upload_limit
    
    result = admin_override_upload_limit(call.from_user.id, target_user_id)
    
    if result['success']:
        bot.answer_callback_query(call.id, result['message'])
        # Refresh user view
        show_user_details(bot, call, target_user_id)
    else:
        bot.answer_callback_query(call.id, result['error'], show_alert=True)


def _handle_reset_search_limit(bot, call: CallbackQuery, target_user_id):
    """Reset search limits for a user"""
    from src.bots.ardayda_bot.search_flow import admin_override_search_limit
    
    result = admin_override_search_limit(call.from_user.id, target_user_id)
    
    if result['success']:
        bot.answer_callback_query(call.id, result['message'])
        # Refresh user view
        show_user_details(bot, call, target_user_id)
    else:
        bot.answer_callback_query(call.id, result['error'], show_alert=True)