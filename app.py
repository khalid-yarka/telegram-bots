# app.py
"""
Optimized Flask application for PythonAnywhere
- Authentication required for all pages
- Response caching
- Minimal database queries
- Gzip compression
"""

from flask import Flask, request, jsonify, render_template, abort, session, redirect, url_for
import logging
import os
import hashlib
import hmac
import time
from functools import wraps

# Database operations
from src.master_db.operations import get_bot_by_token, add_log_entry, get_all_bots, get_system_stats

# Config
from src.config import config

# Security utilities
from src.utils.security import validate_bot_token, verify_telegram_secret

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(config)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change-this-in-production')

# Simple cache for stats (prevents repeated DB queries)
_cache = {
    'stats': None,
    'stats_time': 0,
    'bots': None,
    'bots_time': 0
}
CACHE_TTL = 60  # seconds


# ==================== AUTHENTICATION DECORATOR ====================

def login_required(f):
    """Require authentication for web routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def api_key_required(f):
    """Require API key for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.environ.get('API_KEY', 'change-this-in-production')
        
        if not api_key or not hmac.compare_digest(api_key, expected_key):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ==================== CACHE HELPERS ====================

def get_cached_stats():
    """Get system stats from cache or database"""
    now = time.time()
    if _cache['stats'] and (now - _cache['stats_time']) < CACHE_TTL:
        return _cache['stats']
    
    # Cache miss - query database
    stats = get_system_stats()
    _cache['stats'] = stats
    _cache['stats_time'] = now
    return stats


def get_cached_bots():
    """Get all bots from cache or database"""
    now = time.time()
    if _cache['bots'] and (now - _cache['bots_time']) < CACHE_TTL:
        return _cache['bots']
    
    # Cache miss - query database
    bots = get_all_bots()
    _cache['bots'] = bots
    _cache['bots_time'] = now
    return bots


# ==================== AUTHENTICATION ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        # Simple password check - in production use proper auth
        if password == os.environ.get('ADMIN_PASSWORD', 'admin123'):
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid password")
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Log out"""
    session.pop('logged_in', None)
    return redirect(url_for('login'))


# ==================== WEBHOOK HANDLER (PUBLIC) ====================

@app.route('/webhook/<bot_token>', methods=['POST'])
def handle_webhook(bot_token):
    """
    Handle incoming Telegram webhook updates
    This endpoint is public (called by Telegram)
    """
    start_time = time.time()
    
    try:
        # 1. Validate token format (fast)
        if not validate_bot_token(bot_token):
            logger.warning(f"Invalid token format: {bot_token[:10]}...")
            abort(400)

        # 2. Verify Telegram secret header (optional but recommended)
        # verify_telegram_secret(app.config.get("TELEGRAM_WEBHOOK_SECRET"))

        # 3. Get JSON data
        json_data = request.get_json(force=True)
        if not json_data:
            logger.warning(f"No JSON data for token: {bot_token[:10]}...")
            return jsonify({'error': 'No data received'}), 400

        update_id = json_data.get('update_id', 'unknown')

        # 4. Fetch bot info (fast query)
        bot_info = get_bot_by_token(bot_token)
        if not bot_info:
            logger.warning(f"Bot not found: {bot_token[:10]}...")
            return jsonify({'error': 'Bot not found'}), 404

        if not bot_info.get('is_active'):
            logger.warning(f"Inactive bot attempt: {bot_token[:10]}...")
            return jsonify({'error': 'Bot inactive'}), 403

        # 5. Log the update (async - don't wait)
        try:
            add_log_entry(
                bot_token=bot_token,
                action_type='webhook_received',
                details=f"Update {update_id} received"
            )
        except:
            pass  # Don't fail if logging fails

        # 6. Dispatch update based on bot type (lazy import)
        bot_type = bot_info.get('bot_type', 'unknown')

        if bot_type == 'master':
            from bots.master_bot.bot import process_master_update
            process_master_update(bot_token, json_data)
        elif bot_type == 'ardayda':
            from bots.ardayda_bot.bot import process_ardayda_update
            process_ardayda_update(bot_token, json_data)
        elif bot_type == 'dhalinyaro':
            from bots.dhalinyaro_bot.bot import process_dhalinyaro_update
            process_dhalinyaro_update(bot_token, json_data)
        else:
            logger.error(f"Unknown bot type: {bot_type}")
            return jsonify({'error': 'Unknown bot type'}), 400

        # Log if slow
        elapsed = time.time() - start_time
        if elapsed > 1:
            logger.warning(f"Slow webhook ({elapsed:.2f}s): {bot_token[:10]}...")

        return jsonify({'status': 'success', 'update_id': update_id}), 200

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ==================== PROTECTED WEB PAGES ====================

@app.route('/')
@login_required
def index():
    """Dashboard homepage"""
    # Get cached stats
    stats = get_cached_stats()
    bots = get_cached_bots()
    
    return render_template(
        'index.html',
        title="Dashboard",
        stats=stats,
        bots=bots[:5],  # Only first 5 for dashboard
        total_bots=len(bots)
    )


@app.route('/bots')
@login_required
def bots_page():
    """Bot management page"""
    bots = get_cached_bots()
    return render_template(
        'bots.html',
        title="Bot Management",
        bots=bots
    )


@app.route('/logs')
@login_required
def logs_page():
    """System logs page"""
    from master_db.operations import get_recent_logs
    logs = get_recent_logs(limit=100)
    return render_template(
        'logs.html',
        title="System Logs",
        logs=logs
    )


# ==================== API ENDPOINTS (Protected) ====================

@app.route('/api/bots', methods=['GET'])
@api_key_required
def list_bots_api():
    """API to list all bots"""
    try:
        bots = get_cached_bots()

        # Hide full tokens for security
        safe_bots = []
        for bot in bots:
            safe_bot = {
                'bot_name': bot.get('bot_name'),
                'bot_type': bot.get('bot_type'),
                'is_active': bot.get('is_active'),
                'bot_token': f"{bot.get('bot_token', '')[:10]}...",
                'owner_id': bot.get('owner_id'),
                'created_at': str(bot.get('created_at')) if bot.get('created_at') else None
            }
            safe_bots.append(safe_bot)

        return jsonify({
            'success': True,
            'count': len(safe_bots),
            'bots': safe_bots
        })
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
@api_key_required
def stats_api():
    """API to get system stats"""
    try:
        stats = get_cached_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Stats API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Public health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'telegram-bots-platform',
        'timestamp': time.time()
    })


@app.route('/api/webhook/check/<bot_token>', methods=['POST'])
@api_key_required
def check_webhook_api(bot_token):
    """Check webhook status for a bot"""
    from utils.webhook_manager import check_webhook
    
    result = check_webhook(bot_token)
    return jsonify(result)


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('500.html'), 500


# ==================== STARTUP ====================

if __name__ == '__main__':
    # Local development only
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # For PythonAnywhere WSGI
    # Warm up cache on startup
    with app.app_context():
        try:
            get_cached_stats()
            get_cached_bots()
            logger.info("Cache warmed up on startup")
        except Exception as e:
            logger.error(f"Startup cache warmup failed: {e}")