import os
import logging
from flask import Flask, request, jsonify
import hmac
import hashlib
import threading
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========== ROUTES ESSENZIALI ==========

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Weather Bot 🌤️</title></head>
    <body>
        <h1>Weather Bot is running!</h1>
        <p>Telegram weather bot is active.</p>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

# ⚠️ QUESTA È LA ROUTE PIÙ IMPORTANTE - DEVE ESISTERE!
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Handle Telegram webhook requests."""
    
    if request.method == 'GET':
        return "✅ Webhook endpoint is working! Telegram sends POST requests here.", 200
    
    # Verify secret token
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    
    if secret_token != Config.WEBHOOK_SECRET:
        logger.warning(f"Invalid webhook secret. Expected: {Config.WEBHOOK_SECRET}, Got: {secret_token}")
        return 'Unauthorized', 403
    
    logger.info("✅ Valid webhook request received")
    
    # Get update from Telegram
    update = request.get_json()
    
    # Process the update (you need to add your bot logic here)
    if 'message' in update:
        chat_id = update['message']['chat']['id']
        text = update['message'].get('text', '')
        
        logger.info(f"Message from {chat_id}: {text}")
        
        # Send a simple response (TEMPORARY - will be replaced by actual bot)
        import requests
        response_text = "🤖 Bot is working! Try /start or /weather Rome"
        
        if text == '/start':
            response_text = "Hello! I'm your weather bot! 🌤️ Use /weather Rome"
        elif text.startswith('/weather'):
            city = text.replace('/weather', '').strip()
            response_text = f"Weather for {city if city else 'your city'} will be available soon!"
        
        requests.post(
            f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': response_text
            }
        )
    
    return 'OK', 200

def verify_cron_request():
    """Verify cron job request using HMAC signature."""
    # ... (keep your existing cron verification code) ...

@app.route('/trigger-morning-reports', methods=['POST'])
def trigger_morning_reports():
    # ... (keep your existing cron endpoints) ...

@app.route('/trigger-rain-check', methods=['POST'])
def trigger_rain_check():
    # ... (keep your existing cron endpoints) ...

# ========== AVVIO SERVER ==========

if __name__ == '__main__':
    # Validate configuration
    try:
        Config.validate()
        logger.info("✅ Configuration validated successfully")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        exit(1)
    
    # Start Flask server
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)