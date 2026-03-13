# src/bots/ardayda_bot/upload_flow.py
"""
Updated upload flow with:
- Rate limiting (100/day, admin bypass)
- SQLite state management
- File size limits
- Duplicate prevention
- Admin override
"""

from telebot.types import Message, CallbackQuery
from src.bots.ardayda_bot import database, buttons, text
from src.bots.ardayda_bot.helpers import safe_edit_message
from src.bots.ardayda_bot.state_manager import (
    get_state_manager,
    set_user_status,
    get_user_status,
    get_user_flow_data,
    update_user_flow_data,
    set_temp_data,
    get_temp_data,
    clear_temp_data
)
from src.bots.ardayda_bot.rate_limiter import can_upload, increment_upload, get_rate_limiter
from src.bots.ardayda_bot.conflict_manager import save_message_id
import logging
import time

logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB (Telegram limit is 50MB)
ALLOWED_EXTENSIONS = ['.pdf']
UPLOAD_TIMEOUT = 300  # 5 minutes

# Status constants
STATUS_UPLOAD_WAIT_PDF = "upload:wait_pdf"
STATUS_UPLOAD_SUBJECT = "upload:subject"
STATUS_UPLOAD_TAGS = "upload:tags"
STATUS_MENU_HOME = "menu:home"


def start(bot, message: Message):
    """Initialize upload flow with rate limit check"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check rate limit (admins bypass)
    can_proceed, remaining, limit_msg = can_upload(user_id)
    
    if not can_proceed:
        bot.send_message(
            chat_id,
            f"⏰ *Upload Limit Reached*\n\n{limit_msg}\n\nAdmins have unlimited uploads.",
            reply_markup=buttons.main_menu(user_id),
            parse_mode="Markdown"
        )
        logger.info(f"User {user_id} blocked by upload rate limit")
        return
    
    # Clear any previous temp data
    clear_temp_data(user_id, 'upload')
    
    # Set status
    set_user_status(user_id, STATUS_UPLOAD_WAIT_PDF)
    
    # Store limit info in flow data
    set_temp_data(user_id, 'upload', 'remaining_uploads', remaining, ttl=UPLOAD_TIMEOUT)
    set_temp_data(user_id, 'upload', 'start_time', time.time(), ttl=UPLOAD_TIMEOUT)
    
    msg = bot.send_message(
        chat_id,
        f"📤 *Upload PDF*\n\n"
        f"Please send your PDF file.\n"
        f"Max size: 50MB\n"
        f"Format: PDF only\n\n"
        f"*You have {remaining} uploads remaining today*",
        reply_markup=buttons.cancel_button(),
        parse_mode="Markdown"
    )
    
    save_message_id(user_id, msg.message_id)
    logger.info(f"User {user_id} started upload flow ({remaining} remaining)")


def handle_pdf_upload(bot, message: Message):
    """Process received PDF document with validation"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    status = get_user_status(user_id)

    # Verify we're in the correct state
    if status != STATUS_UPLOAD_WAIT_PDF:
        bot.send_message(
            chat_id,
            "⚠️ Please start upload from the menu first.",
            reply_markup=buttons.main_menu(user_id)
        )
        return

    doc = message.document
    
    # ========== VALIDATION ==========
    
    # 1. Check if it's a PDF
    if not doc or not doc.mime_type or not doc.mime_type.lower().endswith('pdf'):
        bot.send_message(
            chat_id,
            "❌ *Invalid File*\n\nPlease send a valid PDF document.",
            reply_markup=buttons.cancel_button(),
            parse_mode="Markdown"
        )
        return
    
    # 2. Check file size (Telegram gives us file_size)
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        size_mb = doc.file_size / (1024 * 1024)
        bot.send_message(
            chat_id,
            f"❌ *File Too Large*\n\n"
            f"Your file: {size_mb:.1f}MB\n"
            f"Max allowed: 50MB\n\n"
            f"Please compress or choose a smaller file.",
            reply_markup=buttons.cancel_button(),
            parse_mode="Markdown"
        )
        return
    
    # 3. Check for file_unique_id (required for duplicate detection)
    if not doc.file_unique_id:
        logger.error(f"Document missing file_unique_id: {doc}")
        bot.send_message(
            chat_id,
            "❌ Invalid PDF file. Please try another file.",
            reply_markup=buttons.cancel_button(),
            parse_mode="Markdown"
        )
        return
    
    # 4. Check for duplicate
    if database.pdf_exists(doc.file_unique_id):
        bot.send_message(
            chat_id,
            "⚠️ *Duplicate PDF*\n\nThis PDF already exists in the system!",
            reply_markup=buttons.main_menu(user_id),
            parse_mode="Markdown"
        )
        set_user_status(user_id, STATUS_MENU_HOME)
        return
    
    # ========== STORE FILE DATA ==========
    
    # Get remaining uploads from temp data
    remaining = get_temp_data(user_id, 'upload', 'remaining_uploads') or 100
    
    # Store in state manager (persistent)
    set_temp_data(user_id, 'upload', 'file_id', doc.file_id, ttl=UPLOAD_TIMEOUT)
    set_temp_data(user_id, 'upload', 'file_unique_id', doc.file_unique_id, ttl=UPLOAD_TIMEOUT)
    set_temp_data(user_id, 'upload', 'name', doc.file_name or f"PDF_{int(time.time())}.pdf", ttl=UPLOAD_TIMEOUT)
    set_temp_data(user_id, 'upload', 'remaining_uploads', remaining, ttl=UPLOAD_TIMEOUT)
    
    logger.info(f"User {user_id} uploaded valid PDF: {doc.file_name}")
    
    # Move to subject selection
    set_user_status(user_id, STATUS_UPLOAD_SUBJECT)
    
    bot.send_message(
        chat_id,
        f"📝 *Select Subject*\n\n"
        f"File: `{doc.file_name}`\n"
        f"Size: {doc.file_size // 1024}KB\n\n"
        f"Choose the subject for this PDF:",
        reply_markup=buttons.subject_buttons(text.SUBJECTS),
        parse_mode="Markdown"
    )


def handle_callback(bot, call: CallbackQuery):
    """Handle upload flow callbacks"""
    user_id = call.from_user.id
    data = call.data
    status = get_user_status(user_id)

    logger.debug(f"Upload callback - User: {user_id}, Data: {data}, Status: {status}")

    if not status or not status.startswith("upload:"):
        bot.answer_callback_query(call.id, text.SESSION_EXPIRED)
        return

    # ----- SUBJECT SELECT -----
    if status == STATUS_UPLOAD_SUBJECT and data.startswith("upload_subject:"):
        subject = data.split(":", 1)[1]

        # Store subject in state manager
        set_temp_data(user_id, 'upload', 'subject', subject, ttl=UPLOAD_TIMEOUT)
        
        # Move to tags selection
        set_user_status(user_id, STATUS_UPLOAD_TAGS)

        # Get current tags from state
        current_tags = get_temp_data(user_id, 'upload', 'tags') or []
        
        safe_edit_message(
            bot,
            call.message.chat.id,
            call.message.message_id,
            f"🏷️ *Select Tags*\n\n"
            f"Subject: *{subject}*\n\n"
            f"You can select multiple tags.\n"
            f"Tap ⬆️ Upload PDF when done:",
            reply_markup=buttons.tag_buttons(text.TAGS, current_tags),
            parse_mode="Markdown"
        )
        
        logger.info(f"User {user_id} selected subject: {subject}")
        bot.answer_callback_query(call.id)
        return

    # ----- TAG TOGGLE -----
    if status == STATUS_UPLOAD_TAGS and data.startswith("upload_tag:"):
        tag = data.split(":", 1)[1]
        
        # Get current tags
        current_tags = get_temp_data(user_id, 'upload', 'tags') or []
        
        # Toggle tag
        if tag in current_tags:
            current_tags.remove(tag)
            action = "removed"
        else:
            current_tags.append(tag)
            action = "added"
        
        # Store updated tags
        set_temp_data(user_id, 'upload', 'tags', current_tags, ttl=UPLOAD_TIMEOUT)

        # Update only the keyboard
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=buttons.tag_buttons(text.TAGS, current_tags)
            )
        except Exception as e:
            logger.warning(f"Could not edit keyboard: {e}")
        
        logger.debug(f"User {user_id} {action} tag: {tag}")
        bot.answer_callback_query(call.id)
        return

    # ----- FINAL UPLOAD -----
    if data == "upload_done":
        logger.info(f"User {user_id} attempting final upload")
        
        # Get all data from state manager
        file_id = get_temp_data(user_id, 'upload', 'file_id')
        file_unique_id = get_temp_data(user_id, 'upload', 'file_unique_id')
        name = get_temp_data(user_id, 'upload', 'name')
        subject = get_temp_data(user_id, 'upload', 'subject')
        tags = get_temp_data(user_id, 'upload', 'tags') or []
        remaining = get_temp_data(user_id, 'upload', 'remaining_uploads')
        
        # Validate required fields
        if not file_id:
            bot.answer_callback_query(call.id, "❌ Missing PDF file. Please start over.")
            return
            
        if not subject:
            bot.answer_callback_query(call.id, "❌ Missing subject. Please select a subject.")
            return
        
        try:
            # Show processing message
            safe_edit_message(
                bot,
                call.message.chat.id,
                call.message.message_id,
                "⏳ Processing upload...",
                parse_mode="Markdown"
            )
            
            # Finalize upload
            success, message_text, pdf_id = _finalize_upload(
                bot, user_id, file_id, file_unique_id, name, subject, tags
            )
            
            if success:
                # Increment rate limit counter (only if not admin)
                if not get_rate_limiter().is_admin(user_id):
                    increment_upload(user_id)
                    remaining_msg = f"\n\n*You have {remaining - 1} uploads remaining today*"
                else:
                    remaining_msg = "\n\n*Admin upload - no limit*"
                
                # Success message
                final_text = (
                    f"✅ *Upload Successful!*\n\n"
                    f"📄 *Name:* {name}\n"
                    f"📚 *Subject:* {subject}\n"
                    f"🏷️ *Tags:* {', '.join(tags) if tags else 'None'}"
                    f"{remaining_msg}"
                )
                
                safe_edit_message(
                    bot,
                    call.message.chat.id,
                    call.message.message_id,
                    final_text,
                    reply_markup=buttons.main_menu(user_id),
                    parse_mode="Markdown"
                )
                
                logger.info(f"User {user_id} uploaded PDF ID: {pdf_id}")
            else:
                # Error message
                safe_edit_message(
                    bot,
                    call.message.chat.id,
                    call.message.message_id,
                    f"❌ *Upload Failed*\n\n{message_text}",
                    reply_markup=buttons.main_menu(user_id),
                    parse_mode="Markdown"
                )
            
        except Exception as e:
            logger.error(f"Upload error for user {user_id}: {str(e)}", exc_info=True)
            safe_edit_message(
                bot,
                call.message.chat.id,
                call.message.message_id,
                f"❌ *Upload Failed*\n\n{str(e)[:100]}",
                reply_markup=buttons.main_menu(user_id),
                parse_mode="Markdown"
            )
        
        finally:
            # Clear state
            set_user_status(user_id, STATUS_MENU_HOME)
            clear_temp_data(user_id, 'upload')
        
        bot.answer_callback_query(call.id)
        return

    # ----- CANCEL -----
    if data == "upload_cancel":
        logger.info(f"User {user_id} cancelled upload")
        clear_temp_data(user_id, 'upload')
        set_user_status(user_id, STATUS_MENU_HOME)
        
        safe_edit_message(
            bot,
            call.message.chat.id,
            call.message.message_id,
            text.CANCELLED,
            reply_markup=buttons.main_menu(user_id),
            parse_mode="Markdown"
        )
        
        bot.answer_callback_query(call.id)
        return


def _finalize_upload(bot, user_id, file_id, file_unique_id, name, subject, tags):
    """Complete the upload process (database insertion)"""
    try:
        # Insert PDF into database
        pdf_id = database.insert_pdf(
            file_id=file_id,
            file_unique_id=file_unique_id,
            name=name,
            subject=subject,
            uploader_id=user_id
        )

        if not pdf_id:
            return False, "Failed to insert PDF into database", None

        # Add tags if any
        if tags:
            database.add_pdf_tags_bulk(pdf_id, tags)
            logger.info(f"Added {len(tags)} tags to PDF {pdf_id}")

        return True, "Success", pdf_id
        
    except Exception as e:
        logger.error(f"Database error during finalize: {e}")
        return False, f"Database error: {str(e)[:50]}", None


# ==================== ADMIN FUNCTIONS ====================

def get_upload_stats(admin_id):
    """Get upload statistics for admin panel"""
    from src.bots.ardayda_bot.admin_utils import is_admin
    
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    try:
        with database.get_db_connection() as conn:
            # Total PDFs
            cursor = conn.execute("SELECT COUNT(*) as count FROM pdfs")
            total_pdfs = cursor.fetchone()['count']
            
            # Uploads today
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM pdfs 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_pdfs = cursor.fetchone()['count']
            
            # Total downloads
            cursor = conn.execute("SELECT SUM(downloads) as total FROM pdfs")
            total_downloads = cursor.fetchone()['total'] or 0
            
            # Top uploaders
            cursor = conn.execute("""
                SELECT u.name, u.user_id, COUNT(p.id) as count
                FROM users u
                JOIN pdfs p ON u.user_id = p.uploader_id
                GROUP BY u.user_id
                ORDER BY count DESC
                LIMIT 5
            """)
            top_uploaders = [dict(row) for row in cursor.fetchall()]
            
            # PDFs by subject
            cursor = conn.execute("""
                SELECT subject, COUNT(*) as count
                FROM pdfs
                GROUP BY subject
                ORDER BY count DESC
            """)
            by_subject = {}
            for row in cursor.fetchall():
                by_subject[row['subject']] = row['count']
            
            return {
                'success': True,
                'stats': {
                    'total_pdfs': total_pdfs,
                    'today': today_pdfs,
                    'total_downloads': total_downloads,
                    'top_uploaders': top_uploaders,
                    'by_subject': by_subject
                }
            }
    except Exception as e:
        logger.error(f"Error getting upload stats: {e}")
        return {'success': False, 'error': str(e)}


def admin_override_upload_limit(admin_id, user_id):
    """Admin function to reset/override upload limits"""
    from src.bots.ardayda_bot.rate_limiter import get_rate_limiter
    from src.bots.ardayda_bot.admin_utils import is_admin
    
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    success = get_rate_limiter().reset_user_limits(user_id, 'upload')
    
    if success:
        database.log_admin_action(
            admin_id,
            'reset_upload_limits',
            'user',
            user_id
        )
        return {'success': True, 'message': f'Upload limits reset for user {user_id}'}
    else:
        return {'success': False, 'error': 'Failed to reset limits'}