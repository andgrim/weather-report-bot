"""
Simple Flask server that runs Telegram bot with endpoints for cron jobs
"""

import os
import logging
from flask import Flask, request, jsonify
import subprocess
import sys
import threading
from send_morning_report import send_morning_reports
from check_rain_alerts import check_and_send_rain_alerts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Secret token for cron job (set in Render environment)
CRON_SECRET = os.environ.get('CRON_SECRET', 'your-secret-token-here')

def run_bot():
    """Start bot in a separate process."""
    try:
        logger.info("🔄 Starting Telegram bot...")
        # Run bot_core.py directly in a subprocess
        process = subprocess.Popen(
            [sys.executable, "bot_core.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Log bot output in background
        def log_output():
            while True:
                output = process.stdout.readline()
                if output:
                    logger.info(f"🤖 BOT: {output.strip()}")
                elif process.poll() is not None:
                    break
        
        threading.Thread(target=log_output, daemon=True).start()
        logger.info("✅ Bot process started successfully")
        return process
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        return None

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
    return "OK", 200

@app.route('/trigger-morning-reports')
def trigger_morning_reports():
    """Endpoint to trigger morning reports (called by cron job)."""
    secret = request.args.get('secret')
    
    if secret != CRON_SECRET:
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

@app.route('/trigger-rain-check')
def trigger_rain_check():
    """Endpoint to trigger rain alerts check (called by cron job)."""
    secret = request.args.get('secret')
    
    if secret != CRON_SECRET:
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

if __name__ == '__main__':
    # Start bot when server starts
    bot_process = run_bot()
    
    # Start Flask on Render's port
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)