# app.py
"""
Optimized Flask application for PythonAnywhere
- Authentication required for all pages
- Response caching
- Minimal database queries
- Gzip compression
"""

from flask import Flask, request, jsonify, render_template, abort, session, redirect, url_for, send_from_directory
import logging
import os
import hashlib
import hmac
import time
from functools import wraps
from datetime import timedelta

# Database operations
from src.master_db.operations import get_bot_by_token, add_log_entry, get_all_bots, get_system_stats, get_logs

# NEW: Import additional operations for bot management
from src.master_db.operations import (
    add_bot, delete_bot, toggle_bot_status, update_bot_name,
    update_webhook_status, get_webhook_status
)

# NEW: Import webhook manager
from src.utils.webhook_manager import set_webhook, delete_webhook, check_webhook

# NEW: Import permissions
from src.utils.permissions import is_super_admin

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

# ==================== SESSION CONFIGURATION ====================
# Critical for login to work properly
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'development-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# Simple cache for stats (prevents repeated DB queries)
_cache = {
    'stats': None,
    'stats_time': 0,
    'bots': None,
    'bots_time': 0
}
CACHE_TTL = 60  # seconds


# ==================== AUTHENTICATION DECORATORS ====================

def login_required(f):
    """Require authentication for web routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if not session.get('logged_in'):
            logger.debug(f"Access denied to {request.path} - not logged in")
            # Store the page they were trying to access
            session['next_url'] = request.url
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
            logger.warning(f"Invalid API key attempt from {request.remote_addr}")
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ==================== BEFORE REQUEST HANDLER ====================

@app.before_request
def before_request():
    """Handle session and authentication before each request"""
    # List of public endpoints that don't need authentication
    public_endpoints = [
        'login', 
        'static', 
        'health_check',
        'handle_webhook',
        'debug_session',
        'test_auth',
        'debug_db',
        'debug_data'  # Added for debugging
    ]
    
    # Allow public endpoints
    if request.endpoint in public_endpoints:
        return
    
    # Special handling for webhook endpoint (it's public)
    if request.endpoint == 'handle_webhook':
        return
    
    # For API routes, they are protected by api_key_required decorator
    if request.path.startswith('/api/'):
        return
    
    # For all other routes, check if user is logged in
    if not session.get('logged_in'):
        # Don't redirect API requests - they'll be handled by decorator
        if not request.path.startswith('/api/'):
            logger.debug(f"Redirecting to login from {request.path}")
            return redirect(url_for('login'))
    
    # Ensure session is refreshed
    session.modified = True


@app.after_request
def after_request(response):
    """Add headers to prevent caching of protected pages"""
    if not request.path.startswith('/static/') and not request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# ==================== CACHE HELPERS ====================

def get_cached_stats():
    """Get system stats from cache or database"""
    now = time.time()
    if _cache['stats'] and (now - _cache['stats_time']) < CACHE_TTL:
        return _cache['stats']
    
    # Cache miss - query database
    try:
        stats = get_system_stats()
        _cache['stats'] = stats
        _cache['stats_time'] = now
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {}


def get_cached_bots():
    """Get all bots from cache or database"""
    now = time.time()
    if _cache['bots'] and (now - _cache['bots_time']) < CACHE_TTL:
        return _cache['bots']
    
    # Cache miss - query database
    try:
        bots = get_all_bots()
        _cache['bots'] = bots
        _cache['bots_time'] = now
        return bots
    except Exception as e:
        logger.error(f"Error getting bots: {e}")
        return []


# ==================== AUTHENTICATION ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple login page"""
    # If already logged in, redirect to dashboard
    if session.get('logged_in'):
        logger.debug("User already logged in, redirecting to index")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        # Get admin password from environment or use default for development
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        logger.debug(f"Login attempt from {request.remote_addr}")
        
        if password == admin_password:
            # Set session
            session['logged_in'] = True
            session['login_time'] = time.time()
            session['ip_address'] = request.remote_addr
            session.permanent = False
            
            logger.info(f"Successful login from {request.remote_addr}")
            
            # Add log entry
            try:
                add_log_entry(
                    bot_token=None,
                    action_type='admin_login',
                    details=f"Admin logged in from {request.remote_addr}",
                    user_id=0,
                    level='info'
                )
            except:
                pass
            
            # Redirect to next URL if exists
            next_url = session.pop('next_url', None)
            if next_url:
                return redirect(next_url)
            return redirect(url_for('index'))
        else:
            logger.warning(f"Failed login attempt from {request.remote_addr}")
            return render_template('login.html', error="Invalid password")
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Log out"""
    logger.info(f"User logged out from {request.remote_addr}")
    
    # Add log entry
    try:
        add_log_entry(
            bot_token=None,
            action_type='admin_logout',
            details=f"Admin logged out from {request.remote_addr}",
            user_id=0,
            level='info'
        )
    except:
        pass
    
    session.clear()  # Clear all session data
    return redirect(url_for('login'))


# ==================== DEBUG ROUTES ====================

@app.route('/debug-session')
def debug_session():
    """Debug endpoint to check session (remove in production)"""
    return {
        'logged_in': session.get('logged_in', False),
        'login_time': session.get('login_time'),
        'ip_address': session.get('ip_address'),
        'session_keys': list(session.keys()),
        'cookie_secure': app.config.get('SESSION_COOKIE_SECURE'),
        'secret_key_set': app.secret_key is not None
    }


@app.route('/test-auth')
def test_auth():
    """Test if user is authenticated"""
    if session.get('logged_in'):
        return f"""
        <h1>You are logged in!</h1>
        <p>Session data: {dict(session)}</p>
        <a href="/">Go to Dashboard</a> | 
        <a href="/logout">Logout</a>
        """
    else:
        return f"""
        <h1>Not logged in</h1>
        <p>Session data: {dict(session)}</p>
        <a href="/login">Go to Login</a>
        """


@app.route('/debug-db')
def debug_db():
    """Check database connection and data"""
    try:
        # Check bots
        bots = get_all_bots()
        bot_count = len(bots)
        
        # Check logs
        logs = get_logs(limit=10)
        log_count = len(logs)
        
        # Get system stats
        stats = get_system_stats()
        
        return {
            'database_connected': True,
            'bot_count': bot_count,
            'sample_bots': bots[:3] if bots else [],
            'log_count': log_count,
            'sample_logs': logs[:3] if logs else [],
            'stats': stats
        }
    except Exception as e:
        return {
            'database_connected': False,
            'error': str(e),
            'error_type': type(e).__name__
        }


@app.route('/debug-data')
@login_required
def debug_data():
    """Debug endpoint to check database content (temporary)"""
    try:
        from src.master_db.operations import get_all_bots
        bots = get_all_bots(include_inactive=True)
        
        # Convert datetime objects to strings for JSON serialization
        serializable_bots = []
        for bot in bots:
            bot_dict = dict(bot)
            # Convert any non-serializable objects
            for key, value in bot_dict.items():
                if hasattr(value, 'isoformat'):  # Handle datetime
                    bot_dict[key] = value.isoformat()
            serializable_bots.append(bot_dict)
        
        return {
            'success': True,
            'count': len(serializable_bots),
            'bots': serializable_bots,
            'database_path': 'master.db'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }


# ==================== STATIC FILES ====================

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files with caching"""
    response = send_from_directory('static', filename)
    # Cache static files for 1 year
    response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response


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

        # 2. Get JSON data
        json_data = request.get_json(force=True)
        if not json_data:
            logger.warning(f"No JSON data for token: {bot_token[:10]}...")
            return jsonify({'error': 'No data received'}), 400

        update_id = json_data.get('update_id', 'unknown')

        # 3. Fetch bot info (fast query)
        bot_info = get_bot_by_token(bot_token)
        if not bot_info:
            logger.warning(f"Bot not found: {bot_token[:10]}...")
            return jsonify({'error': 'Bot not found'}), 404

        if not bot_info.get('is_active'):
            logger.warning(f"Inactive bot attempt: {bot_token[:10]}...")
            return jsonify({'error': 'Bot inactive'}), 403

        # 4. Log the update (async - don't wait)
        try:
            add_log_entry(
                bot_token=bot_token,
                action_type='webhook_received',
                details=f"Update {update_id} received",
                level='info'
            )
        except:
            pass  # Don't fail if logging fails

        # 5. Dispatch update based on bot type (lazy import)
        bot_type = bot_info.get('bot_type', 'unknown')

        if bot_type == 'master':
            from src.bots.master_bot.bot import process_master_update
            process_master_update(bot_token, json_data)
        elif bot_type == 'ardayda':
            from src.bots.ardayda_bot.bot import process_ardayda_update
            process_ardayda_update(bot_token, json_data)
        elif bot_type == 'dhalinyaro':
            from src.bots.dhalinyaro_bot.bot import process_dhalinyaro_update
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
    logger.debug(f"Dashboard accessed by {request.remote_addr}")
    
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
    logger.debug(f"Bots page accessed by {request.remote_addr}")
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
    logger.debug(f"Logs page accessed by {request.remote_addr}")
    return render_template(
        'logs.html',
        title="System Logs"
    )


# ==================== NEW: BOT MANAGEMENT API ENDPOINTS ====================

@app.route('/api/bots/add', methods=['POST'])
@login_required
@api_key_required
def add_bot_api():
    """API to add a new bot via website"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['bot_token', 'bot_name', 'bot_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        # Validate token format
        if not validate_bot_token(data['bot_token']):
            return jsonify({'success': False, 'error': 'Invalid bot token format'}), 400
        
        # Check if bot already exists
        existing = get_bot_by_token(data['bot_token'])
        if existing:
            return jsonify({'success': False, 'error': 'Bot token already registered'}), 400
        
        # Get owner_id (default to 0 for system)
        owner_id = 0  # System admin
        
        # Add bot to database
        success, message = add_bot(
            bot_token=data['bot_token'],
            bot_name=data['bot_name'],
            bot_type=data['bot_type'],
            owner_id=owner_id,
            bot_username=data.get('bot_username')
        )
        
        if success:
            # Auto-setup webhook
            webhook_success = set_webhook(data['bot_token'], data['bot_type'])
            
            # Log the action
            add_log_entry(
                bot_token=data['bot_token'],
                action_type='bot_added',
                details=f"Bot {data['bot_name']} added via web interface",
                user_id=owner_id,
                level='info'
            )
            
            # Clear cache to force refresh
            _cache['bots'] = None
            
            return jsonify({
                'success': True,
                'message': 'Bot added successfully',
                'webhook_setup': webhook_success,
                'bot': {
                    'bot_token': data['bot_token'],
                    'bot_name': data['bot_name'],
                    'bot_type': data['bot_type'],
                    'is_active': True
                }
            })
        else:
            return jsonify({'success': False, 'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error adding bot: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bots/<bot_token>/delete', methods=['POST'])
@login_required
@api_key_required
def delete_bot_api(bot_token):
    """API to delete a bot"""
    try:
        # Get bot info
        bot = get_bot_by_token(bot_token)
        if not bot:
            return jsonify({'success': False, 'error': 'Bot not found'}), 404
        
        # Delete webhook first
        delete_webhook(bot_token)
        
        # Delete from database
        success, message = delete_bot(bot_token, 0)  # 0 = system admin
        
        if success:
            # Log the action
            add_log_entry(
                bot_token=bot_token,
                action_type='bot_deleted',
                details=f"Bot {bot.get('bot_name')} deleted via web interface",
                user_id=0,
                level='warning'
            )
            
            # Clear cache
            _cache['bots'] = None
            
            return jsonify({'success': True, 'message': 'Bot deleted successfully'})
        else:
            return jsonify({'success': False, 'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error deleting bot: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bots/<bot_token>/toggle', methods=['POST'])
@login_required
@api_key_required
def toggle_bot_api(bot_token):
    """API to activate/deactivate a bot"""
    try:
        data = request.get_json()
        active = data.get('active', True)
        
        # Get bot info
        bot = get_bot_by_token(bot_token)
        if not bot:
            return jsonify({'success': False, 'error': 'Bot not found'}), 404
        
        success, message = toggle_bot_status(bot_token, 0, active)
        
        if success:
            status = "activated" if active else "deactivated"
            
            # Log the action
            add_log_entry(
                bot_token=bot_token,
                action_type=f'bot_{status}',
                details=f"Bot {bot.get('bot_name')} {status} via web interface",
                user_id=0,
                level='info'
            )
            
            # Clear cache
            _cache['bots'] = None
            
            return jsonify({
                'success': True, 
                'message': f'Bot {status} successfully',
                'is_active': active
            })
        else:
            return jsonify({'success': False, 'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error toggling bot: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bots/<bot_token>/webhook', methods=['GET', 'POST'])
@login_required
@api_key_required
def manage_webhook_api(bot_token):
    """API to check or setup webhook"""
    try:
        if request.method == 'GET':
            # Check webhook status
            result = check_webhook(bot_token)
            return jsonify(result)
        
        elif request.method == 'POST':
            # Setup webhook
            data = request.get_json() or {}
            bot_type = data.get('bot_type')
            
            if not bot_type:
                # Get from database
                bot = get_bot_by_token(bot_token)
                if not bot:
                    return jsonify({'success': False, 'error': 'Bot not found'}), 404
                bot_type = bot.get('bot_type')
            
            success = set_webhook(bot_token, bot_type)
            
            return jsonify({
                'success': success,
                'message': 'Webhook configured successfully' if success else 'Webhook setup failed'
            })
            
    except Exception as e:
        logger.error(f"Error managing webhook: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bots/<bot_token>/rename', methods=['POST'])
@login_required
@api_key_required
def rename_bot_api(bot_token):
    """API to rename a bot"""
    try:
        data = request.get_json()
        new_name = data.get('new_name')
        
        if not new_name or len(new_name) < 3 or len(new_name) > 100:
            return jsonify({'success': False, 'error': 'Name must be between 3-100 characters'}), 400
        
        # Get bot info
        bot = get_bot_by_token(bot_token)
        if not bot:
            return jsonify({'success': False, 'error': 'Bot not found'}), 404
        
        success, message = update_bot_name(bot_token, new_name, 0)
        
        if success:
            # Log the action
            add_log_entry(
                bot_token=bot_token,
                action_type='bot_renamed',
                details=f"Bot renamed from {bot.get('bot_name')} to {new_name}",
                user_id=0,
                level='info'
            )
            
            # Clear cache
            _cache['bots'] = None
            
            return jsonify({'success': True, 'message': 'Bot renamed successfully'})
        else:
            return jsonify({'success': False, 'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error renaming bot: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bulk/webhook-check', methods=['POST'])
@login_required
@api_key_required
def bulk_webhook_check():
    """Check webhooks for all bots"""
    try:
        bots = get_cached_bots()
        results = []
        
        for bot in bots[:10]:  # Limit to 10 to avoid rate limits
            if bot.get('is_active'):
                webhook_info = check_webhook(bot['bot_token'])
                results.append({
                    'bot_name': bot.get('bot_name'),
                    'bot_token': bot['bot_token'][:10] + '...',
                    'status': webhook_info.get('status', 'unknown'),
                    'url': webhook_info.get('url', 'Not set')
                })
        
        return jsonify({
            'success': True,
            'checked': len(results),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error in bulk webhook check: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== API ENDPOINTS (Protected) ====================

@app.route('/api/bots', methods=['GET'])
@api_key_required
def list_bots_api():
    """API to list all bots - Returns FULL tokens for internal use"""
    try:
        bots = get_cached_bots()

        # Return FULL bot data for internal API use
        # The API key requirement ensures only authorized requests get full tokens
        safe_bots = []
        for bot in bots:
            safe_bot = {
                'bot_name': bot.get('bot_name'),
                'bot_type': bot.get('bot_type'),
                'is_active': bot.get('is_active'),
                'bot_token': bot.get('bot_token'),  # Return FULL token since this is internal API
                'owner_id': bot.get('owner_id'),
                'created_at': str(bot.get('created_at')) if bot.get('created_at') else None,
                'bot_username': bot.get('bot_username'),
                'last_seen': str(bot.get('last_seen')) if bot.get('last_seen') else None
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


# ==================== LOGS API ENDPOINT ====================

@app.route('/api/logs', methods=['GET'])
@api_key_required
def get_logs_api():
    """API to get system logs"""
    try:
        # Get query parameters
        limit = request.args.get('limit', default=100, type=int)
        bot_token = request.args.get('bot_token', default=None)
        action_type = request.args.get('action_type', default=None)
        
        logs = get_logs(limit=limit, bot_token=bot_token, action_type=action_type)
        
        # Format logs for JSON response
        formatted_logs = []
        for log in logs:
            # Mask bot token for security in logs (since logs might be viewed by non-admins)
            bot_token_display = log.get('bot_token')
            if bot_token_display:
                bot_token_display = f"{bot_token_display[:10]}..." if len(bot_token_display) > 10 else bot_token_display
            
            formatted_logs.append({
                'id': log.get('id'),
                'timestamp': log.get('timestamp'),
                'bot_token': bot_token_display,  # Masked in logs for security
                'bot_name': log.get('bot_name'),
                'user_id': log.get('user_id'),
                'action_type': log.get('action_type'),
                'details': log.get('details'),
                'level': log.get('level', 'info')
            })
        
        return jsonify({
            'success': True,
            'count': len(formatted_logs),
            'logs': formatted_logs
        })
    except Exception as e:
        logger.error(f"Logs API error: {str(e)}")
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
    from src.utils.webhook_manager import check_webhook
    
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
    app.run(host='0.0.0.0', port=port, debug=True)
else:
    # For PythonAnywhere WSGI
    # Warm up cache on startup
    with app.app_context():
        try:
            get_cached_stats()
            get_cached_bots()
            logger.info("Cache warmed up on startup")
            logger.info(f"Session config: secure={app.config['SESSION_COOKIE_SECURE']}, httponly={app.config['SESSION_COOKIE_HTTPONLY']}")
        except Exception as e:
            logger.error(f"Startup cache warmup failed: {e}")