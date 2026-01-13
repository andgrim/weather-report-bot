import os
import logging
import hmac
import hashlib
import threading
from flask import Flask, request, jsonify
import requests
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========== CRON SECURITY ==========

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
    
    # Use constant-time comparison
    return hmac.compare_digest(signature, expected_signature)

# ========== ROUTES ==========

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weather Report Bot 🌤️</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .container { max-width: 600px; margin: 0 auto; }
            .status { color: green; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌤️ Weather Report Bot</h1>
            <p class="status">✅ Service is running</p>
            <p>Telegram weather bot is active in background.</p>
            <p>Use Telegram to interact with the bot.</p>
            <hr>
            <p><small>Powered by Open-Meteo API | Running on Render</small></p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'telegram-weather-bot',
        'webhook_endpoint': '/webhook'
    }), 200

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Handle Telegram webhook requests."""
    
    if request.method == 'GET':
        return "✅ Webhook endpoint is working! Telegram sends POST requests with JSON updates.", 200
    
    # Verify secret token
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    
    if secret_token != Config.WEBHOOK_SECRET:
        logger.warning(f"❌ Invalid webhook secret. Expected: {Config.WEBHOOK_SECRET[:10]}..., Got: {secret_token[:10] if secret_token else 'None'}...")
        return 'Unauthorized', 403
    
    logger.info("✅ Valid webhook request received")
    
    try:
        # Get update from Telegram
        update = request.get_json()
        
        # Log the update type
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            text = update['message'].get('text', '')
            username = update['message']['chat'].get('username', 'Unknown')
            
            logger.info(f"📨 Message from @{username} ({chat_id}): {text}")
            
            # Send a simple response
            if text == '/start':
                response_text = (
                    "Hello! I'm your Weather Bot! 🌤️\n\n"
                    "Available commands:\n"
                    "/weather <city> - Get weather forecast\n"
                    "/rain <city> - Get rain forecast\n"
                    "/savecity <city> - Save your default city\n"
                    "/myweather - Weather for saved city\n"
                    "/help - Show all commands"
                )
            elif text == '/help':
                response_text = (
                    "🌤️ *Weather Bot Help*\n\n"
                    "*Basic Commands:*\n"
                    "• /weather Rome - Full forecast\n"
                    "• /rain Rome - Rain forecast\n"
                    "• /savecity Rome - Save city\n"
                    "• /myweather - Forecast for saved city\n"
                    "• /language - Change language\n\n"
                    "You can also just send a city name!"
                )
            elif text.startswith('/weather'):
                city = text.replace('/weather', '').strip()
                if city:
                    response_text = f"🌤️ Getting weather for {city}... (feature coming soon!)"
                else:
                    response_text = "Please specify a city: /weather Rome"
            elif text.startswith('/rain'):
                city = text.replace('/rain', '').strip()
                if city:
                    response_text = f"🌧️ Getting rain forecast for {city}... (feature coming soon!)"
                else:
                    response_text = "Please specify a city: /rain Rome"
            else:
                # Assume it's a city name
                if len(text) < 50 and text not in ['', ' ']:
                    response_text = f"🌤️ Getting weather for {text}... (feature coming soon!)"
                else:
                    response_text = "Send me a city name or use /help for commands"
            
            # Send response to Telegram
            try:
                requests.post(
                    f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
                    json={
                        'chat_id': chat_id,
                        'text': response_text,
                        'parse_mode': 'Markdown'
                    },
                    timeout=5
                )
                logger.info(f"✅ Response sent to {chat_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send Telegram response: {e}")
        
        elif 'callback_query' in update:
            logger.info(f"Callback query received")
        else:
            logger.info(f"Other update type: {list(update.keys())}")
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}")
        return 'Internal Server Error', 500

@app.route('/trigger-morning-reports', methods=['POST'])
def trigger_morning_reports():
    """Endpoint to trigger morning reports (called by cron job)."""
    if not verify_cron_request():
        logger.warning("❌ Unauthorized cron attempt for morning reports")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        logger.info("🌅 Cron job triggered - sending morning reports...")
        
        # Import here to avoid circular imports
        from send_morning_report import send_morning_reports
        
        # Run in background thread
        thread = threading.Thread(target=send_morning_reports, daemon=True)
        thread.start()
        
        return jsonify({
            'status': 'started',
            'message': 'Morning reports are being sent in background'
        }), 200
    except Exception as e:
        logger.error(f"❌ Error triggering morning reports: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/trigger-rain-check', methods=['POST'])
def trigger_rain_check():
    """Endpoint to trigger rain alerts check (called by cron job)."""
    if not verify_cron_request():
        logger.warning("❌ Unauthorized cron attempt for rain check")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        logger.info("🌧️ Cron job triggered - checking rain alerts...")
        
        # Import here to avoid circular imports
        from check_rain_alerts import check_and_send_rain_alerts
        
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

@app.route('/test-cron', methods=['GET'])
def test_cron():
    """Test endpoint to verify cron signature (for debugging)."""
    if not Config.CRON_SECRET:
        return jsonify({'error': 'CRON_SECRET not configured'}), 500
    
    # Calculate signature for empty data
    signature = hmac.new(
        Config.CRON_SECRET.encode(),
        b'',
        hashlib.sha256
    ).hexdigest()
    
    return jsonify({
        'signature_for_empty_data': signature,
        'instructions': 'Use this signature in header X-Cron-Signature'
    })

# ========== START SERVER ==========

if __name__ == '__main__':
    # Validate configuration
    try:
        Config.validate()
        logger.info("✅ Configuration validated successfully")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        exit(1)
    
    # Check if required modules exist
    try:
        from send_morning_report import send_morning_reports
        from check_rain_alerts import check_and_send_rain_alerts
        logger.info("✅ All required modules loaded successfully")
    except ImportError as e:
        logger.warning(f"⚠️ Some modules not available: {e}")
    
    # Start Flask server
    logger.info(f"🚀 Starting Flask server on port {Config.PORT}")
    logger.info(f"🌐 Webhook URL: {Config.RENDER_EXTERNAL_URL}/webhook")
    logger.info(f"🔐 Webhook secret configured: {'Yes' if Config.WEBHOOK_SECRET else 'No'}")
    logger.info(f"⏰ Cron secret configured: {'Yes' if Config.CRON_SECRET else 'No'}")
    
    app.run(
        host='0.0.0.0',
        port=Config.PORT,
        debug=False,
        use_reloader=False
    )