# bots/ardayda_bot/admin_handlers.py

from telebot.types import CallbackQuery, Message
from src.bots.ardayda_bot import database, buttons
# Import src.from admin_utils instead of admin for is_admin
from src.bots.ardayda_bot.admin_utils import is_admin
from src.bots.ardayda_bot.admin import (
    get_all_users,
    get_user_details,
    get_user_pdfs,
    suspend_user,
    unsuspend_user,
    make_admin,
    remove_admin,
    get_all_pdfs,
    get_pdf_details,
    delete_pdf,
    get_user_stats,
    get_pdf_stats,
    get_admin_logs,
    clear_admin_logs,
    log_admin_action,
    USERS_PER_PAGE,
    PDFS_PER_PAGE,
    LOGS_PER_PAGE
)
from src.bots.ardayda_bot.admin_buttons import (
    admin_panel_main,
    admin_users_list,
    admin_user_actions,
    admin_pdfs_list,
    admin_pdf_actions,
    admin_stats_menu,
    admin_logs_list,
    admin_confirm_action
)
from src.bots.ardayda_bot.helpers import safe_edit_message
import logging

logger = logging.getLogger(__name__)


# ==================== MAIN ADMIN PANEL ====================
def show_admin_panel(bot, message: Message):
    """Show main admin panel directly from a message (not callback)"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.send_message(
            message.chat.id,
            "⛔ Admin access required!",
            reply_markup=buttons.main_menu(user_id)
        )
        return
    
    # Send new message with admin panel
    bot.send_message(
        message.chat.id,
        "⚙️ *Admin Panel*\n\nWelcome to the Ardayda Bot Admin Panel. Select an option:",
        reply_markup=admin_panel_main(),
        parse_mode="Markdown"
    )
    
    log_admin_action(user_id, 'view_admin_panel', 'system', 0)


# ==================== USER MANAGEMENT ====================

def show_users_list(bot, call: CallbackQuery, page: int = 1):
    """Show paginated list of users"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    users, total_pages = get_all_users(page)
    
    if not users:
        safe_edit_message(
            bot,
            call.message.chat.id,
            call.message.message_id,
            "📭 No users found.",
            reply_markup=admin_panel_main(),
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return
    
    # Build message
    text = f"👥 *User Management* (Page {page}/{total_pages})\n\n"
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_users_list(users, page, total_pages),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def show_user_details(bot, call: CallbackQuery, target_user_id: int, page: int = 1):
    """Show detailed user information"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    user = get_user_details(target_user_id)
    
    if not user:
        bot.answer_callback_query(call.id, "❌ User not found!")
        return
    
    # Format user info
    name = user.get('name', 'Not set')
    region = user.get('region', 'Not set')
    school = user.get('school', 'Not set')
    user_class = user.get('class', 'Not set')
    status = user.get('status', 'Unknown')
    is_user_admin = "✅ Yes" if user.get('is_admin') else "❌ No"
    suspended = "🚫 Yes" if user.get('suspended') else "✅ No"
    created_at = user.get('created_at')
    join_date = created_at.strftime("%Y-%m-%d") if created_at else "Unknown"
    pdf_count = user.get('pdf_count', 0)
    
    text = (
        f"👤 *User Details*\n\n"
        f"🆔 *ID:* `{target_user_id}`\n"
        f"📝 *Name:* {name}\n"
        f"📍 *Region:* {region}\n"
        f"🏫 *School:* {school}\n"
        f"📚 *Class:* {user_class}\n"
        f"📊 *Status:* {status}\n"
        f"👑 *Admin:* {is_user_admin}\n"
        f"🚫 *Suspended:* {suspended}\n"
        f"📅 *Joined:* {join_date}\n"
        f"📄 *PDFs:* {pdf_count}\n"
    )
    
    username = name if name != 'Not set' else str(target_user_id)
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_user_actions(target_user_id, username, page, page),
        parse_mode="Markdown"
    )
    
    log_admin_action(admin_id, 'view_user', 'user', target_user_id)
    bot.answer_callback_query(call.id)


def show_user_pdfs(bot, call: CallbackQuery, target_user_id: int, page: int = 1):
    """Show PDFs uploaded by a specific user"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    pdfs, total_pages = get_user_pdfs(target_user_id, page)
    
    if not pdfs:
        bot.answer_callback_query(call.id, "📭 This user has no PDFs.")
        return
    
    # Get user name
    user = database.get_user(target_user_id)
    user_name = user.get('name', f'ID {target_user_id}') if user else f'ID {target_user_id}'
    
    text = f"📄 *PDFs uploaded by {user_name}* (Page {page}/{total_pages})\n\n"
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_pdfs_list(pdfs, page, total_pages),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def handle_warn_user(bot, call: CallbackQuery, target_user_id: int):
    """Warn a user"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    # Get user name
    user = database.get_user(target_user_id)
    user_name = user.get('name', f'ID {target_user_id}') if user else f'ID {target_user_id}'
    
    # Show confirmation
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        f"⚠️ *Warn User*\n\nAre you sure you want to warn {user_name}?",
        reply_markup=admin_confirm_action('warn', target_user_id),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def handle_suspend_user(bot, call: CallbackQuery, target_user_id: int):
    """Suspend a user"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    # Show confirmation
    user = database.get_user(target_user_id)
    user_name = user.get('name', f'ID {target_user_id}') if user else f'ID {target_user_id}'
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        f"🔨 *Suspend User*\n\nAre you sure you want to suspend {user_name}?\n\nSuspended users cannot use the bot.",
        reply_markup=admin_confirm_action('suspend', target_user_id),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def handle_unsuspend_user(bot, call: CallbackQuery, target_user_id: int):
    """Unsuspend a user"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    if unsuspend_user(admin_id, target_user_id):
        bot.answer_callback_query(call.id, "✅ User unsuspended successfully!")
        # Refresh user view
        show_user_details(bot, call, target_user_id)
    else:
        bot.answer_callback_query(call.id, "❌ Failed to unsuspend user!")


def handle_make_admin(bot, call: CallbackQuery, target_user_id: int):
    """Make a user admin"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    # Show confirmation
    user = database.get_user(target_user_id)
    user_name = user.get('name', f'ID {target_user_id}') if user else f'ID {target_user_id}'
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        f"👑 *Make Admin*\n\nAre you sure you want to make {user_name} an admin?\n\nThey will have full access to admin panel.",
        reply_markup=admin_confirm_action('makeadmin', target_user_id),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def handle_remove_admin(bot, call: CallbackQuery, target_user_id: int):
    """Remove admin privileges"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    # Don't allow removing your own admin status
    if admin_id == target_user_id:
        bot.answer_callback_query(call.id, "❌ You cannot remove your own admin status!")
        return
    
    # Show confirmation
    user = database.get_user(target_user_id)
    user_name = user.get('name', f'ID {target_user_id}') if user else f'ID {target_user_id}'
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        f"👤 *Remove Admin*\n\nAre you sure you want to remove admin privileges from {user_name}?",
        reply_markup=admin_confirm_action('removeadmin', target_user_id),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


# ==================== PDF MANAGEMENT ====================

def show_pdfs_list(bot, call: CallbackQuery, page: int = 1):
    """Show paginated list of all PDFs"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    pdfs, total_pages = get_all_pdfs(page)
    
    if not pdfs:
        safe_edit_message(
            bot,
            call.message.chat.id,
            call.message.message_id,
            "📭 No PDFs found.",
            reply_markup=admin_panel_main(),
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return
    
    text = f"📄 *PDF Management* (Page {page}/{total_pages})\n\n"
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_pdfs_list(pdfs, page, total_pages),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def show_pdf_details(bot, call: CallbackQuery, pdf_id: int, page: int = 1):
    """Show detailed PDF information"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    pdf = get_pdf_details(pdf_id)
    
    if not pdf:
        bot.answer_callback_query(call.id, "❌ PDF not found!")
        return
    
    # Format PDF info
    name = pdf.get('name', 'Unknown')
    subject = pdf.get('subject', 'Unknown')
    uploader_name = pdf.get('uploader_name', 'Unknown')
    uploader_id = pdf.get('uploader_id', 'Unknown')
    created_at = pdf.get('created_at')
    upload_date = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "Unknown"
    downloads = pdf.get('downloads', 0)
    tags = pdf.get('tags', [])
    tags_text = ', '.join(tags) if tags else 'No tags'
    
    text = (
        f"📄 *PDF Details*\n\n"
        f"🆔 *ID:* `{pdf_id}`\n"
        f"📄 *Name:* {name}\n"
        f"📚 *Subject:* {subject}\n"
        f"🏷️ *Tags:* {tags_text}\n"
        f"👤 *Uploader:* {uploader_name} (`{uploader_id}`)\n"
        f"📥 *Downloads:* {downloads}\n"
        f"📅 *Uploaded:* {upload_date}\n"
    )
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_pdf_actions(pdf_id, name, page, page),
        parse_mode="Markdown"
    )
    
    log_admin_action(admin_id, 'view_pdf', 'pdf', pdf_id)
    bot.answer_callback_query(call.id)


def handle_delete_pdf(bot, call: CallbackQuery, pdf_id: int):
    """Delete a PDF"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    # Get PDF name
    pdf = database.get_pdf_by_id(pdf_id)
    pdf_name = pdf.get('name', 'Unknown') if pdf else 'Unknown'
    
    # Show confirmation
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        f"🗑️ *Delete PDF*\n\nAre you sure you want to delete:\n\n📄 `{pdf_name}`\n\nThis action cannot be undone!",
        reply_markup=admin_confirm_action('delete_pdf', pdf_id),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def handle_pdf_user(bot, call: CallbackQuery, pdf_id: int):
    """Show uploader of a PDF"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    pdf = get_pdf_details(pdf_id)
    if pdf and pdf.get('uploader_id'):
        show_user_details(bot, call, pdf['uploader_id'])
    else:
        bot.answer_callback_query(call.id, "❌ Uploader not found!")


def handle_pdf_stats(bot, call: CallbackQuery, pdf_id: int):
    """Show statistics for a PDF"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    pdf = database.get_pdf_by_id(pdf_id)
    if not pdf:
        bot.answer_callback_query(call.id, "❌ PDF not found!")
        return
    
    text = (
        f"📊 *PDF Statistics*\n\n"
        f"📄 *Name:* {pdf.get('name', 'Unknown')}\n"
        f"📥 *Downloads:* {pdf.get('downloads', 0)}\n"
        f"📅 *Uploaded:* {pdf.get('created_at', 'Unknown')}\n"
    )
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_pdf_actions(pdf_id, pdf.get('name', ''), 1, 1),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


# ==================== STATISTICS ====================

def show_stats(bot, call: CallbackQuery):
    """Show statistics menu"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        "📊 *Statistics Menu*\n\nSelect a category to view statistics:",
        reply_markup=admin_stats_menu(),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def show_user_stats(bot, call: CallbackQuery):
    """Show user statistics"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    stats = get_user_stats()
    
    text = (
        f"👥 *User Statistics*\n\n"
        f"📊 *Total Users:* {stats.get('total_users', 0)}\n"
        f"📅 *Joined Today:* {stats.get('today_users', 0)}\n"
        f"📆 *Joined This Week:* {stats.get('week_users', 0)}\n"
        f"👑 *Admins:* {stats.get('admin_count', 0)}\n"
    )
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_stats_menu(),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


def show_pdf_stats(bot, call: CallbackQuery):
    """Show PDF statistics"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    stats = get_pdf_stats()
    
    text = (
        f"📄 *PDF Statistics*\n\n"
        f"📊 *Total PDFs:* {stats.get('total_pdfs', 0)}\n"
        f"📅 *Uploaded Today:* {stats.get('today_pdfs', 0)}\n"
        f"📥 *Total Downloads:* {stats.get('total_downloads', 0)}\n\n"
        f"📚 *Top Subjects:*\n"
    )
    
    for subject in stats.get('top_subjects', []):
        text += f"• {subject['subject']}: {subject['count']} PDFs ({subject['downloads']} downloads)\n"
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_stats_menu(),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


# ==================== ADMIN LOGS ====================

def show_logs(bot, call: CallbackQuery, page: int = 1):
    """Show admin logs"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    logs, total_pages = get_admin_logs(page)
    
    if not logs:
        safe_edit_message(
            bot,
            call.message.chat.id,
            call.message.message_id,
            "📝 No admin logs found.",
            reply_markup=admin_panel_main(),
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return
    
    text = f"📝 *Admin Action Logs* (Page {page}/{total_pages})\n\n"
    
    for log in logs[:5]:
        # Convert to Somalia time
        if log.get('created_at'):
            somalia_time = database.utc_to_somalia(log['created_at'])
            time_str = somalia_time.strftime("%Y-%m-%d %H:%M")
        else:
            time_str = "Unknown"
            
        text += f"• [{time_str}] Admin `{log['admin_id']}` {log['action']} {log['target_type']} `{log['target_id']}`\n"
    
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        text,
        reply_markup=admin_logs_list(logs, page, total_pages),
        parse_mode="Markdown"
    )


def handle_clear_logs(bot, call: CallbackQuery):
    """Clear all admin logs"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    # Show confirmation
    safe_edit_message(
        bot,
        call.message.chat.id,
        call.message.message_id,
        "🗑️ *Clear All Logs*\n\nAre you sure you want to delete all admin logs?\n\nThis action cannot be undone!",
        reply_markup=admin_confirm_action('clear_logs', 0),
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)


# ==================== CONFIRMATION HANDLERS ====================

def handle_confirmation(bot, call: CallbackQuery, action: str, target_id: int):
    """Handle confirmation of actions"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    success = False
    message = ""
    
    if action == 'suspend':
        success = suspend_user(admin_id, target_id)
        message = "✅ User suspended successfully!" if success else "❌ Failed to suspend user!"
        
    elif action == 'unsuspend':
        success = unsuspend_user(admin_id, target_id)
        message = "✅ User unsuspended successfully!" if success else "❌ Failed to unsuspend user!"
        
    elif action == 'makeadmin':
        success = make_admin(admin_id, target_id)
        message = "✅ User is now an admin!" if success else "❌ Failed to make user admin!"
        
    elif action == 'removeadmin':
        success = remove_admin(admin_id, target_id)
        message = "✅ Admin privileges removed!" if success else "❌ Failed to remove admin privileges!"
        
    elif action == 'delete_pdf':
        success = delete_pdf(admin_id, target_id)
        message = "✅ PDF deleted successfully!" if success else "❌ Failed to delete PDF!"
        
    elif action == 'clear_logs':
        success = clear_admin_logs(admin_id)
        message = "✅ All logs cleared!" if success else "❌ Failed to clear logs!"
    
    elif action == 'warn':
        log_admin_action(admin_id, 'warn_user', 'user', target_id)
        message = "⚠️ User has been warned!"
        success = True
    
    # Show result message
    bot.answer_callback_query(call.id, message)
    
    if success:
        # Go back to previous menu - but we need to use a new message
        if 'user' in action or action == 'warn':
            # Send new message instead of editing
            bot.send_message(
                call.message.chat.id,
                message,
                parse_mode="Markdown"
            )
            # Then show user details in a new message
            user = get_user_details(target_id)
            if user:
                username = user.get('name', str(target_id))
                text = f"👤 *User Details*\n\n🆔 ID: `{target_id}`\n📝 Name: {username}"
                bot.send_message(
                    call.message.chat.id,
                    text,
                    reply_markup=admin_user_actions(target_id, username),
                    parse_mode="Markdown"
                )
        elif 'pdf' in action:
            show_pdfs_list(bot, call, 1)  # This will send new message
        elif 'logs' in action:
            show_logs(bot, call, 1)


def handle_cancellation(bot, call: CallbackQuery, action: str, target_id: int):
    """Handle cancellation of actions"""
    admin_id = call.from_user.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "⛔ Admin access required!")
        return
    
    bot.answer_callback_query(call.id, "❌ Action cancelled")
    
    # Go back to previous menu
    if 'user' in action:
        show_user_details(bot, call, target_id)
    elif 'pdf' in action:
        show_pdfs_list(bot, call)
    elif 'logs' in action:
        show_logs(bot, call)
    else:
        show_admin_panel(bot, call)