# src/bots/ardayda_bot/search_flow.py
"""
Updated search flow with:
- Rate limiting (50 searches per 12 hours, admin bypass)
- SQLite state management
- Search history tracking
- Admin search override
- Better pagination
"""

from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.bots.ardayda_bot import database, buttons, text
from src.bots.ardayda_bot.helpers import safe_edit_message
from src.bots.ardayda_bot.state_manager import (
    get_state_manager,
    set_user_status,
    get_user_status,
    set_temp_data,
    get_temp_data,
    clear_temp_data
)
from src.bots.ardayda_bot.rate_limiter import can_search, increment_search
from src.bots.ardayda_bot.conflict_manager import save_message_id
import logging
import time

logger = logging.getLogger(__name__)

# Constants
RESULTS_PER_PAGE = 5
SEARCH_TIMEOUT = 1800  # 30 minutes
MAX_SEARCH_HISTORY = 20

# Status constants
STATUS_SEARCH_SUBJECT = "search:subject"
STATUS_SEARCH_TAGS = "search:tags"
STATUS_MENU_HOME = "menu:home"


def start(bot, message: Message):
    """Initialize search flow with rate limit check"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check rate limit (admins bypass)
    can_proceed, remaining, limit_msg = can_search(user_id)
    
    if not can_proceed:
        bot.send_message(
            chat_id,
            f"⏰ *Search Limit Reached*\n\n{limit_msg}\n\nAdmins have unlimited searches.",
            reply_markup=buttons.main_menu(user_id),
            parse_mode="Markdown"
        )
        logger.info(f"User {user_id} blocked by search rate limit")
        return
    
    # Clear any previous search data
    clear_temp_data(user_id, 'search')
    
    # Set status
    set_user_status(user_id, STATUS_SEARCH_SUBJECT)
    
    # Store rate limit info
    set_temp_data(user_id, 'search', 'remaining_searches', remaining, ttl=SEARCH_TIMEOUT)
    set_temp_data(user_id, 'search', 'start_time', time.time(), ttl=SEARCH_TIMEOUT)
    
    msg = bot.send_message(
        chat_id,
        f"🔍 *Search PDFs*\n\n"
        f"Select a subject to search.\n"
        f"*You have {remaining} searches remaining today*",
        reply_markup=buttons.search_subject_buttons(text.SUBJECTS),
        parse_mode="Markdown"
    )
    
    save_message_id(user_id, msg.message_id)
    logger.info(f"User {user_id} started search flow ({remaining} remaining)")


def handle_callback(bot, call: CallbackQuery):
    """Handle search flow callbacks"""
    user_id = call.from_user.id
    data = call.data
    status = get_user_status(user_id)

    logger.debug(f"Search callback - User: {user_id}, Data: {data}, Status: {status}")

    if not status or not status.startswith("search:"):
        bot.answer_callback_query(call.id, text.SESSION_EXPIRED)
        return

    # ----- SUBJECT SELECT -----
    if status == STATUS_SEARCH_SUBJECT and data.startswith("search_subject:"):
        subject = data.split(":", 1)[1]
        
        # Save subject to state manager
        set_temp_data(user_id, 'search', 'subject', subject, ttl=SEARCH_TIMEOUT)
        set_temp_data(user_id, 'search', 'tags', [], ttl=SEARCH_TIMEOUT)
        
        # Move to tags selection
        set_user_status(user_id, STATUS_SEARCH_TAGS)
        
        current_tags = []

        # Edit message to show tags
        try:
            bot.edit_message_text(
                "🏷️ *Select Tags*\n\n"
                f"Subject: *{subject}*\n\n"
                "You can select multiple tags or click 'Skip Tags':",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=buttons.search_tag_buttons(text.TAGS, current_tags),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not edit message: {e}")
            bot.send_message(
                call.message.chat.id,
                "🏷️ *Select Tags*\n\n"
                f"Subject: *{subject}*\n\n"
                "You can select multiple tags or click 'Skip Tags':",
                reply_markup=buttons.search_tag_buttons(text.TAGS, current_tags),
                parse_mode="Markdown"
            )
        
        logger.info(f"User {user_id} selected subject: {subject}")
        bot.answer_callback_query(call.id)
        return

    # ----- TAG TOGGLE -----
    if status == STATUS_SEARCH_TAGS and data.startswith("search_tag:"):
        tag = data.split(":", 1)[1]
        
        # Get current tags
        current_tags = get_temp_data(user_id, 'search', 'tags') or []
        
        # Toggle tag
        if tag in current_tags:
            current_tags.remove(tag)
            action = "removed"
        else:
            current_tags.append(tag)
            action = "added"
        
        # Update in state manager
        set_temp_data(user_id, 'search', 'tags', current_tags, ttl=SEARCH_TIMEOUT)

        # Update only the keyboard
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=buttons.search_tag_buttons(text.TAGS, current_tags)
            )
        except Exception as e:
            logger.warning(f"Could not edit keyboard: {e}")
        
        logger.debug(f"User {user_id} {action} tag: {tag}")
        bot.answer_callback_query(call.id)
        return

    # ----- FINAL SEARCH -----
    if data == "search_done":
        _execute_search(bot, call, user_id, with_tags=True)
        return

    # ----- SKIP TAGS -----
    if data == "search_skip":
        _execute_search(bot, call, user_id, with_tags=False)
        return

    # ----- PAGINATION -----
    if data.startswith("pdf_page:"):
        page = int(data.split(":", 1)[1])
        
        # Get search data from state
        subject = get_temp_data(user_id, 'search', 'subject')
        tags = get_temp_data(user_id, 'search', 'tags') or []
        results = get_temp_data(user_id, 'search', 'results')
        
        if not results:
            # Results not in cache - search again
            results = database.search_pdfs(subject, tags)
            set_temp_data(user_id, 'search', 'results', results, ttl=SEARCH_TIMEOUT)
        
        # Update page
        set_temp_data(user_id, 'search', 'page', page, ttl=SEARCH_TIMEOUT)
        
        _send_results(bot, call.message.chat.id, user_id, subject, tags, results, page, call.message.message_id)
        
        bot.answer_callback_query(call.id)
        return

    # ----- PDF SEND -----
    if data.startswith("pdf_send:"):
        try:
            pdf_id = int(data.split(":", 1)[1])
            pdf = database.get_pdf_by_id(pdf_id)

            if not pdf:
                bot.answer_callback_query(call.id, "❌ PDF not found.")
                return

            # Get tags for caption
            tags = database.get_pdf_tags(pdf_id)
            tags_text = f"\n🏷️ Tags: {', '.join(tags)}" if tags else ""
            
            # Track download
            database.increment_download_count(pdf_id)
            
            caption = (
                f"📄 *{pdf['name']}*\n"
                f"📚 Subject: {pdf['subject']}"
                f"{tags_text}"
            )
            
            bot.send_document(
                call.message.chat.id, 
                pdf['file_id'], 
                caption=caption,
                parse_mode="Markdown"
            )
            
            # Add to search history
            _add_to_search_history(user_id, pdf)
            
            logger.info(f"User {user_id} downloaded PDF ID: {pdf_id}")
            bot.answer_callback_query(call.id, "✅ PDF sent successfully!")
            
        except Exception as e:
            logger.error(f"Error sending PDF: {e}")
            bot.answer_callback_query(call.id, "❌ Error sending PDF")
        return

    # ----- CANCEL -----
    if data == "search_cancel":
        logger.info(f"User {user_id} cancelled search")
        clear_temp_data(user_id, 'search')
        set_user_status(user_id, STATUS_MENU_HOME)
        
        try:
            bot.edit_message_text(
                text.CANCELLED,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=buttons.main_menu(user_id),
                parse_mode="Markdown"
            )
        except:
            bot.send_message(
                call.message.chat.id,
                text.CANCELLED,
                reply_markup=buttons.main_menu(user_id),
                parse_mode="Markdown"
            )
        
        bot.answer_callback_query(call.id)
        return

    # ----- NOOP -----
    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # ----- STALE BUTTON -----
    logger.warning(f"Stale button clicked by user {user_id}: {data}")
    bot.answer_callback_query(call.id, "❌ This action is no longer available. Please start over.")


def _execute_search(bot, call, user_id, with_tags=True):
    """Execute the search and display results"""
    # Get data from state
    subject = get_temp_data(user_id, 'search', 'subject')
    tags = get_temp_data(user_id, 'search', 'tags') if with_tags else []
    remaining = get_temp_data(user_id, 'search', 'remaining_searches')
    
    if not subject:
        bot.answer_callback_query(call.id, "No subject selected. Please start over.")
        return
    
    logger.info(f"User {user_id} searching: subject={subject}, tags={tags}")
    
    # Show loading message
    try:
        bot.edit_message_text(
            "🔍 Searching for PDFs...",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    except:
        bot.send_message(
            call.message.chat.id,
            "🔍 Searching for PDFs..."
        )
    
    # Perform search
    results = database.search_pdfs(subject, tags)
    
    logger.info(f"Search found {len(results)} results for user {user_id}")
    
    # Store results in state
    set_temp_data(user_id, 'search', 'results', results, ttl=SEARCH_TIMEOUT)
    set_temp_data(user_id, 'search', 'page', 1, ttl=SEARCH_TIMEOUT)
    
    # Increment search count (only if not admin)
    from src.bots.ardayda_bot.rate_limiter import get_rate_limiter
    if not get_rate_limiter().is_admin(user_id):
        increment_search(user_id)
        remaining_msg = f"\n\n*You have {remaining - 1} searches remaining*"
    else:
        remaining_msg = "\n\n*Admin search - no limit*"
    
    # Send results
    _send_results(bot, call.message.chat.id, user_id, subject, tags, results, 1, call.message.message_id, remaining_msg)
    
    bot.answer_callback_query(call.id)


def _send_results(bot, chat_id, user_id, subject, tags, results, page, message_id=None, extra_msg=""):
    """Display search results with pagination"""
    
    if not results:
        clear_temp_data(user_id, 'search')
        set_user_status(user_id, STATUS_MENU_HOME)
        
        tags_text = f" with tags: {', '.join(tags)}" if tags else ""
        no_results_msg = (
            f"😕 *No PDFs Found*\n\n"
            f"No PDFs found for {subject}{tags_text}.\n\n"
            f"Try different tags or subject, or upload some PDFs!"
            f"{extra_msg}"
        )
        
        if message_id:
            try:
                bot.edit_message_text(
                    text=no_results_msg,
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=buttons.main_menu(user_id),
                    parse_mode="Markdown"
                )
            except:
                bot.send_message(
                    chat_id,
                    no_results_msg,
                    reply_markup=buttons.main_menu(user_id),
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                chat_id,
                no_results_msg,
                reply_markup=buttons.main_menu(user_id),
                parse_mode="Markdown"
            )
        return

    total_pages = (len(results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
    start = (page - 1) * RESULTS_PER_PAGE
    end = min(start + RESULTS_PER_PAGE, len(results))
    page_results = results[start:end]

    tags_text = f" with tags: {', '.join(tags)}" if tags else ""
    
    if page > total_pages:
        page = total_pages
    
    text_msg = (
        f"📚 *Search Results*\n\n"
        f"📖 Subject: *{subject}*\n"
        f"{tags_text}\n"
        f"📄 Found: *{len(results)}* PDFs\n"
        f"📑 Page *{page}* of *{total_pages}*\n"
        f"{extra_msg}\n\n"
        f"Choose a document to download:"
    )

    markup = InlineKeyboardMarkup(row_width=1)
    
    # Add PDF buttons
    for pdf in page_results:
        display_name = pdf['name']
        if len(display_name) > 40:
            display_name = display_name[:37] + "..."
        
        # Add download count indicator
        downloads = pdf.get('downloads', 0)
        download_indicator = f" [{downloads}⬇️]" if downloads > 0 else ""
            
        markup.add(
            InlineKeyboardButton(
                f"📄 {display_name}{download_indicator}",
                callback_data=f"pdf_send:{pdf['id']}"
            )
        )

    # Pagination row
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton("⬅️ Previous", callback_data=f"pdf_page:{page-1}")
        )
    
    pagination_buttons.append(
        InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")
    )
    
    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"pdf_page:{page+1}")
        )
    
    if pagination_buttons:
        markup.row(*pagination_buttons)
    
    # Action buttons
    markup.row(
        InlineKeyboardButton("🔍 New Search", callback_data="search_cancel"),
        InlineKeyboardButton("❌ Cancel", callback_data="search_cancel")
    )

    try:
        if message_id:
            bot.edit_message_text(
                text=text_msg,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                chat_id,
                text=text_msg,
                reply_markup=markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error sending results: {e}")
        if message_id:
            bot.send_message(
                chat_id,
                text=text_msg,
                reply_markup=markup,
                parse_mode="Markdown"
            )


def _add_to_search_history(user_id, pdf):
    """Add downloaded PDF to user's search history"""
    history = get_temp_data(user_id, 'history', 'downloads') or []
    
    # Add to front
    history.insert(0, {
        'pdf_id': pdf['id'],
        'name': pdf['name'],
        'time': time.time()
    })
    
    # Keep only last MAX_SEARCH_HISTORY
    history = history[:MAX_SEARCH_HISTORY]
    
    set_temp_data(user_id, 'history', 'downloads', history, ttl=86400)  # 24 hours


# ==================== ADMIN FUNCTIONS ====================

def get_search_stats(admin_id):
    """Get search statistics for admin panel"""
    from src.bots.ardayda_bot.admin_utils import is_admin
    
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    try:
        with database.get_db_connection() as conn:
            # Most downloaded PDFs
            cursor = conn.execute("""
                SELECT name, downloads, subject
                FROM pdfs
                ORDER BY downloads DESC
                LIMIT 10
            """)
            popular_pdfs = [dict(row) for row in cursor.fetchall()]
            
            # Total searches (estimated from rate limiter)
            from src.bots.ardayda_bot.rate_limiter import get_rate_limiter
            usage_stats = get_rate_limiter().get_usage_stats()
            total_searches = sum(1 for u in usage_stats if u['action_type'] == 'search')
            
            return {
                'success': True,
                'stats': {
                    'popular_pdfs': popular_pdfs,
                    'total_searches_today': total_searches,
                    'total_downloads': sum(p['downloads'] for p in popular_pdfs)
                }
            }
    except Exception as e:
        logger.error(f"Error getting search stats: {e}")
        return {'success': False, 'error': str(e)}


def admin_override_search_limit(admin_id, user_id):
    """Admin function to reset search limits for a user"""
    from src.bots.ardayda_bot.rate_limiter import get_rate_limiter
    from src.bots.ardayda_bot.admin_utils import is_admin
    
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    success = get_rate_limiter().reset_user_limits(user_id, 'search')
    
    if success:
        database.log_admin_action(
            admin_id,
            'reset_search_limits',
            'user',
            user_id
        )
        return {'success': True, 'message': f'Search limits reset for user {user_id}'}
    else:
        return {'success': False, 'error': 'Failed to reset limits'}


def get_user_search_history(admin_id, user_id):
    """Get search history for a specific user (admin only)"""
    from src.bots.ardayda_bot.admin_utils import is_admin
    
    if not is_admin(admin_id):
        return {'success': False, 'error': 'Admin access required'}
    
    history = get_temp_data(user_id, 'history', 'downloads') or []
    
    return {
        'success': True,
        'history': history,
        'count': len(history)
    }