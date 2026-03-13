# src/bots/ardayda_bot/registration.py
"""
Updated registration flow using SQLite state management
- No more in-memory pagination (registration_pages)
- Persistent across webhooks
- Admin can view registration stats
"""

from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.bots.ardayda_bot import database, buttons, text
from src.bots.ardayda_bot.state_manager import (
    get_state_manager,
    set_user_status,
    get_user_status,
    set_user_page,
    get_user_page,
    update_user_flow_data,
    get_user_flow_data,
    clear_user_status
)
import logging

logger = logging.getLogger(__name__)

# Constants
SCHOOLS_PER_PAGE = 5

# Status constants (match database)
STATUS_REG_NAME = "reg:name"
STATUS_REG_REGION = "reg:region"
STATUS_REG_SCHOOL = "reg:school"
STATUS_REG_CLASS = "reg:class"
STATUS_MENU_HOME = "menu:home"


# ---------- CHECK IF REGISTERING ----------
def is_registering(user_id):
    """Check if user is in registration flow"""
    status = get_user_status(user_id)
    return status and status.startswith("reg:")


# ---------- START REGISTRATION ----------
def start(bot, user_id, chat_id):
    """Start registration for new user"""
    # Set status to registration: name
    set_user_status(user_id, STATUS_REG_NAME)
    
    # Initialize page to 0 in state manager
    set_user_page(user_id, 0)
    
    bot.send_message(
        chat_id,
        text.REG_NAME,
        parse_mode="Markdown"
    )
    
    logger.info(f"User {user_id} started registration")


# ---------- HANDLE TEXT MESSAGES ----------
def handle_message(bot, message: Message):
    """Handle text messages during registration flow"""
    user_id = message.from_user.id
    status = get_user_status(user_id)
    text_msg = message.text.strip()

    # ----- STEP 1: ENTER NAME -----
    if status == STATUS_REG_NAME:
        # Validate name (at least 3 characters, at least 2 words)
        words = text_msg.split()
        if len(words) < 2 or len(text_msg) < 4:
            bot.send_message(
                message.chat.id,
                "❌ Please enter your full name (first and last name):"
            )
            return
            
        # Save name to database
        database.set_user_name(user_id, text_msg)
        
        # Move to region selection
        set_user_status(user_id, STATUS_REG_REGION)
        
        # Ask for region
        _ask_region(bot, message.chat.id)
        return

    # ----- STEP 3: ENTER CLASS -----
    elif status == STATUS_REG_CLASS:
        # Validate class (F3 or F4, case insensitive)
        normalized = text_msg.upper().strip()
        if normalized not in ["F3", "F4"]:
            bot.send_message(
                message.chat.id,
                "❌ Please enter your class (F3 or F4):"
            )
            return
        
        # Save class
        database.set_user_class(user_id, normalized)
        
        # Finalize registration
        _finalize_registration(bot, message.chat.id, user_id)
        return

    # Should not happen
    else:
        bot.send_message(
            message.chat.id,
            "⚠️ Unexpected registration state. Please start over with /cancel"
        )


# ---------- ASK REGION (Inline Keyboard) ----------
def _ask_region(bot, chat_id):
    """Show region selection buttons"""
    kb = InlineKeyboardMarkup(row_width=2)
    
    for region in text.form_four_schools_by_region.keys():
        kb.add(
            InlineKeyboardButton(
                f"🏫 {region}", 
                callback_data=f"reg_region:{region}"
            )
        )
    
    bot.send_message(
        chat_id, 
        "📍 *Select your region:*",
        reply_markup=kb,
        parse_mode="Markdown"
    )


# ---------- ASK SCHOOL (with pagination) ----------
def _ask_school(bot, chat_id, user_id, region):
    """Show school selection with pagination (uses SQLite for page tracking)"""
    
    schools = text.form_four_schools_by_region[region]
    page = get_user_page(user_id)
    
    # Calculate pagination
    start = page * SCHOOLS_PER_PAGE
    end = min(start + SCHOOLS_PER_PAGE, len(schools))
    page_schools = schools[start:end]
    total_pages = (len(schools) + SCHOOLS_PER_PAGE - 1) // SCHOOLS_PER_PAGE
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Add school buttons for current page
    for school in page_schools:
        kb.add(
            InlineKeyboardButton(
                f"🏫 {school}", 
                callback_data=f"reg_school:{school}"
            )
        )
    
    # Pagination row
    pagination_buttons = []
    
    # Previous button
    if page > 0:
        pagination_buttons.append(
            InlineKeyboardButton("⬅️ Prev", callback_data="school_prev")
        )
    
    # Page indicator
    pagination_buttons.append(
        InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop")
    )
    
    # Next button
    if end < len(schools):
        pagination_buttons.append(
            InlineKeyboardButton("Next ➡️", callback_data="school_next")
        )
    
    if pagination_buttons:
        kb.row(*pagination_buttons)
    
    # Cancel button
    kb.row(InlineKeyboardButton("❌ Cancel Registration", callback_data="reg_cancel"))
    
    bot.send_message(
        chat_id,
        f"📍 *Region:* {region}\n\nSelect your school:",
        reply_markup=kb,
        parse_mode="Markdown"
    )


# ---------- HANDLE CALLBACKS ----------
def handle_callback(bot, call: CallbackQuery):
    """Handle registration callbacks"""
    user_id = call.from_user.id
    data = call.data
    status = get_user_status(user_id)

    if not status or not status.startswith("reg:"):
        bot.answer_callback_query(call.id, "Registration session expired")
        return

    # ----- REGION SELECTED -----
    if status == STATUS_REG_REGION and data.startswith("reg_region:"):
        region = data.split(":", 1)[1]
        
        # Save region to database
        database.set_user_region(user_id, region)
        
        # Move to school selection
        set_user_status(user_id, STATUS_REG_SCHOOL)
        
        # Reset page to 0
        set_user_page(user_id, 0)
        
        # Edit the message to remove buttons
        try:
            bot.edit_message_text(
                f"✅ Selected region: *{region}*",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
        except:
            pass
        
        # Ask for school (new message)
        _ask_school(bot, call.message.chat.id, user_id, region)
        
        bot.answer_callback_query(call.id)
        return

    # ----- SCHOOL SELECTED -----
    if status == STATUS_REG_SCHOOL and data.startswith("reg_school:"):
        school = data.split(":", 1)[1]
        
        # Save school to database
        database.set_user_school(user_id, school)
        
        # Move to class entry
        set_user_status(user_id, STATUS_REG_CLASS)
        
        # Edit the message to remove buttons
        try:
            bot.edit_message_text(
                f"✅ Selected school: *{school}*",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
        except:
            pass
        
        # Ask for class
        bot.send_message(
            call.message.chat.id,
            "📚 *Enter your class*\n\nPlease enter F3 or F4:",
            reply_markup=buttons.cancel_button(),
            parse_mode="Markdown"
        )
        
        bot.answer_callback_query(call.id)
        return

    # ----- SCHOOL PAGINATION -----
    if status == STATUS_REG_SCHOOL:
        user = database.get_user(user_id)
        region = user.get('region') if user else None
        
        if not region:
            bot.answer_callback_query(call.id, "Region not found. Please restart.")
            return
        
        schools = text.form_four_schools_by_region[region]
        current_page = get_user_page(user_id)
        total_pages = (len(schools) + SCHOOLS_PER_PAGE - 1) // SCHOOLS_PER_PAGE
        
        if data == "school_next":
            new_page = min(current_page + 1, total_pages - 1)
            set_user_page(user_id, new_page)
            
        elif data == "school_prev":
            new_page = max(0, current_page - 1)
            set_user_page(user_id, new_page)
        else:
            bot.answer_callback_query(call.id)
            return
        
        # Update the school list
        page = get_user_page(user_id)
        start = page * SCHOOLS_PER_PAGE
        end = min(start + SCHOOLS_PER_PAGE, len(schools))
        page_schools = schools[start:end]
        
        # Build new keyboard
        kb = InlineKeyboardMarkup(row_width=1)
        for school in page_schools:
            kb.add(InlineKeyboardButton(f"🏫 {school}", callback_data=f"reg_school:{school}"))
        
        # Pagination
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="school_prev"))
        
        pagination_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
        
        if end < len(schools):
            pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="school_next"))
        
        if pagination_buttons:
            kb.row(*pagination_buttons)
        
        kb.row(InlineKeyboardButton("❌ Cancel", callback_data="reg_cancel"))
        
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=kb
            )
        except Exception as e:
            logger.warning(f"Could not edit keyboard: {e}")
        
        bot.answer_callback_query(call.id)
        return

    # ----- CANCEL REGISTRATION -----
    if data == "reg_cancel":
        # Clear registration status
        clear_user_status(user_id)
        
        try:
            bot.edit_message_text(
                "❌ Registration cancelled.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
        except:
            pass
        
        bot.send_message(
            call.message.chat.id,
            text.CANCELLED,
            reply_markup=buttons.main_menu(user_id),
            parse_mode="Markdown"
        )
        
        bot.answer_callback_query(call.id, "Registration cancelled")
        return

    # ----- FALLBACK -----
    bot.answer_callback_query(call.id, "Invalid registration action")


# ---------- FINALIZE REGISTRATION ----------
def _finalize_registration(bot, chat_id, user_id):
    """Complete registration and show main menu"""
    
    # Set status to main menu
    clear_user_status(user_id)  # This removes registration status
    
    # Get user data for welcome message
    user = database.get_user(user_id)
    name = user.get("name", "User") if user else "User"
    
    bot.send_message(
        chat_id,
        f"✅ *Registration Complete!*\n\nWelcome, {name}! 🎉\n\nYou can now upload and search PDFs using the menu below.",
        reply_markup=buttons.main_menu(user_id),
        parse_mode="Markdown"
    )
    
    logger.info(f"User {user_id} completed registration")


# ---------- ADMIN FUNCTIONS ----------
def get_registration_stats(admin_id):
    """Get registration statistics for admin panel"""
    from src.bots.ardayda_bot.admin_utils import is_admin
    
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    try:
        stats = database.get_user_stats()
        
        # Get incomplete registrations
        with database.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE name IS NULL OR region IS NULL OR school IS NULL
            """)
            incomplete = cursor.fetchone()['count']
            
            # Users by region
            cursor = conn.execute("""
                SELECT region, COUNT(*) as count 
                FROM users 
                WHERE region IS NOT NULL 
                GROUP BY region
            """)
            by_region = {}
            for row in cursor.fetchall():
                by_region[row['region']] = row['count']
        
        return {
            'success': True,
            'stats': {
                'total_users': stats['total_users'],
                'today': stats['today_users'],
                'this_week': stats['week_users'],
                'incomplete': incomplete,
                'by_region': by_region
            }
        }
    except Exception as e:
        logger.error(f"Error getting registration stats: {e}")
        return {'success': False, 'error': str(e)}