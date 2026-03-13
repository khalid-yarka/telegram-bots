# src/bots/ardayda_bot/buttons.py

from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# Import from admin_utils instead of admin
from src.bots.ardayda_bot.admin_utils import is_admin

# ---------- MAIN MENU (HOME ONLY) ----------

def main_menu(user_id=None):
    """
    Main menu with upload, search, and profile options
    Shows Admin Panel button only if user is admin
    """
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    
    # First row: Upload and Search
    markup.row(
        KeyboardButton("📤 Upload"),
        KeyboardButton("🔍 Search")
    )
    
    # Second row: Profile
    markup.row(KeyboardButton("👤 Profile"))
    
    # Third row: Admin Panel (only for admins)
    if user_id and is_admin(user_id):
        markup.row(KeyboardButton("⚙️ Admin Panel"))
    
    return markup


# ---------- CANCEL (ONLY DURING OPERATIONS) ----------

def cancel_button():
    """Simple cancel button for ongoing operations"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(
        KeyboardButton("❌ Cancel")
    )
    return markup


# ---------- SUBJECT SELECTION (INLINE) ----------

def subject_buttons(subjects):
    """
    Show subjects as inline buttons for upload flow
    subjects: list[str]
    """
    markup = InlineKeyboardMarkup(row_width=2)

    buttons = [
        InlineKeyboardButton(
            text=f"📘 {subject}",
            callback_data=f"upload_subject:{subject}"
        )
        for subject in subjects
    ]

    markup.add(*buttons)
    return markup


# ---------- TAG SELECTION (MULTI-SELECT INLINE) ----------

def tag_buttons(tags, selected_tags):
    """
    Show tags with checkmarks for selected ones (upload flow)
    tags: list[str]
    selected_tags: list[str]
    """
    markup = InlineKeyboardMarkup(row_width=3)

    for tag in tags:
        is_selected = tag in selected_tags
        text = f"✅ {tag}" if is_selected else f"🏷️ {tag}"

        markup.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f"upload_tag:{tag}"
            )
        )

    # Add action buttons
    markup.row(
        InlineKeyboardButton("⬆️ Upload PDF", callback_data="upload_done"),
        InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")
    )

    return markup


# ---------- SEARCH SUBJECT BUTTONS ----------

def search_subject_buttons(subjects):
    """
    Show subjects for search flow
    subjects: list[str]
    """
    markup = InlineKeyboardMarkup(row_width=2)

    buttons = [
        InlineKeyboardButton(
            text=f"🔍 {subject}",
            callback_data=f"search_subject:{subject}"
        )
        for subject in subjects
    ]

    markup.add(*buttons)
    return markup


# ---------- SEARCH TAG SELECTION ----------

def search_tag_buttons(tags, selected_tags):
    """
    Show tags for search with selection indicators
    tags: list[str]
    selected_tags: list[str]
    """
    markup = InlineKeyboardMarkup(row_width=3)

    for tag in tags:
        is_selected = tag in selected_tags
        text = f"✅ {tag}" if is_selected else f"🏷️ {tag}"

        markup.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f"search_tag:{tag}"
            )
        )

    # Add action buttons
    markup.row(
        InlineKeyboardButton("🔍 Search", callback_data="search_done"),
        InlineKeyboardButton("⏭️ Skip Tags", callback_data="search_skip"),
        InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")
    )

    return markup


# ---------- SEARCH ACTION BUTTONS ----------

def search_action_buttons():
    """Action buttons for search results"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("🔍 New Search", callback_data="search_cancel"),
        InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")
    )
    return markup


# ---------- PAGINATION BUTTONS (FOR SEARCH RESULTS) ----------

def pagination_buttons(current_page, total_pages):
    """
    Create pagination controls for search results
    current_page: int
    total_pages: int
    """
    markup = InlineKeyboardMarkup(row_width=3)
    
    buttons = []
    
    # Previous button
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"pdf_page:{current_page-1}")
        )
    else:
        buttons.append(
            InlineKeyboardButton("⬅️", callback_data="noop")
        )
    
    # Page indicator
    buttons.append(
        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="noop")
    )
    
    # Next button
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton("➡️ Next", callback_data=f"pdf_page:{current_page+1}")
        )
    else:
        buttons.append(
            InlineKeyboardButton("➡️", callback_data="noop")
        )
    
    markup.row(*buttons)
    
    # Cancel button
    markup.row(
        InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")
    )
    
    return markup


# ---------- PDF RESULT BUTTONS (FOR SEARCH RESULTS) ----------

def pdf_result_buttons(pdfs, current_page, total_pages):
    """
    Create complete result page with PDF buttons and pagination
    pdfs: list of pdf dicts with 'id' and 'name'
    current_page: int
    total_pages: int
    """
    markup = InlineKeyboardMarkup(row_width=1)
    
    # Add PDF buttons
    for pdf in pdfs:
        # Truncate long names
        display_name = pdf['name']
        if len(display_name) > 40:
            display_name = display_name[:37] + "..."
            
        markup.add(
            InlineKeyboardButton(
                text=f"📄 {display_name}",
                callback_data=f"pdf_send:{pdf['id']}"
            )
        )
    
    # Add pagination
    pagination_buttons = []
    
    if current_page > 1:
        pagination_buttons.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"pdf_page:{current_page-1}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="noop")
    )
    
    if current_page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton("➡️ Next", callback_data=f"pdf_page:{current_page+1}")
        )
    
    if pagination_buttons:
        markup.row(*pagination_buttons)
    
    # Add cancel button
    markup.row(
        InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")
    )
    
    return markup


# ---------- NOOP BUTTON (PLACEHOLDER) ----------

def noop_button(text="⚫"):
    """
    Create a non-functional button for placeholders
    """
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(text, callback_data="noop")
    )
    return markup


# ---------- BACK BUTTON (COMMON) ----------

def back_button(callback_data="back"):
    """Simple back button"""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🔙 Back", callback_data=callback_data)
    )
    return markup


# ---------- YES/NO CONFIRMATION BUTTONS ----------

def yes_no_buttons(action, target_id):
    """
    Yes/No confirmation buttons
    action: the action to confirm (e.g., 'delete', 'suspend')
    target_id: the target ID
    """
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data=f"confirm_{action}:{target_id}"),
        InlineKeyboardButton("❌ No", callback_data=f"cancel_{action}:{target_id}")
    )
    return markup