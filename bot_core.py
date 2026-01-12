import logging
import json
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import Config
from weather_service import get_complete_weather_report, get_detailed_rain_forecast

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# File to store user language preferences
USER_PREFS_FILE = 'user_preferences.json'

def load_user_prefs():
    """Load user language preferences from file."""
    if os.path.exists(USER_PREFS_FILE):
        with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_user_prefs(prefs):
    """Save user language preferences to file."""
    with open(USER_PREFS_FILE, 'w', encoding='utf-8') as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)

def get_user_language(user_id):
    """Get user's preferred language."""
    prefs = load_user_prefs()
    return prefs.get(str(user_id), 'en')  # Default to English

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show welcome message."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    
    welcome_msg = {
        'en': "Hello! I am your Weather Assistant 🌤️\n\n"
              "Send me a city name or use:\n"
              "/weather <city> - Full forecast\n"
              "/rain <city> - Detailed rain alerts\n"
              "/language - Change language",
        'it': "Ciao! Sono il tuo Assistente Meteo 🌤️\n\n"
              "Inviami un nome di città o usa:\n"
              "/meteo <città> - Previsioni complete\n"
              "/pioggia <città> - Avvisi pioggia dettagliati\n"
              "/lingua - Cambia lingua"
    }
    
    # Enhanced keyboard with rain alert option
    keyboard = [
        ["🌤️ Weather / Meteo"],
        ["🌧️ Rain Alert / Allerta Pioggia"],
        ["🌐 Language / Lingua"]
    ]
    
    await update.message.reply_text(
        welcome_msg[lang],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode='Markdown'
    )

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language or /lingua command - show language options."""
    lang_keyboard = [["🇬🇧 English", "🇮🇹 Italiano"]]
    await update.message.reply_text(
        "Choose your language / Scegli la tua lingua:",
        reply_markup=ReplyKeyboardMarkup(lang_keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's language choice."""
    user_id = update.effective_user.id
    choice = update.message.text
    prefs = load_user_prefs()
    
    if "Italiano" in choice:
        prefs[str(user_id)] = 'it'
        msg = "✅ Language set to Italian! / Lingua impostata su Italiano!"
    else:
        prefs[str(user_id)] = 'en'
        msg = "✅ Language set to English! / Lingua impostata su Inglese!"
    
    save_user_prefs(prefs)
    await update.message.reply_text(msg)

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /weather or /meteo command - get weather for city."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    
    if not context.args:
        no_city = {
            'en': "Please specify a city. Example: /weather Rome",
            'it': "Specifica una città. Esempio: /meteo Roma"
        }
        await update.message.reply_text(no_city[lang])
        return
    
    city = ' '.join(context.args)
    await process_weather_request(update, city, user_id, lang)

async def rain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rain or /pioggia command - get detailed rain forecast."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    
    if not context.args:
        no_city = {
            'en': "Please specify a city. Example: /rain Rome",
            'it': "Specifica una città. Esempio: /pioggia Roma"
        }
        await update.message.reply_text(no_city[lang])
        return
    
    city = ' '.join(context.args)
    await process_rain_request(update, city, user_id, lang)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    text = update.message.text.strip()
    
    # Handle language choice
    if text in ["🇬🇧 English", "🇮🇹 Italiano"]:
        await handle_language_choice(update, context)
        return
    
    # Handle weather button
    if text in ["🌤️ Weather / Meteo"]:
        prompt = {
            'en': "Send me a city name for the full weather forecast.",
            'it': "Inviami il nome di una città per le previsioni complete."
        }
        await update.message.reply_text(prompt[lang])
        return
    
    # Handle rain alert button
    if text in ["🌧️ Rain Alert / Allerta Pioggia"]:
        prompt = {
            'en': "Send me a city name for detailed rain alerts.",
            'it': "Inviami il nome di una città per avvisi pioggia dettagliati."
        }
        await update.message.reply_text(prompt[lang])
        return
    
    # Handle language change button
    if text in ["🌐 Language / Lingua", "/language", "/lingua"]:
        await language_command(update, context)
        return
    
    # Assume it's a city name - default to full weather report
    await process_weather_request(update, text, user_id, lang)

async def process_weather_request(update, city, user_id, lang):
    """Process weather request and send response."""
    await update.message.reply_chat_action(action="typing")
    
    result = get_complete_weather_report(city, lang)
    
    if result['success']:
        await update.message.reply_text(result['message'], parse_mode='Markdown')
        
        # Offer detailed rain report
        offer_rain = {
            'en': f"🌧️ For detailed rain forecast for {city}, use /rain {city}",
            'it': f"🌧️ Per previsioni pioggia dettagliate per {city}, usa /pioggia {city}"
        }
        await update.message.reply_text(offer_rain[lang])
    else:
        error_msg = {
            'en': f"❌ I couldn't find weather data for '{city}'.\n\n"
                  "Please check the city name and try again.",
            'it': f"❌ Non riesco a trovare dati meteo per '{city}'.\n\n"
                  "Controlla il nome della città e riprova."
        }
        await update.message.reply_text(error_msg[lang])

async def process_rain_request(update, city, user_id, lang):
    """Process rain forecast request and send detailed response."""
    await update.message.reply_chat_action(action="typing")
    
    result = get_detailed_rain_forecast(city, lang)
    
    if result['success']:
        await update.message.reply_text(result['message'], parse_mode='Markdown')
    else:
        error_msg = {
            'en': f"❌ I couldn't find rain data for '{city}'.\n\n"
                  "Please check the city name and try again.",
            'it': f"❌ Non riesco a trovare dati pioggia per '{city}'.\n\n"
                  "Controlla il nome della città e riprova."
        }
        await update.message.reply_text(error_msg[lang])

def main():
    """Start the bot in webhook mode (Render) or polling mode (local)."""
    if not Config.BOT_TOKEN:
        logger.error("ERROR: BOT_TOKEN not found. Please check your .env file.")
        return
    
    # Create application
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("aiuto", start_command))
    
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("meteo", weather_command))
    
    app.add_handler(CommandHandler("rain", rain_command))
    app.add_handler(CommandHandler("pioggia", rain_command))
    
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("lingua", language_command))
    
    # Add message handler for city names
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # DECIDE: Webhook for Render or Polling for local
    if Config.WEBHOOK_MODE and Config.RENDER_EXTERNAL_URL:
        # ✅ WEBHOOK MODE (for Render)
        logger.info("Starting bot in WEBHOOK mode for Render...")
        
        # Build webhook URL
        webhook_url = f"{Config.RENDER_EXTERNAL_URL}/webhook"
        logger.info(f"Webhook URL: {webhook_url}")
        
        # Start webhook
        app.run_webhook(
            listen="0.0.0.0",
            port=Config.PORT,
            url_path=Config.BOT_TOKEN,
            webhook_url=webhook_url,
            secret_token='WEBHOOK_SECRET'
        )
    else:
        # ✅ POLLING MODE (for local development)
        logger.info("Starting bot in POLLING mode (local development)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

def run_bot():
    """Function to run the bot."""
    if not Config.BOT_TOKEN:
        print("ERROR: BOT_TOKEN not found in .env")
        return
    
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add all handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("meteo", weather_command))
    app.add_handler(CommandHandler("rain", rain_command))
    app.add_handler(CommandHandler("pioggia", rain_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("lingua", language_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    print("🤖 Bot starting in polling mode...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    run_bot()