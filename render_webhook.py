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

# ========== TRANSLATIONS ==========

TRANSLATIONS = {
    'en': {
        'welcome': "Hello! I'm your Weather Assistant 🌤️\n\nSend me a city name or use:\n/weather <city> - Full forecast\n/rain <city> - Detailed rain alerts\n/savecity <city> - Save your city\n/myweather - Forecast for saved city\n/rainalerts - Toggle rain notifications\n/language - Change language",
        'help': "🌤️ *Weather Bot Help*\n\n*Basic Commands:*\n• Send any city name for forecast\n• /weather <city> - Full forecast\n• /rain <city> - Detailed rain forecast\n\n*City Management:*\n• /savecity <city> - Save your default city\n• /myweather - Forecast for saved city\n• /myrain - Rain forecast for saved city\n\n*Rain Notifications:*\n• /rainalerts - Toggle rain notifications\n\n*Settings:*\n• /language - Change language\n• /help - Show this message",
        'no_city_weather': "Please specify a city. Example: /weather Rome\n\nOr save your city with /savecity Rome to use /myweather",
        'no_city_rain': "Please specify a city. Example: /rain Rome\n\nOr save your city with /savecity Rome to use /myrain",
        'city_saved': "✅ Your city '{city}' has been saved!\n\nNow you can use:\n• /myweather - Get forecast for {city}\n• /myrain - Get rain forecast for {city}\n• /rainalerts - Enable rain notifications\n\nYou'll also receive automatic morning reports at 8:00 AM!",
        'no_saved_city': "You haven't saved a city yet.\n\nUse: /savecity Rome\nOr send me any city name to get its forecast.",
        'weather_for_saved': "🌤️ Weather for your saved city ({city}):",
        'rain_for_saved': "🌧️ Rain forecast for your saved city ({city}):",
        'city_not_found': "❌ I couldn't find weather data for '{city}'.\n\nPlease check the city name and try again.",
        'error': "❌ Sorry, there was an error. Please try again later.",
        'choose_language': "Choose your language:",
        'language_set': "✅ Language set to English!",
        'rain_alerts_on': "✅ Rain alerts ACTIVATED for {city}!\n\nI'll notify you when rain is expected.\nNotifications: 7:00-22:00.",
        'rain_alerts_off': "❌ Rain alerts DEACTIVATED.",
        'save_prompt': "💡 Want to save '{city}' as your default city?\nUse: /savecity {city}\nThen use /myweather for automatic forecasts!"
    },
    'it': {
        'welcome': "Ciao! Sono il tuo Assistente Meteo 🌤️\n\nInviami un nome di città o usa:\n/meteo <città> - Previsioni complete\n/pioggia <città> - Avvisi pioggia\n/salvacitta <città> - Salva la tua città\n/miometeo - Previsioni per città salvata\n/avvisipioggia - Attiva notifiche pioggia\n/lingua - Cambia lingua",
        'help': "🌤️ *Aiuto Bot Meteo*\n\n*Comandi Base:*\n• Invia un nome di città per le previsioni\n• /meteo <città> - Previsioni complete\n• /pioggia <città> - Previsioni pioggia dettagliate\n\n*Gestione Città:*\n• /salvacitta <città> - Salva la tua città predefinita\n• /miometeo - Previsioni per città salvata\n• /miapioggia - Previsioni pioggia per città salvata\n\n*Notifiche Pioggia:*\n• /avvisipioggia - Attiva notifiche pioggia\n\n*Impostazioni:*\n• /lingua - Cambia lingua\n• /aiuto - Mostra questo messaggio",
        'no_city_weather': "Specifica una città. Esempio: /meteo Roma\n\nO salva la tua città con /salvacitta Roma per usare /miometeo",
        'no_city_rain': "Specifica una città. Esempio: /pioggia Roma\n\nO salva la tua città con /salvacitta Roma per usare /miapioggia",
        'city_saved': "✅ La città '{city}' è stata salvata!\n\nOra puoi usare:\n• /miometeo - Previsioni per {city}\n• /miapioggia - Previsioni pioggia per {city}\n• /avvisipioggia - Attiva notifiche pioggia\n\nRiceverai anche report automatici alle 8:00 del mattino!",
        'no_saved_city': "Non hai salvato una città.\n\nUsa: /salvacitta Roma\nO inviami un nome di città per le sue previsioni.",
        'weather_for_saved': "🌤️ Previsioni per la tua città salvata ({city}):",
        'rain_for_saved': "🌧️ Previsioni pioggia per la tua città salvata ({city}):",
        'city_not_found': "❌ Non riesco a trovare dati meteo per '{city}'.\n\nControlla il nome della città e riprova.",
        'error': "❌ Mi dispiace, c'è stato un errore. Riprova più tardi.",
        'choose_language': "Scegli la tua lingua:",
        'language_set': "✅ Lingua impostata su Italiano!",
        'rain_alerts_on': "✅ Avvisi pioggia ATTIVATI per {city}!\n\nTi avviserò quando è prevista pioggia.\nNotifiche: 7:00-22:00.",
        'rain_alerts_off': "❌ Avvisi pioggia DISATTIVATI.",
        'save_prompt': "💡 Vuoi salvare '{city}' come tua città predefinita?\nUsa: /salvacitta {city}\nPoi usa /miometeo per previsioni automatiche!"
    }
}

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

# ========== USER PREFERENCES ==========

def get_user_language(user_id):
    """Get user's language preference."""
    try:
        from user_prefs import load_user_prefs
        prefs = load_user_prefs()
        return prefs.get(str(user_id), 'en')
    except:
        return 'en'

def set_user_language(user_id, lang):
    """Set user's language preference."""
    try:
        from user_prefs import load_user_prefs, save_user_prefs
        prefs = load_user_prefs()
        prefs[str(user_id)] = lang
        save_user_prefs(prefs)
        return True
    except:
        return False

def get_user_city_pref(user_id):
    """Get user's saved city."""
    try:
        from user_prefs import load_user_prefs
        prefs = load_user_prefs()
        return prefs.get('cities', {}).get(str(user_id))
    except:
        return None

def save_user_city_pref(user_id, city):
    """Save user's city."""
    try:
        from user_prefs import load_user_prefs, save_user_prefs
        prefs = load_user_prefs()
        
        if 'cities' not in prefs:
            prefs['cities'] = {}
        
        prefs['cities'][str(user_id)] = city
        save_user_prefs(prefs)
        return True
    except:
        return False

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
    """Handle Telegram webhook requests with multi-language support."""
    
    if request.method == 'GET':
        return "✅ Webhook endpoint is working! Telegram sends POST requests with JSON updates.", 200
    
    # Verify secret token
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    
    if secret_token != Config.WEBHOOK_SECRET:
        logger.warning(f"❌ Invalid webhook secret")
        return 'Unauthorized', 403
    
    logger.info("✅ Valid webhook request received")
    
    try:
        # Get update from Telegram
        update = request.get_json()
        
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            text = update['message'].get('text', '').strip()
            username = update['message']['chat'].get('username', 'Unknown')
            
            logger.info(f"📨 Message from @{username} ({chat_id}): {text}")
            
            # Get user language
            lang = get_user_language(chat_id)
            
            # Handle language selection
            if text in ["🇬🇧 English", "🇮🇹 Italiano", "/language", "/lingua"]:
                if text == "🇮🇹 Italiano" or text == "/lingua":
                    set_user_language(chat_id, 'it')
                    response_text = TRANSLATIONS['it']['language_set']
                else:
                    set_user_language(chat_id, 'en')
                    response_text = TRANSLATIONS['en']['language_set']
                
                # Also show language options
                keyboard = {
                    'inline_keyboard': [[
                        {'text': '🇬🇧 English', 'callback_data': 'lang_en'},
                        {'text': '🇮🇹 Italiano', 'callback_data': 'lang_it'}
                    ]]
                }
                
                requests.post(
                    f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
                    json={
                        'chat_id': chat_id,
                        'text': TRANSLATIONS[lang]['choose_language'],
                        'reply_markup': keyboard
                    }
                )
                
                # Send language confirmation
                requests.post(
                    f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
                    json={
                        'chat_id': chat_id,
                        'text': response_text
                    }
                )
                return 'OK', 200
            
            # Import weather service here to avoid circular imports
            from weather_service import get_complete_weather_report, get_detailed_rain_forecast
            
            # Handle commands with language support
            if text in ['/start', '/start@' + (update['message'].get('chat', {}).get('username', ''))]:
                response_text = TRANSLATIONS[lang]['welcome']
            
            elif text in ['/help', '/aiuto', '/help@', '/aiuto@']:
                response_text = TRANSLATIONS[lang]['help']
            
            elif text.startswith(('/weather ', '/meteo ')):
                city = text.split(' ', 1)[1] if ' ' in text else ''
                if not city:
                    response_text = TRANSLATIONS[lang]['no_city_weather']
                else:
                    result = get_complete_weather_report(city, lang)
                    if result['success']:
                        response_text = result['message']
                        # Ask to save city
                        if not get_user_city_pref(chat_id):
                            save_prompt = TRANSLATIONS[lang]['save_prompt'].format(city=city)
                            requests.post(
                                f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
                                json={
                                    'chat_id': chat_id,
                                    'text': save_prompt
                                }
                            )
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=city)
            
            elif text.startswith(('/rain ', '/pioggia ')):
                city = text.split(' ', 1)[1] if ' ' in text else ''
                if not city:
                    response_text = TRANSLATIONS[lang]['no_city_rain']
                else:
                    result = get_detailed_rain_forecast(city, lang)
                    if result['success']:
                        response_text = result['message']
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=city)
            
            elif text.startswith(('/savecity ', '/salvacitta ')):
                city = text.split(' ', 1)[1] if ' ' in text else ''
                if not city:
                    response_text = TRANSLATIONS[lang]['no_city_weather']
                else:
                    if save_user_city_pref(chat_id, city):
                        response_text = TRANSLATIONS[lang]['city_saved'].format(city=city)
                    else:
                        response_text = TRANSLATIONS[lang]['error']
            
            elif text in ['/myweather', '/miometeo']:
                saved_city = get_user_city_pref(chat_id)
                if not saved_city:
                    response_text = TRANSLATIONS[lang]['no_saved_city']
                else:
                    result = get_complete_weather_report(saved_city, lang)
                    if result['success']:
                        response_text = f"{TRANSLATIONS[lang]['weather_for_saved'].format(city=saved_city)}\n\n{result['message']}"
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=saved_city)
            
            elif text in ['/myrain', '/miapioggia']:
                saved_city = get_user_city_pref(chat_id)
                if not saved_city:
                    response_text = TRANSLATIONS[lang]['no_saved_city']
                else:
                    result = get_detailed_rain_forecast(saved_city, lang)
                    if result['success']:
                        response_text = f"{TRANSLATIONS[lang]['rain_for_saved'].format(city=saved_city)}\n\n{result['message']}"
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=saved_city)
            
            elif text in ['/rainalerts', '/avvisipioggia']:
                saved_city = get_user_city_pref(chat_id)
                if not saved_city:
                    response_text = TRANSLATIONS[lang]['no_saved_city']
                else:
                    # Toggle rain alerts (simplified version)
                    # In a real implementation, you would save this preference
                    response_text = f"Rain alerts feature coming soon! {TRANSLATIONS[lang]['rain_alerts_on'].format(city=saved_city)}"
            
            else:
                # Assume it's a city name (not a command)
                if len(text) < 50 and text not in ['', ' ']:
                    # Try to get weather
                    result = get_complete_weather_report(text, lang)
                    if result['success']:
                        response_text = result['message']
                        # Ask to save city
                        if not get_user_city_pref(chat_id):
                            save_prompt = TRANSLATIONS[lang]['save_prompt'].format(city=text)
                            requests.post(
                                f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
                                json={
                                    'chat_id': chat_id,
                                    'text': save_prompt
                                }
                            )
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=text)
                else:
                    response_text = TRANSLATIONS[lang]['help']
            
            # Send response to Telegram
            try:
                requests.post(
                    f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
                    json={
                        'chat_id': chat_id,
                        'text': response_text,
                        'parse_mode': 'Markdown',
                        'disable_web_page_preview': True
                    },
                    timeout=10
                )
                logger.info(f"✅ Response sent to {chat_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send Telegram response: {e}")
        
        elif 'callback_query' in update:
            # Handle callback queries (for language selection, etc.)
            callback_data = update['callback_query']['data']
            user_id = update['callback_query']['from']['id']
            
            if callback_data.startswith('lang_'):
                lang_code = callback_data.split('_')[1]
                set_user_language(user_id, lang_code)
                
                # Answer callback query
                requests.post(
                    f'https://api.telegram.org/bot{Config.BOT_TOKEN}/answerCallbackQuery',
                    json={
                        'callback_query_id': update['callback_query']['id'],
                        'text': f'Language set to {"English" if lang_code == "en" else "Italian"}'
                    }
                )
                
                # Send confirmation
                requests.post(
                    f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
                    json={
                        'chat_id': user_id,
                        'text': TRANSLATIONS[lang_code]['language_set']
                    }
                )
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}")
        # Still return OK to Telegram to avoid webhook errors
        return 'OK', 200

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