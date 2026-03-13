import requests
import logging
from datetime import datetime
from src.config import config
from src.master_db.operations import update_webhook_status, get_webhook_status

logger = logging.getLogger(__name__)

def set_webhook(bot_token, bot_type):
    """
    Set webhook for a Telegram bot

    Args:
        bot_token: Telegram bot token
        bot_type: Type of bot (master, ardayda, dhalinyaro)

    Returns:
        bool: True if successful
    """
    try:
        webhook_url = f"{config.WEBHOOK_URL_BASE}/webhook/{bot_token}"

        # Telegram API URL
        api_url = f"{config.TELEGRAM_API_URL}{bot_token}/setWebhook"

        # Set webhook with max connections = 40
        payload = {
            'url': webhook_url,
            'max_connections': 40,
            'drop_pending_updates': True
        }

        response = requests.post(api_url, data=payload, timeout=10)
        result = response.json()

        if result.get('ok'):
            logger.info(f"Webhook set for {bot_type} bot: {webhook_url}")
            update_webhook_status(bot_token, 'active')
            return True
        else:
            error_msg = result.get('description', 'Unknown error')
            logger.error(f"Failed to set webhook for {bot_type}: {error_msg}")
            update_webhook_status(bot_token, 'failed', error_msg)
            return False

    except requests.exceptions.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        logger.error(f"Webhook request error for {bot_type}: {error_msg}")
        update_webhook_status(bot_token, 'failed', error_msg)
        return False
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Webhook error for {bot_type}: {error_msg}")
        update_webhook_status(bot_token, 'failed', error_msg)
        return False

def delete_webhook(bot_token):
    """Delete webhook for a bot"""
    try:
        api_url = f"{config.TELEGRAM_API_URL}{bot_token}/deleteWebhook"
        response = requests.post(api_url, timeout=10)
        result = response.json()

        if result.get('ok'):
            logger.info(f"Webhook deleted for bot {bot_token[:10]}...")
            update_webhook_status(bot_token, 'pending')
            return True
        else:
            logger.error(f"Failed to delete webhook: {result.get('description')}")
            return False

    except Exception as e:
        logger.error(f"Error deleting webhook: {str(e)}")
        return False

def check_webhook(bot_token):
    """
    Check if webhook is set and working

    Returns:
        dict: Webhook info or error
    """
    try:
        api_url = f"{config.TELEGRAM_API_URL}{bot_token}/getWebhookInfo"
        response = requests.get(api_url, timeout=5)
        result = response.json()

        if result.get('ok'):
            webhook_info = result.get('result', {})

            # Update status
            if webhook_info.get('url'):
                status = 'active'
                error = None
            else:
                status = 'pending'
                error = 'No webhook set'

            update_webhook_status(bot_token, status, error)

            return {
                'success': True,
                'status': status,
                'url': webhook_info.get('url'),
                'has_custom_certificate': webhook_info.get('has_custom_certificate', False),
                'pending_update_count': webhook_info.get('pending_update_count', 0),
                'last_error_date': webhook_info.get('last_error_date'),
                'last_error_message': webhook_info.get('last_error_message'),
                'max_connections': webhook_info.get('max_connections', 40)
            }
        else:
            error_msg = result.get('description', 'Unknown error')
            update_webhook_status(bot_token, 'failed', error_msg)
            return {
                'success': False,
                'error': error_msg
            }

    except requests.exceptions.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        update_webhook_status(bot_token, 'failed', error_msg)
        return {'success': False, 'error': error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        update_webhook_status(bot_token, 'failed', error_msg)
        return {'success': False, 'error': error_msg}

def setup_all_webhooks():
    """Setup webhooks for all active bots"""
    try:
        from src.master_db.operations import get_all_bots

        bots = get_all_bots()
        results = {
            'total': len(bots),
            'success': 0,
            'failed': 0,
            'details': []
        }

        for bot in bots:
            bot_token = bot['bot_token']
            bot_type = bot['bot_type']
            bot_name = bot['bot_name']

            success = set_webhook(bot_token, bot_type)

            if success:
                results['success'] += 1
                results['details'].append({
                    'bot': bot_name,
                    'type': bot_type,
                    'status': '✅ Success'
                })
            else:
                results['failed'] += 1
                results['details'].append({
                    'bot': bot_name,
                    'type': bot_type,
                    'status': '❌ Failed'
                })

        logger.info(f"Webhook setup complete: {results['success']}/{results['total']} successful")
        return results

    except Exception as e:
        logger.error(f"Error setting up webhooks: {str(e)}")
        return {'error': str(e)}

def get_webhook_summary():
    """Get summary of all webhook statuses"""
    try:
        from src.master_db.operations import get_all_bots

        bots = get_all_bots()
        summary = {
            'total': len(bots),
            'active': 0,
            'failed': 0,
            'pending': 0,
            'bots': []
        }

        for bot in bots:
            bot_token = bot['bot_token']
            status_info = get_webhook_status(bot_token)

            if status_info:
                status = status_info.get('status', 'pending')
                summary[status] = summary.get(status, 0) + 1

                summary['bots'].append({
                    'name': bot['bot_name'],
                    'type': bot['bot_type'],
                    'status': status,
                    'last_checked': status_info.get('last_checked'),
                    'last_error': status_info.get('last_error')
                })

        return summary

    except Exception as e:
        logger.error(f"Error getting webhook summary: {str(e)}")
        return {'error': str(e)}