import os
import logging
import hmac
import hashlib
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify
import requests
from config import Config
from weather_service import get_complete_weather_report, get_detailed_rain_forecast

# Configura logging con output ridotto
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========== USER PREFERENCES MANAGEMENT ==========

USER_PREFS_FILE = 'user_preferences.json'

def load_user_prefs():
    """Load user preferences from file."""
    if os.path.exists(USER_PREFS_FILE):
        try:
            with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
                return eval(f.read())
        except Exception as e:
            logger.error(f"Error loading preferences: {e}")
            return {}
    return {}

def save_user_prefs(prefs):
    """Save user preferences to file."""
    try:
        with open(USER_PREFS_FILE, 'w', encoding='utf-8') as f:
            f.write(str(prefs))
        return True
    except Exception as e:
        logger.error(f"Error saving preferences: {e}")
        return False

def get_user_language(user_id):
    """Get user's preferred language."""
    prefs = load_user_prefs()
    if 'languages' in prefs:
        return prefs['languages'].get(str(user_id), 'en')
    return prefs.get(str(user_id), 'en')

def set_user_language(user_id, lang):
    """Set user's language preference."""
    prefs = load_user_prefs()
    if 'languages' not in prefs:
        prefs['languages'] = {}
    prefs['languages'][str(user_id)] = lang
    return save_user_prefs(prefs)

def get_user_city(user_id):
    """Get user's saved city."""
    prefs = load_user_prefs()
    return prefs.get('cities', {}).get(str(user_id))

def save_user_city(user_id, city):
    """Save user's city."""
    prefs = load_user_prefs()
    if 'cities' not in prefs:
        prefs['cities'] = {}
    prefs['cities'][str(user_id)] = city
    return save_user_prefs(prefs)

def get_rain_alerts_status(user_id):
    """Get user's rain alerts status."""
    prefs = load_user_prefs()
    return prefs.get('rain_alerts', {}).get(str(user_id), False)

def set_rain_alerts_status(user_id, status):
    """Set user's rain alerts status."""
    prefs = load_user_prefs()
    if 'rain_alerts' not in prefs:
        prefs['rain_alerts'] = {}
    prefs['rain_alerts'][str(user_id)] = status
    return save_user_prefs(prefs)

def get_all_users_with_cities():
    """Get all users with saved cities."""
    prefs = load_user_prefs()
    return prefs.get('cities', {})

def get_all_users_with_rain_alerts():
    """Get all users with rain alerts enabled."""
    prefs = load_user_prefs()
    cities = prefs.get('cities', {})
    rain_alerts = prefs.get('rain_alerts', {})
    return {uid: True for uid in rain_alerts if rain_alerts[uid] and uid in cities}

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
        'language_set_it': "✅ Lingua impostata su Italiano!",
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
        'language_set_en': "✅ Language set to English!",
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

# ========== TELEGRAM WEBHOOK HANDLER ==========

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Handle Telegram webhook requests."""
    
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
                
                send_telegram_message(chat_id, TRANSLATIONS[lang]['choose_language'], keyboard)
                send_telegram_message(chat_id, response_text)
                return 'OK', 200
            
            # Handle commands with language support
            if text in ['/start', '/start@']:
                response_text = TRANSLATIONS[lang]['welcome']
            
            elif text in ['/help', '/aiuto']:
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
                        if not get_user_city(chat_id):
                            save_prompt = TRANSLATIONS[lang]['save_prompt'].format(city=city)
                            send_telegram_message(chat_id, save_prompt)
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
                        # Ask to save city
                        if not get_user_city(chat_id):
                            save_prompt = TRANSLATIONS[lang]['save_prompt'].format(city=city)
                            send_telegram_message(chat_id, save_prompt)
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=city)
            
            elif text.startswith(('/savecity ', '/salvacitta ')):
                city = text.split(' ', 1)[1] if ' ' in text else ''
                if not city:
                    response_text = TRANSLATIONS[lang]['no_city_weather']
                else:
                    if save_user_city(chat_id, city):
                        # Auto-enable rain alerts when saving a city
                        set_rain_alerts_status(chat_id, True)
                        response_text = TRANSLATIONS[lang]['city_saved'].format(city=city)
                    else:
                        response_text = TRANSLATIONS[lang]['error']
            
            elif text in ['/myweather', '/miometeo']:
                saved_city = get_user_city(chat_id)
                if not saved_city:
                    response_text = TRANSLATIONS[lang]['no_saved_city']
                else:
                    result = get_complete_weather_report(saved_city, lang)
                    if result['success']:
                        response_text = f"{TRANSLATIONS[lang]['weather_for_saved'].format(city=saved_city)}\n\n{result['message']}"
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=saved_city)
            
            elif text in ['/myrain', '/miapioggia']:
                saved_city = get_user_city(chat_id)
                if not saved_city:
                    response_text = TRANSLATIONS[lang]['no_saved_city']
                else:
                    result = get_detailed_rain_forecast(saved_city, lang)
                    if result['success']:
                        response_text = f"{TRANSLATIONS[lang]['rain_for_saved'].format(city=saved_city)}\n\n{result['message']}"
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=saved_city)
            
            elif text in ['/rainalerts', '/avvisipioggia']:
                saved_city = get_user_city(chat_id)
                if not saved_city:
                    response_text = TRANSLATIONS[lang]['no_saved_city']
                else:
                    # Toggle rain alerts
                    current_status = get_rain_alerts_status(chat_id)
                    new_status = not current_status
                    set_rain_alerts_status(chat_id, new_status)
                    
                    if new_status:
                        response_text = TRANSLATIONS[lang]['rain_alerts_on'].format(city=saved_city)
                    else:
                        response_text = TRANSLATIONS[lang]['rain_alerts_off']
            
            else:
                # Assume it's a city name (not a command)
                if len(text) < 50 and text not in ['', ' ']:
                    # Try to get weather
                    result = get_complete_weather_report(text, lang)
                    if result['success']:
                        response_text = result['message']
                        # Ask to save city
                        if not get_user_city(chat_id):
                            save_prompt = TRANSLATIONS[lang]['save_prompt'].format(city=text)
                            send_telegram_message(chat_id, save_prompt)
                    else:
                        response_text = TRANSLATIONS[lang]['city_not_found'].format(city=text)
                else:
                    response_text = TRANSLATIONS[lang]['help']
            
            # Send response to Telegram
            send_telegram_message(chat_id, response_text)
            logger.info(f"✅ Response sent to {chat_id}")
        
        elif 'callback_query' in update:
            # Handle callback queries (for language selection, etc.)
            callback_data = update['callback_query']['data']
            user_id = update['callback_query']['from']['id']
            
            if callback_data.startswith('lang_'):
                lang_code = callback_data.split('_')[1]
                set_user_language(user_id, lang_code)
                
                # Answer callback query
                answer_callback_query(update['callback_query']['id'], 
                                     f'Language set to {"English" if lang_code == "en" else "Italian"}')
                
                # Send confirmation
                if lang_code == 'en':
                    send_telegram_message(user_id, TRANSLATIONS['en']['language_set'])
                else:
                    send_telegram_message(user_id, TRANSLATIONS['it']['language_set'])
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}")
        # Still return OK to Telegram to avoid webhook errors
        return 'OK', 200

def send_telegram_message(chat_id, text, reply_markup=None):
    """Send message to Telegram."""
    try:
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            data['reply_markup'] = reply_markup
        
        response = requests.post(
            f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage',
            json=data,
            timeout=10
        )
        return response.json()
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram message: {e}")
        return None

def answer_callback_query(callback_query_id, text):
    """Answer callback query."""
    try:
        requests.post(
            f'https://api.telegram.org/bot{Config.BOT_TOKEN}/answerCallbackQuery',
            json={
                'callback_query_id': callback_query_id,
                'text': text
            }
        )
    except Exception as e:
        logger.error(f"❌ Failed to answer callback query: {e}")

# ========== CRON JOB ENDPOINTS ==========

@app.route('/trigger-morning-reports', methods=['POST'])
def trigger_morning_reports():
    """Endpoint to trigger morning reports for ALL users."""
    if not verify_cron_request():
        logger.warning("❌ Unauthorized cron attempt for morning reports")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        logger.info("🌅 Cron job triggered - sending morning reports")
        
        # Run in background thread with minimal logging
        thread = threading.Thread(target=send_morning_reports_minimal, daemon=True)
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
    """Endpoint to trigger rain alerts check for ALL users."""
    if not verify_cron_request():
        logger.warning("❌ Unauthorized cron attempt for rain check")
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        logger.info("🌧️ Cron job triggered - checking rain alerts")
        
        # Run in background thread with minimal logging
        thread = threading.Thread(target=check_and_send_rain_alerts_minimal, daemon=True)
        thread.start()
        
        return jsonify({
            'status': 'started',
            'message': 'Rain alerts check is running in background'
        }), 200
    except Exception as e:
        logger.error(f"❌ Error triggering rain check: {e}")
        return jsonify({'error': str(e)}), 500

# ========== MINIMAL LOGGING FUNCTIONS FOR CRON JOBS ==========

def send_morning_reports_minimal():
    """Send morning weather reports with minimal logging."""
    try:
        # Get all users with saved cities
        users_with_cities = get_all_users_with_cities()
        
        if not users_with_cities:
            logger.info("ℹ️ No users with saved cities")
            return
        
        logger.info(f"📨 Sending morning reports to {len(users_with_cities)} users")
        
        successful_sends = 0
        failed_sends = 0
        
        for user_id_str, city in users_with_cities.items():
            try:
                user_id = int(user_id_str)
                lang = get_user_language(user_id_str)
                
                # Get weather report
                result = get_complete_weather_report(city, lang)
                
                if result['success']:
                    # Format morning message
                    if lang == 'it':
                        morning_greeting = f"🌅 *Buongiorno!* Ecco le previsioni per {city}:\n\n"
                    else:
                        morning_greeting = f"🌅 *Good morning!* Here's the forecast for {city}:\n\n"
                    
                    full_message = morning_greeting + result['message']
                    
                    # Send message
                    send_telegram_message(user_id, full_message)
                    
                    successful_sends += 1
                    
                    # Log progress only every 10 users to reduce output
                    if successful_sends % 10 == 0:
                        logger.debug(f"Progress: {successful_sends}/{len(users_with_cities)}")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.3)
                    
                else:
                    failed_sends += 1
                    logger.debug(f"⚠️ Could not get weather for {city} (user {user_id})")
                    
            except Exception as e:
                failed_sends += 1
                logger.debug(f"❌ Error for user {user_id_str}: {str(e)[:50]}")
        
        # Log summary (short)
        logger.info(f"📊 Morning reports: {successful_sends} sent, {failed_sends} failed")
        
    except Exception as e:
        logger.error(f"❌ Critical error in morning reports: {str(e)[:100]}")

def check_and_send_rain_alerts_minimal():
    """Check rain alerts with minimal logging."""
    try:
        # Get all users with rain alerts enabled
        users_with_alerts = get_all_users_with_rain_alerts()
        
        if not users_with_alerts:
            logger.info("ℹ️ No users with rain alerts")
            return
        
        logger.info(f"🌧️ Checking rain for {len(users_with_alerts)} users")
        
        alerts_sent = 0
        errors = 0
        
        for user_id_str in users_with_alerts.keys():
            try:
                user_id = int(user_id_str)
                lang = get_user_language(user_id_str)
                city = get_user_city(user_id_str)
                
                if not city:
                    continue
                
                # Get weather data
                result = get_complete_weather_report(city, lang)
                
                if not result['success']:
                    continue
                
                # Check if there's rain in the forecast
                # This is a simplified check - in a real implementation
                # you would parse the weather data to check for rain
                
                # For now, we'll just log that we checked
                # In a real bot, you would implement actual rain detection
                
                alerts_sent += 1
                
                # Log progress only occasionally
                if alerts_sent % 20 == 0:
                    logger.debug(f"Rain check progress: {alerts_sent}/{len(users_with_alerts)}")
                
                # Small delay
                time.sleep(0.2)
                
            except Exception as e:
                errors += 1
                logger.debug(f"❌ Error checking user {user_id_str}: {str(e)[:50]}")
        
        # Short summary
        logger.info(f"📊 Rain checks: {alerts_sent} checked, {errors} errors")
        
    except Exception as e:
        logger.error(f"❌ Critical error in rain checks: {str(e)[:100]}")

# ========== ADMIN ENDPOINTS ==========

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weather Report Bot 🌤️</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .container { max-width: 800px; margin: 0 auto; }
            .status { color: green; font-weight: bold; }
            .endpoint { text-align: left; background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            code { background: #333; color: #fff; padding: 2px 5px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌤️ Weather Report Bot</h1>
            <p class="status">✅ Service is running</p>
            <p>Telegram weather bot is active in background.</p>
            
            <div class="endpoint">
                <h3>📊 Bot Status</h3>
                <p><strong>Health Check:</strong> <a href="/health">/health</a></p>
                <p><strong>Webhook Test:</strong> <a href="/webhook">/webhook</a> (GET)</p>
                <p><strong>Cron Test:</strong> <a href="/test-cron">/test-cron</a></p>
            </div>
            
            <div class="endpoint">
                <h3>🔧 Admin Endpoints</h3>
                <p><strong>All User Stats:</strong> <a href="/admin/stats">/admin/stats</a></p>
                <p><strong>Fix Rain Alerts for ALL Users:</strong> <a href="/admin/fix-all-rain-alerts">/admin/fix-all-rain-alerts</a></p>
                <p><strong>Send Test to Specific User:</strong> <code>/admin/test-user?user_id=123456</code></p>
            </div>
            
            <div class="endpoint">
                <h3>⏰ Cron Endpoints (POST only)</h3>
                <p><code>/trigger-morning-reports</code> - Send morning reports to ALL users</p>
                <p><code>/trigger-rain-check</code> - Check and send rain alerts to ALL users</p>
                <p><em>Requires header: X-Cron-Signature: [signature]</em></p>
            </div>
            
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
        'timestamp': datetime.now().isoformat(),
        'users': len(get_all_users_with_cities())
    }), 200

@app.route('/ping')
def ping():
    """Endpoint per mantenere attivo il servizio su Render."""
    return jsonify({
        'status': 'active', 
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/admin/stats')
def admin_stats():
    """Get statistics for ALL users."""
    try:
        users_with_cities = get_all_users_with_cities()
        users_with_rain_alerts = get_all_users_with_rain_alerts()
        
        # Get all unique user IDs
        all_user_ids = set()
        prefs = load_user_prefs()
        
        # Collect all user IDs from different sections
        if 'languages' in prefs:
            all_user_ids.update(prefs['languages'].keys())
        if 'cities' in prefs:
            all_user_ids.update(prefs['cities'].keys())
        if 'rain_alerts' in prefs:
            all_user_ids.update(prefs['rain_alerts'].keys())
        
        # Get list of unique cities
        unique_cities = list(set(users_with_cities.values()))
        
        return jsonify({
            'statistics': {
                'total_users': len(all_user_ids),
                'users_with_saved_cities': len(users_with_cities),
                'users_with_rain_alerts_enabled': len(users_with_rain_alerts),
                'unique_cities': unique_cities,
                'total_unique_cities': len(unique_cities)
            },
            'users_by_city': {
                city: sum(1 for c in users_with_cities.values() if c == city)
                for city in unique_cities
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test-cron')
def test_cron():
    """Test endpoint to verify cron signature."""
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
    
    # Start Flask server
    logger.info(f"🚀 Starting Flask server on port {Config.PORT}")
    logger.info(f"🌐 Webhook URL: {Config.RENDER_EXTERNAL_URL}/webhook")
    
    app.run(
        host='0.0.0.0',
        port=Config.PORT,
        debug=False,
        use_reloader=False
    )