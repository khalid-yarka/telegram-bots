# bots/ardayda_bot/admin_buttons.py

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

def admin_panel_main():
    """Main admin panel menu"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        InlineKeyboardButton("👥 Manage Users", callback_data="admin_users:1"),
        InlineKeyboardButton("📄 Manage PDFs", callback_data="admin_pdfs:1"),
        InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
        InlineKeyboardButton("📝 View Logs", callback_data="admin_logs:1"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="admin_back")  # Changed from "🔙 Back to Menu"
    ]
    
    markup.add(*buttons)
    return markup


def admin_user_actions(user_id, username=None, current_page=1, total_pages=1):
    """Actions for a specific user"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    # User info button (no action)
    markup.add(InlineKeyboardButton(
        f"👤 User: {username or f'ID {user_id}'}", 
        callback_data="noop"
    ))
    
    # Action buttons
    buttons = [
        InlineKeyboardButton("📋 View PDFs", callback_data=f"admin_user_pdfs:{user_id}:1"),
        InlineKeyboardButton("⚠️ Warn User", callback_data=f"admin_warn:{user_id}"),
        InlineKeyboardButton("🔨 Suspend User", callback_data=f"admin_suspend:{user_id}"),
        InlineKeyboardButton("✅ Unsuspend", callback_data=f"admin_unsuspend:{user_id}"),
        InlineKeyboardButton("👑 Make Admin", callback_data=f"admin_makeadmin:{user_id}"),
        InlineKeyboardButton("👤 Remove Admin", callback_data=f"admin_removeadmin:{user_id}"),
    ]
    
    markup.add(*buttons)
    
    # Navigation buttons
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users:{current_page-1}"))
    
    nav_buttons.append(InlineKeyboardButton("📄 Back to List", callback_data=f"admin_users:{current_page}"))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    return markup


def admin_pdf_actions(pdf_id, pdf_name, current_page=1, total_pages=1):
    """Actions for a specific PDF"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    # PDF info
    display_name = pdf_name[:30] + "..." if len(pdf_name) > 30 else pdf_name
    markup.add(InlineKeyboardButton(
        f"📄 {display_name}", 
        callback_data="noop"
    ))
    
    # Action buttons
    buttons = [
        InlineKeyboardButton("👤 View Uploader", callback_data=f"admin_pdf_user:{pdf_id}"),
        InlineKeyboardButton("🗑️ Delete PDF", callback_data=f"admin_delete_pdf:{pdf_id}"),
        InlineKeyboardButton("📊 Stats", callback_data=f"admin_pdf_stats:{pdf_id}")
    ]
    
    markup.add(*buttons)
    
    # Navigation buttons
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_pdfs:{current_page-1}"))
    
    nav_buttons.append(InlineKeyboardButton("📄 Back to List", callback_data=f"admin_pdfs:{current_page}"))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    return markup


def admin_users_list(users, current_page, total_pages):
    """List of users with pagination"""
    markup = InlineKeyboardMarkup(row_width=1)
    
    # Add user buttons
    for user in users:
        name = user.get('name', 'Unknown')[:20]
        user_id = user['user_id']
        is_admin = "👑 " if user.get('is_admin') else ""
        status = "🚫" if user.get('suspended') else "✅"
        
        markup.add(InlineKeyboardButton(
            f"{status} {is_admin}{name} (ID: {user_id})",
            callback_data=f"admin_view_user:{user_id}:{current_page}"
        ))
    
    # Pagination
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_users:{current_page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="noop"))
    
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_users:{current_page+1}"))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    # Navigation buttons - both back to admin panel and main menu
    markup.row(
        InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="admin_back")
    )
    
    return markup


def admin_pdfs_list(pdfs, current_page, total_pages):
    """List of PDFs with pagination"""
    markup = InlineKeyboardMarkup(row_width=1)
    
    # Add PDF buttons
    for pdf in pdfs:
        name = pdf.get('name', 'Unknown')[:25] + "..." if len(pdf.get('name', '')) > 25 else pdf.get('name', 'Unknown')
        pdf_id = pdf['id']
        
        markup.add(InlineKeyboardButton(
            f"📄 {name} (ID: {pdf_id})",
            callback_data=f"admin_view_pdf:{pdf_id}:{current_page}"
        ))
    
    # Pagination
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_pdfs:{current_page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="noop"))
    
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_pdfs:{current_page+1}"))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    # Navigation buttons
    markup.row(
        InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="admin_back")
    )
    
    return markup


def admin_stats_menu():
    """Statistics menu options"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        InlineKeyboardButton("👥 Users Stats", callback_data="admin_stats_users"),
        InlineKeyboardButton("📄 PDFs Stats", callback_data="admin_stats_pdfs"),
        InlineKeyboardButton("📊 Subject Stats", callback_data="admin_stats_subjects"),
        InlineKeyboardButton("🏷️ Tag Stats", callback_data="admin_stats_tags"),
        InlineKeyboardButton("📈 Daily Activity", callback_data="admin_stats_daily"),
        InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
    ]
    
    markup.add(*buttons)
    return markup


def admin_logs_list(logs, current_page, total_pages):
    """List of admin logs with pagination"""
    markup = InlineKeyboardMarkup(row_width=1)
    
    # Add log entries (just as text, no buttons)
    for log in logs[:5]:  # Show only first 5 as preview
        time_str = log['created_at'].strftime("%H:%M") if hasattr(log['created_at'], 'strftime') else str(log['created_at'])[11:16]
        action = log['action'][:15]
        markup.add(InlineKeyboardButton(
            f"{time_str} | {action} | by {log['admin_id']}",
            callback_data="noop"
        ))
    
    # Pagination
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_logs:{current_page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="noop"))
    
    if current_page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_logs:{current_page+1}"))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    # Clear logs button (super admin only)
    markup.row(
        InlineKeyboardButton("🗑️ Clear Logs", callback_data="admin_clear_logs"),
        InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
    )
    
    return markup


def admin_confirm_action(action_type, target_id):
    """Confirmation buttons for destructive actions"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        InlineKeyboardButton("✅ Yes, Confirm", callback_data=f"admin_confirm_{action_type}:{target_id}"),
        InlineKeyboardButton("❌ No, Cancel", callback_data=f"admin_cancel_{action_type}:{target_id}")
    )
    
    return markup


def noop_button(text="⚫"):
    """Placeholder button"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text, callback_data="noop"))
    return markup