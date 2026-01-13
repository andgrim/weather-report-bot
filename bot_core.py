import logging
import json
import os
import atexit
from threading import Lock
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

# Lock per prevenire race condition
PREFS_LOCK = Lock()

def load_user_prefs():
    """Load user language preferences from file."""
    with PREFS_LOCK:
        if os.path.exists(USER_PREFS_FILE):
            try:
                with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.error(f"Error loading preferences from {USER_PREFS_FILE}")
                return {}
        return {}

def save_user_prefs(prefs):
    """Save user language preferences to file."""
    with PREFS_LOCK:
        try:
            # Crea directory se non esiste
            os.makedirs(os.path.dirname(USER_PREFS_FILE), exist_ok=True)
            
            # Salva in file temporaneo prima di rinominare (atomic operation)
            temp_file = USER_PREFS_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
            
            # Rinomina atomico
            if os.name == 'nt':  # Windows
                os.replace(temp_file, USER_PREFS_FILE)
            else:  # Unix/Linux
                os.rename(temp_file, USER_PREFS_FILE)
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")

def get_user_language(user_id):
    """Get user's preferred language."""
    prefs = load_user_prefs()
    return prefs.get(str(user_id), 'en')  # Default to English

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show welcome message."""
    try:
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        welcome_msg = {
            'en': "Hello! I am your Weather Assistant 🌤️\n\n"
                  "Send me a city name or use:\n"
                  "/weather <city> - Full forecast\n"
                  "/rain <city> - Detailed rain alerts\n"
                  "/savecity <city> - Save your city\n"
                  "/myweather - Forecast for saved city\n"
                  "/rainalerts - Toggle rain notifications\n"
                  "/language - Change language",
            'it': "Ciao! Sono il tuo Assistente Meteo 🌤️\n\n"
                  "Inviami un nome di città o usa:\n"
                  "/meteo <città> - Previsioni complete\n"
                  "/pioggia <città> - Avvisi pioggia\n"
                  "/salvacitta <città> - Salva la tua città\n"
                  "/miometeo - Previsioni per città salvata\n"
                  "/avvisipioggia - Attiva notifiche pioggia\n"
                  "/lingua - Cambia lingua"
        }
        
        # Keyboard con comandi principali
        keyboard = [
            ["🌤️ Weather / Meteo"],
            ["📍 My City / Mia Città"],
            ["🌧️ Rain Alert / Allerta Pioggia"],
            ["💾 Save City / Salva Città"],
            ["🔔 Rain Notif / Notif Pioggia"],
            ["🌐 Language / Lingua"]
        ]
        
        await update.message.reply_text(
            welcome_msg[lang],
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language or /lingua command - show language options."""
    try:
        lang_keyboard = [["🇬🇧 English", "🇮🇹 Italiano"]]
        await update.message.reply_text(
            "Choose your language / Scegli la tua lingua:",
            reply_markup=ReplyKeyboardMarkup(lang_keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
    except Exception as e:
        logger.error(f"Error in language_command: {e}")

async def handle_language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's language choice."""
    try:
        user_id = update.effective_user.id
        choice = update.message.text
        prefs = load_user_prefs()
        
        if "Italiano" in choice:
            prefs[str(user_id)] = 'it'
            msg = "✅ Lingua impostata su Italiano! / Language set to Italian!"
        else:
            prefs[str(user_id)] = 'en'
            msg = "✅ Language set to English! / Lingua impostata su Inglese!"
        
        save_user_prefs(prefs)
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in handle_language_choice: {e}")
        await update.message.reply_text("❌ Error saving language preference.")

async def save_city_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save user's preferred city."""
    try:
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        if not context.args:
            no_city = {
                'en': "Use: /savecity Rome (to save your preferred city)\n\n"
                      "Then use /myweather to get automatic forecasts for your saved city.",
                'it': "Usa: /salvacitta Roma (per salvare la tua città preferita)\n\n"
                      "Poi usa /miometeo per previsioni automatiche per la tua città salvata."
            }
            await update.message.reply_text(no_city[lang])
            return
        
        city = ' '.join(context.args)
        
        # Carica preferenze esistenti
        prefs = load_user_prefs()
        
        # Inizializza la struttura se non esiste
        if 'cities' not in prefs:
            prefs['cities'] = {}
        
        # Salva città per l'utente
        prefs['cities'][str(user_id)] = city
        save_user_prefs(prefs)
        
        success_msg = {
            'en': f"✅ Your city '{city}' has been saved!\n\n"
                  f"Now you can use:\n"
                  f"• /myweather - Get forecast for {city}\n"
                  f"• /myrain - Get rain forecast for {city}\n"
                  f"• /rainalerts - Enable rain notifications\n\n"
                  f"You'll also receive automatic morning reports at 8:00 AM!",
            'it': f"✅ La città '{city}' è stata salvata!\n\n"
                  f"Ora puoi usare:\n"
                  f"• /miometeo - Previsioni per {city}\n"
                  f"• /miapioggia - Previsioni pioggia per {city}\n"
                  f"• /avvisipioggia - Attiva notifiche pioggia\n\n"
                  f"Riceverai anche report automatici alle 8:00 del mattino!"
        }
        await update.message.reply_text(success_msg[lang])
    except Exception as e:
        logger.error(f"Error in save_city_command: {e}")
        error_msg = {
            'en': "❌ Error saving city. Please try again.",
            'it': "❌ Errore nel salvataggio della città. Riprova."
        }
        await update.message.reply_text(error_msg[get_user_language(update.effective_user.id)])

async def my_weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get weather for saved city."""
    try:
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        # Carica preferenze
        prefs = load_user_prefs()
        saved_city = prefs.get('cities', {}).get(str(user_id))
        
        if not saved_city:
            no_city_msg = {
                'en': "You haven't saved a city yet.\n\n"
                      "Use: /savecity Rome\n"
                      "Or send me any city name to get its forecast.",
                'it': "Non hai salvato una città.\n\n"
                      "Usa: /salvacitta Roma\n"
                      "O inviami un nome di città per le sue previsioni."
            }
            await update.message.reply_text(no_city_msg[lang])
            return
        
        await process_weather_request(update, saved_city, user_id, lang, show_rain_prompt=False)
    except Exception as e:
        logger.error(f"Error in my_weather_command: {e}")
        error_msg = {
            'en': "❌ Error retrieving weather data.",
            'it': "❌ Errore nel recupero dei dati meteo."
        }
        await update.message.reply_text(error_msg[get_user_language(update.effective_user.id)])

async def my_rain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get rain forecast for saved city."""
    try:
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        # Carica preferenze
        prefs = load_user_prefs()
        saved_city = prefs.get('cities', {}).get(str(user_id))
        
        if not saved_city:
            no_city_msg = {
                'en': "You haven't saved a city yet.\n\n"
                      "Use: /savecity Rome\n"
                      "Or use: /rain Rome",
                'it': "Non hai salvato una città.\n\n"
                      "Usa: /salvacitta Roma\n"
                      "O usa: /pioggia Roma"
            }
            await update.message.reply_text(no_city_msg[lang])
            return
        
        await process_rain_request(update, saved_city, user_id, lang)
    except Exception as e:
        logger.error(f"Error in my_rain_command: {e}")
        error_msg = {
            'en': "❌ Error retrieving rain data.",
            'it': "❌ Errore nel recupero dei dati pioggia."
        }
        await update.message.reply_text(error_msg[get_user_language(update.effective_user.id)])

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /weather or /meteo command - get weather for city."""
    try:
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        if not context.args:
            no_city = {
                'en': "Please specify a city. Example: /weather Rome\n\n"
                      "Or save your city with /savecity Rome to use /myweather",
                'it': "Specifica una città. Esempio: /meteo Roma\n\n"
                      "O salva la tua città con /salvacitta Roma per usare /miometeo"
            }
            await update.message.reply_text(no_city[lang])
            return
        
        city = ' '.join(context.args)
        await process_weather_request(update, city, user_id, lang, show_rain_prompt=True)
    except Exception as e:
        logger.error(f"Error in weather_command: {e}")
        error_msg = {
            'en': "❌ Error processing weather request.",
            'it': "❌ Errore nell'elaborazione della richiesta meteo."
        }
        await update.message.reply_text(error_msg[lang])

async def rain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rain or /pioggia command - get detailed rain forecast."""
    try:
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        if not context.args:
            no_city = {
                'en': "Please specify a city. Example: /rain Rome\n\n"
                      "Or save your city with /savecity Rome to use /myrain",
                'it': "Specifica una città. Esempio: /pioggia Roma\n\n"
                      "O salva la tua città con /salvacitta Roma per usare /miapioggia"
            }
            await update.message.reply_text(no_city[lang])
            return
        
        city = ' '.join(context.args)
        await process_rain_request(update, city, user_id, lang)
    except Exception as e:
        logger.error(f"Error in rain_command: {e}")
        error_msg = {
            'en': "❌ Error processing rain request.",
            'it': "❌ Errore nell'elaborazione della richiesta pioggia."
        }
        await update.message.reply_text(error_msg[lang])

async def rain_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle rain alerts for saved city."""
    try:
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        prefs = load_user_prefs()
        
        # Check if user has saved a city
        saved_city = prefs.get('cities', {}).get(str(user_id))
        if not saved_city:
            no_city_msg = {
                'en': "You need to save a city first to enable rain alerts.\n\n"
                      "Use: /savecity Rome",
                'it': "Devi prima salvare una città per attivare gli avvisi pioggia.\n\n"
                      "Usa: /salvacitta Roma"
            }
            await update.message.reply_text(no_city_msg[lang])
            return
        
        # Initialize rain_alerts if not exists
        if 'rain_alerts' not in prefs:
            prefs['rain_alerts'] = {}
        
        # Toggle the setting
        current = prefs['rain_alerts'].get(str(user_id), False)
        new_setting = not current
        
        prefs['rain_alerts'][str(user_id)] = new_setting
        save_user_prefs(prefs)
        
        if new_setting:
            msg = {
                'en': f"✅ Rain alerts ACTIVATED for {saved_city}!\n\n"
                      "I'll notify you when rain is expected in the next hour.\n\n"
                      "Notifications will be sent between 7:00 and 22:00.",
                'it': f"✅ Avvisi pioggia ATTIVATI per {saved_city}!\n\n"
                      "Ti avviserò quando è prevista pioggia nella prossima ora.\n\n"
                      "Le notifiche verranno inviate tra le 7:00 e le 22:00."
            }
        else:
            msg = {
                'en': "❌ Rain alerts DEACTIVATED.",
                'it': "❌ Avvisi pioggia DISATTIVATI."
            }
        
        await update.message.reply_text(msg[lang])
    except Exception as e:
        logger.error(f"Error in rain_alerts_command: {e}")
        error_msg = {
            'en': "❌ Error toggling rain alerts.",
            'it': "❌ Errore nell'attivazione degli avvisi pioggia."
        }
        await update.message.reply_text(error_msg[get_user_language(update.effective_user.id)])

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    try:
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
                'en': "Send me a city name for the full weather forecast.\n\n"
                      "Or use /myweather for your saved city.",
                'it': "Inviami il nome di una città per le previsioni complete.\n\n"
                      "O usa /miometeo per la tua città salvata."
            }
            await update.message.reply_text(prompt[lang])
            return
        
        # Handle my city button
        if text in ["📍 My City / Mia Città"]:
            await my_weather_command(update, context)
            return
        
        # Handle save city button
        if text in ["💾 Save City / Salva Città"]:
            prompt = {
                'en': "Send me the city you want to save.\n\n"
                      "Example: Rome\n"
                      "Or use: /savecity Rome",
                'it': "Inviami la città che vuoi salvare.\n\n"
                      "Esempio: Roma\n"
                      "O usa: /salvacitta Roma"
            }
            await update.message.reply_text(prompt[lang])
            return
        
        # Handle rain alert button
        if text in ["🌧️ Rain Alert / Allerta Pioggia"]:
            prompt = {
                'en': "Send me a city name for detailed rain alerts.\n\n"
                      "Or use /myrain for your saved city.",
                'it': "Inviami il nome di una città per avvisi pioggia dettagliati.\n\n"
                      "O usa /miapioggia per la tua città salvata."
            }
            await update.message.reply_text(prompt[lang])
            return
        
        # Handle rain notifications button
        if text in ["🔔 Rain Notif / Notif Pioggia"]:
            await rain_alerts_command(update, context)
            return
        
        # Handle language change button
        if text in ["🌐 Language / Lingua"]:
            await language_command(update, context)
            return
        
        # If it's a short text, assume it's a city name
        if len(text) < 50:
            await process_weather_request(update, text, user_id, lang, show_rain_prompt=True)
        else:
            error_msg = {
                'en': "Please send me a city name (e.g., 'Rome' or 'London').",
                'it': "Per favore inviami un nome di città (es. 'Roma' o 'Londra')."
            }
            await update.message.reply_text(error_msg[lang])
    except Exception as e:
        logger.error(f"Error in handle_text_message: {e}")
        error_msg = {
            'en': "❌ Error processing message.",
            'it': "❌ Errore nell'elaborazione del messaggio."
        }
        await update.message.reply_text(error_msg[get_user_language(update.effective_user.id)])

async def process_weather_request(update, city, user_id, lang, show_rain_prompt=True):
    """Process weather request and send response."""
    try:
        await update.message.reply_chat_action(action="typing")
        
        result = get_complete_weather_report(city, lang)
        
        if result['success']:
            await update.message.reply_text(result['message'], parse_mode='Markdown')
            
            # Save city automatically if not already saved
            prefs = load_user_prefs()
            if 'cities' not in prefs:
                prefs['cities'] = {}
            
            # Ask if user wants to save this city (only if not already saved)
            if show_rain_prompt and str(user_id) not in prefs['cities']:
                save_prompt = {
                    'en': f"\n💡 Want to save '{city}' as your default city?\n"
                          f"Use: /savecity {city}\n"
                          f"Then use /myweather for automatic forecasts!",
                    'it': f"\n💡 Vuoi salvare '{city}' come tua città predefinita?\n"
                          f"Usa: /salvacitta {city}\n"
                          f"Poi usa /miometeo per previsioni automatiche!"
                }
                await update.message.reply_text(save_prompt[lang])
        else:
            error_msg = {
                'en': f"❌ I couldn't find weather data for '{city}'.\n\n"
                      "Please check the city name and try again.\n"
                      "Examples: Rome, London, Paris, New York",
                'it': f"❌ Non riesco a trovare dati meteo per '{city}'.\n\n"
                      "Controlla il nome della città e riprova.\n"
                      "Esempi: Roma, Milano, Napoli, Torino"
            }
            await update.message.reply_text(error_msg[lang])
    except Exception as e:
        logger.error(f"Error in process_weather_request for city '{city}': {e}")
        error_msg = {
            'en': f"❌ Error retrieving weather data for '{city}'.\n\n"
                  "Please try again later.",
            'it': f"❌ Errore nel recupero dei dati meteo per '{city}'.\n\n"
                  "Riprova più tardi."
        }
        await update.message.reply_text(error_msg[lang])

async def process_rain_request(update, city, user_id, lang):
    """Process rain forecast request and send detailed response."""
    try:
        await update.message.reply_chat_action(action="typing")
        
        result = get_detailed_rain_forecast(city, lang)
        
        if result['success']:
            await update.message.reply_text(result['message'], parse_mode='Markdown')
            
            # Save city automatically if not already saved
            prefs = load_user_prefs()
            if 'cities' not in prefs:
                prefs['cities'] = {}
            
            if str(user_id) not in prefs['cities']:
                save_prompt = {
                    'en': f"\n💡 Want to save '{city}' as your default city?\n"
                          f"Use: /savecity {city}\n"
                          f"Then use /myrain for automatic rain forecasts!",
                    'it': f"\n💡 Vuoi salvare '{city}' come tua città predefinita?\n"
                          f"Usa: /salvacitta {city}\n"
                          f"Poi usa /miapioggia per previsioni pioggia automatiche!"
                }
                await update.message.reply_text(save_prompt[lang])
        else:
            error_msg = {
                'en': f"❌ I couldn't find rain data for '{city}'.\n\n"
                      "Please check the city name and try again.",
                'it': f"❌ Non riesco a trovare dati pioggia per '{city}'.\n\n"
                      "Controlla il nome della città e riprova."
            }
            await update.message.reply_text(error_msg[lang])
    except Exception as e:
        logger.error(f"Error in process_rain_request for city '{city}': {e}")
        error_msg = {
            'en': f"❌ Error retrieving rain data for '{city}'.\n\n"
                  "Please try again later.",
            'it': f"❌ Errore nel recupero dei dati pioggia per '{city}'.\n\n"
                  "Riprova più tardi."
        }
        await update.message.reply_text(error_msg[lang])

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help or /aiuto command."""
    try:
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        help_text = {
            'en': "🌤️ *Weather Bot Help* 🌤️\n\n"
                  "*Basic Commands:*\n"
                  "• Send any city name for forecast\n"
                  "• /weather <city> - Full forecast\n"
                  "• /rain <city> - Detailed rain forecast\n\n"
                  "*City Management:*\n"
                  "• /savecity <city> - Save your default city\n"
                  "• /myweather - Forecast for saved city\n"
                  "• /myrain - Rain forecast for saved city\n\n"
                  "*Rain Notifications:*\n"
                  "• /rainalerts - Toggle rain notifications (when rain is imminent)\n\n"
                  "*Settings:*\n"
                  "• /language - Change language\n"
                  "• /help - Show this message\n\n"
                  "*Automatic Reports:*\n"
                  "• Morning forecast at 8:00 AM (if city saved)\n"
                  "• Rain alerts when rain is expected (if enabled)",
            'it': "🌤️ *Aiuto Bot Meteo* 🌤️\n\n"
                  "*Comandi Base:*\n"
                  "• Invia un nome di città per le previsioni\n"
                  "• /meteo <città> - Previsioni complete\n"
                  "• /pioggia <città> - Previsioni pioggia dettagliate\n\n"
                  "*Gestione Città:*\n"
                  "• /salvacitta <città> - Salva la tua città predefinita\n"
                  "• /miometeo - Previsioni per città salvata\n"
                  "• /miapioggia - Previsioni pioggia per città salvata\n\n"
                  "*Notifiche Pioggia:*\n"
                  "• /avvisipioggia - Attiva notifiche pioggia (quando la pioggia è imminente)\n\n"
                  "*Impostazioni:*\n"
                  "• /lingua - Cambia lingua\n"
                  "• /aiuto - Mostra questo messaggio\n\n"
                  "*Report Automatici:*\n"
                  "• Previsioni mattutine alle 8:00 (se città salvata)\n"
                  "• Avvisi pioggia quando è prevista pioggia (se attivati)"
        }
        
        await update.message.reply_text(help_text[lang], parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        error_msg = "❌ Error displaying help."
        await update.message.reply_text(error_msg)

def setup_handlers(app):
    """Set up all handlers for the bot."""
    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("aiuto", help_command))
    
    # Weather commands
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("meteo", weather_command))
    
    # Rain commands
    app.add_handler(CommandHandler("rain", rain_command))
    app.add_handler(CommandHandler("pioggia", rain_command))
    
    # Saved city commands
    app.add_handler(CommandHandler("savecity", save_city_command))
    app.add_handler(CommandHandler("salvacitta", save_city_command))
    
    app.add_handler(CommandHandler("myweather", my_weather_command))
    app.add_handler(CommandHandler("miometeo", my_weather_command))
    
    app.add_handler(CommandHandler("myrain", my_rain_command))
    app.add_handler(CommandHandler("miapioggia", my_rain_command))
    
    # Rain alerts commands
    app.add_handler(CommandHandler("rainalerts", rain_alerts_command))
    app.add_handler(CommandHandler("avvisipioggia", rain_alerts_command))
    
    # Language commands
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("lingua", language_command))
    
    # Add message handler for text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

async def setup_webhook(app, webhook_url):
    """Set up webhook configuration."""
    try:
        secret_token = getattr(Config, 'WEBHOOK_SECRET', '')
        
        await app.bot.set_webhook(
            url=webhook_url,
            secret_token=secret_token,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        logger.info(f"Webhook set to: {webhook_url}")
        return True
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return False

def cleanup():
    """Cleanup resources on exit."""
    logger.info("Bot shutting down...")
    # Eventuali cleanup aggiuntivi

def main():
    """Start the bot in webhook mode (Render) or polling mode (local)."""
    if not Config.BOT_TOKEN:
        logger.error("ERROR: BOT_TOKEN not found. Please check your .env file.")
        return
    
    # Register cleanup
    atexit.register(cleanup)
    
    # Create application
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Set up all handlers
    setup_handlers(app)
    
    # Decide mode: Webhook for Render or Polling for local
    if getattr(Config, 'WEBHOOK_MODE', False) and getattr(Config, 'RENDER_EXTERNAL_URL', None):
        logger.info("Starting bot in WEBHOOK mode for Render...")
        
        # Build webhook URL
        webhook_url = f"{Config.RENDER_EXTERNAL_URL}/webhook"
        logger.info(f"Webhook URL: {webhook_url}")
        
        # Set up webhook
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Try to set up webhook
        success = loop.run_until_complete(setup_webhook(app, webhook_url))
        
        if success:
            # Start webhook server
            app.run_webhook(
                listen="0.0.0.0",
                port=getattr(Config, 'PORT', 10000),
                webhook_url=webhook_url,
                secret_token=getattr(Config, 'WEBHOOK_SECRET', ''),
                key=getattr(Config, 'PRIVATE_KEY', None),
                cert=getattr(Config, 'CERTIFICATE', None),
                drop_pending_updates=True
            )
        else:
            logger.error("Failed to set up webhook. Falling back to polling...")
            logger.info("Starting bot in POLLING mode...")
            app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    else:
        logger.info("Starting bot in POLLING mode (local development)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()