import logging
import json
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import Config
from weather_service import get_complete_weather_report

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

USER_PREFS_FILE = 'user_preferences.json'

def load_user_prefs():
    if os.path.exists(USER_PREFS_FILE):
        with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_user_prefs(prefs):
    with open(USER_PREFS_FILE, 'w', encoding='utf-8') as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)

def get_user_language(user_id):
    prefs = load_user_prefs()
    return prefs.get(str(user_id), 'en')

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    
    welcome_msg = {
        'en': "Hello! I am your Weather Assistant. 🌤️\n\nSend me a city name or use /weather <city>\nUse /language to change language",
        'it': "Ciao! Sono il tuo Assistente Meteo. 🌤️\n\nInviami un nome di città o usa /meteo <città>\nUsa /lingua per cambiare lingua"
    }
    
    # Tastiera semplice solo per il cambio lingua
    keyboard = [["🌐 Language / Lingua"]]
    await update.message.reply_text(
        welcome_msg[lang],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode='Markdown'
    )
    
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang_keyboard = [["🇬🇧 English", "🇮🇹 Italiano"]]
    await update.message.reply_text(
        "Choose your language / Scegli la tua lingua:",
        reply_markup=ReplyKeyboardMarkup(lang_keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    text = update.message.text.strip()
    
    if text in ["🇬🇧 English", "🇮🇹 Italiano"]:
        await handle_language_choice(update, context)
        return
    
    if text in ["🌐 Language / Lingua", "/language", "/lingua"]:
        await language_command(update, context)
        return
    
    await process_weather_request(update, text, user_id, lang)

async def process_weather_request(update, city, user_id, lang):
    await update.message.reply_chat_action(action="typing")
    
    result = get_complete_weather_report(city, lang)
    
    if result['success']:
        await update.message.reply_text(result['message'], parse_mode='Markdown')
    else:
        error_msg = {
            'en': f"❌ I couldn't find weather data for '{city}'.\n\nPlease check the city name and try again.",
            'it': f"❌ Non riesco a trovare dati meteo per '{city}'.\n\nControlla il nome della città e riprova."
        }
        await update.message.reply_text(error_msg[lang])

def main():
    if not Config.BOT_TOKEN:
        logger.error("ERROR: BOT_TOKEN not found. Please check your .env file.")
        return
    
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("meteo", weather_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("lingua", language_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("aiuto", start_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    logger.info("🤖 Weather Bot starting in polling mode...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()