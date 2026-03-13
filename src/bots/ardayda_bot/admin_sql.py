# bots/ardayda_bot/admin_sql.py

from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from src.bots.ardayda_bot import database
from src.bots.ardayda_bot.admin import is_admin
import logging

logger = logging.getLogger(__name__)

# Super admin IDs (hardcoded for security)
SUPER_ADMINS = [2094426161]  # Add your super admin IDs here

def handle_sql_command(bot, message: Message):
    """Handle /sql command for direct MySQL queries"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Only super admins can execute SQL
    if user_id not in SUPER_ADMINS:
        bot.send_message(chat_id, "⛔ This command is restricted to super admins only!")
        return
    
    # Extract query
    command_text = message.text.strip()
    if not command_text.startswith('/sql '):
        return
    
    query = command_text[5:].strip()  # Remove '/sql '
    
    if not query:
        bot.send_message(chat_id, "❌ Please provide a SQL query.\nExample: `/sql SELECT * FROM users LIMIT 5`")
        return
    
    # Security: Block dangerous commands
    dangerous = ['DROP', 'TRUNCATE', 'ALTER', 'CREATE', 'DELETE']
    if any(cmd in query.upper() for cmd in dangerous):
        # Ask for confirmation for dangerous commands
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("⚠️ Yes, Execute", callback_data=f"sql_confirm:{query}"),
            InlineKeyboardButton("❌ Cancel", callback_data="sql_cancel")
        )
        bot.send_message(
            chat_id,
            f"⚠️ *DANGEROUS OPERATION*\n\nAre you sure you want to execute:\n`{query}`",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return
    
    # Execute safe query
    execute_and_send_result(bot, chat_id, query)

def execute_and_send_result(bot, chat_id, query, is_confirmed=False):
    """Execute SQL query and send results"""
    try:
        # Log the query
        logger.info(f"Admin SQL: {query}")
        
        # Execute query
        result = database.execute_sql_query(query)
        
        if result is None:
            # Not a SELECT query (INSERT, UPDATE, etc.)
            bot.send_message(
                chat_id,
                "✅ Query executed successfully (no results to display)"
            )
        else:
            # Format SELECT results
            if not result:
                bot.send_message(chat_id, "📭 Query returned no results.")
                return
            
            # Format as simple table
            if isinstance(result, list) and len(result) > 0:
                # Get column names
                columns = result[0].keys() if result else []
                
                # Build message
                msg = f"📊 *Results* ({len(result)} rows)\n\n"
                
                # Add header
                header = " | ".join(columns)
                msg += f"`{header}`\n"
                msg += "─" * 40 + "\n"
                
                # Add rows (limit to 10 rows to avoid message too long)
                for row in result[:10]:
                    values = [str(row.get(col, ''))[:20] for col in columns]  # Truncate long values
                    msg += " | ".join(values) + "\n"
                
                if len(result) > 10:
                    msg += f"\n... and {len(result) - 10} more rows"
                
                bot.send_message(chat_id, msg, parse_mode="Markdown")
    
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)}")