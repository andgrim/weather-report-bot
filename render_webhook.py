"""
Render-compatible webhook server for Telegram weather bot.
Combines Flask server for port binding with bot in background thread.
"""

import os
import logging
import threading
import time
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Telegram bot variables
bot_app = None
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot_started = False

# Import your existing functions
try:
    from bot_core import (
        load_user_prefs, save_user_prefs, get_user_language,
        start_command, language_command, handle_language_choice,
        weather_command, handle_text_message, process_weather_request
    )
    logger.info("Successfully imported bot_core functions")
except ImportError as e:
    logger.error(f"Failed to import bot_core: {e}")
    # Define dummy functions to prevent crashes
    async def start_command(*args, **kwargs): pass
    async def language_command(*args, **kwargs): pass
    async def handle_language_choice(*args, **kwargs): pass
    async def weather_command(*args, **kwargs): pass
    async def handle_text_message(*args, **kwargs): pass
    async def process_weather_request(*args, **kwargs): pass

def setup_bot_handlers(application):
    """Setup all bot command handlers."""
    try:
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("weather", weather_command))
        application.add_handler(CommandHandler("meteo", weather_command))
        application.add_handler(CommandHandler("language", language_command))
        application.add_handler(CommandHandler("lingua", language_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        logger.info("Bot handlers setup completed")
    except Exception as e:
        logger.error(f"Error setting up bot handlers: {e}")
    return application

def start_bot_in_thread():
    """Start the Telegram bot in a background thread."""
    global bot_app, bot_started
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    if bot_started:
        logger.info("Bot already started, skipping...")
        return
    
    try:
        logger.info(f"BOT_TOKEN length: {len(BOT_TOKEN) if BOT_TOKEN else 0}")
        
        # Create bot application
        bot_app = Application.builder().token(BOT_TOKEN).build()
        logger.info("Bot application created")
        
        # Setup handlers
        bot_app = setup_bot_handlers(bot_app)
        
        # Start polling in background
        logger.info("Starting Telegram bot in polling mode...")
        
        # Run in separate thread to not block Flask
        def run_polling():
            try:
                bot_app.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True,
                    close_loop=False
                )
            except Exception as e:
                logger.error(f"Error in bot polling: {e}")
        
        bot_thread = threading.Thread(target=run_polling, daemon=True)
        bot_thread.start()
        
        bot_started = True
        logger.info("Telegram bot started successfully in background thread")
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

# Start bot when module loads (for Render)
logger.info("Module loaded, starting bot initialization...")
start_bot_in_thread()

# Flask routes
@app.route('/')
def home():
    bot_status = "✅ Running" if bot_started else "⚠️ Starting..."
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weather Report Bot 🌤️</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .status {{ color: green; font-weight: bold; }}
            .warning {{ color: orange; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌤️ Weather Report Bot</h1>
            <p class="status">Status: {bot_status}</p>
            <p>This bot provides 5-day weather forecasts in English and Italian.</p>
            <p>Find it on Telegram and send any city name to get started.</p>
            <hr>
            <p><small>Powered by Open-Meteo API | Running on Render</small></p>
            <p><small>Bot token: {'Set' if BOT_TOKEN else 'NOT SET'}</small></p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Health check endpoint for Render monitoring."""
    status = "healthy" if bot_started else "starting"
    return {"status": status, "bot_started": bot_started, "service": "weather-bot"}, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Optional webhook endpoint for future use."""
    return {"status": "webhook-ready", "bot_started": bot_started}, 200

@app.route('/start-bot', methods=['POST'])
def manual_start():
    """Manually start the bot if needed."""
    start_bot_in_thread()
    return {"status": "bot_start_triggered", "bot_started": bot_started}, 200

if __name__ == '__main__':
    # Get port from environment (Render provides this)
    port = int(os.environ.get('PORT', 10000))
    
    logger.info(f"Starting Flask server on port {port}")
    logger.info(f"BOT_TOKEN is {'set' if BOT_TOKEN else 'NOT SET'}")
    
    # Start Flask app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )