import os
import logging
import hmac
import hashlib
from flask import Flask, request, jsonify
import threading
from user_prefs import load_user_prefs, get_all_users_with_cities
from send_morning_report import send_morning_reports
from check_rain_alerts import check_and_send_rain_alerts
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def verify_cron_request():
    """Verify cron job request using HMAC signature."""
    if not Config.CRON_SECRET:
        logger.warning("CRON_SECRET not configured")
        return False
    
    signature = request.headers.get('X-Cron-Signature')
    if not signature:
        logger.warning("No signature provided")
        return False
    
    # Calculate expected signature
    expected_signature = hmac.new(
        Config.CRON_SECRET.encode(),
        request.data,
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected_signature)

@app.route('/')
def home():
    """Home page with bot status."""
    prefs = load_user_prefs()
    total_users = len(prefs.get('cities', {}))
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weather Report Bot 🌤️</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .status {{ color: green; font-weight: bold; }}
            .stats {{ margin: 20px 0; padding: 20px; background: #f5f5f5; border-radius: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌤️ Weather Report Bot</h1>
            <p class="status">✅ Service is running</p>
            
            <div class="stats">
                <h3>📊 Bot Statistics</h3>
                <p>Total users with saved cities: <strong>{total_users}</strong></p>
                <p>Mode: <strong>{'Webhook' if Config.WEBHOOK_MODE else 'Polling'}</strong></p>
            </div>
            
            <p>Use Telegram to interact with the bot.</p>
            <hr>
            <p><small>Powered by Open-Meteo API | Running on Render</small></p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Health check endpoint for Render."""
    return jsonify({
        'status': 'healthy',
        'service': 'telegram-weather-bot',
        'mode': 'webhook' if Config.WEBHOOK_MODE else 'polling'
    }), 200

@app.route('/trigger-morning-reports', methods=['POST'])
def trigger_morning_reports():
    """Endpoint to trigger morning reports (called by cron job)."""
    if not verify_cron_request():
        logger.warning("❌ Unauthorized cron attempt")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        logger.info("🌅 Cron job triggered - sending morning reports...")
        
        # Run in background thread
        thread = threading.Thread(target=send_morning_reports, daemon=True)
        thread.start()
        
        return jsonify({
            'status': 'started',
            'message': 'Morning reports are being sent in background'
        }), 200
    except Exception as e:
        logger.error(f"❌ Error triggering reports: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/trigger-rain-check', methods=['POST'])
def trigger_rain_check():
    """Endpoint to trigger rain alerts check (called by cron job)."""
    if not verify_cron_request():
        logger.warning("❌ Unauthorized cron attempt")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        logger.info("🌧️ Cron job triggered - checking rain alerts...")
        
        # Run in background thread
        thread = threading.Thread(target=check_and_send_rain_alerts, daemon=True)
        thread.start()
        
        return jsonify({
            'status': 'started',
            'message': 'Rain alerts check is running in background'
        }), 200
    except Exception as e:
        logger.error(f"❌ Error triggering rain check: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/stats')
def stats():
    """Get bot statistics (protected)."""
    if not verify_cron_request():
        return jsonify({'error': 'Unauthorized'}), 403
    
    prefs = load_user_prefs()
    
    return jsonify({
        'total_users': len(prefs.get('cities', {})),
        'users_with_rain_alerts': sum(1 for v in prefs.get('rain_alerts', {}).values() if v),
        'cities_saved': list(set(prefs.get('cities', {}).values()))
    })

if __name__ == '__main__':
    # Validate configuration
    try:
        Config.validate()
        logger.info("✅ Configuration validated successfully")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        exit(1)
    
    # Start Flask server
    logger.info(f"🚀 Starting Flask server on port {Config.PORT}")
    logger.info(f"🌐 Webhook mode: {Config.WEBHOOK_MODE}")
    
    app.run(
        host='0.0.0.0',
        port=Config.PORT,
        debug=False,
        use_reloader=False
    )