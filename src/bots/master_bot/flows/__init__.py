from .add_bot_flow import register_add_bot_flow, start_add_bot_flow
from .edit_bot_flow import register_edit_bot_flow, start_edit_bot_name
from .delete_bot_flow import register_delete_bot_flow, confirm_delete_bot, execute_delete_bot

def register_flow_handlers(bot_instance):
    """Register all flow handlers"""
    register_add_bot_flow(bot_instance)
    register_edit_bot_flow(bot_instance)
    register_delete_bot_flow(bot_instance)