"""
Webhook Flask server per Render deployment - Versione Aggiornata
Compatibile con le modifiche fatte alla versione locale
"""

import os
import logging
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
import requests
import pytz
from threading import Lock
import hashlib
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========== CONFIGURATION ==========
class Config:
    # Check if running on Render
    IS_RENDER = os.environ.get('RENDER', '').lower() == 'true'
    
    # Load from environment variables
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    PORT = int(os.environ.get('PORT', 10000))
    RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')
    CRON_SECRET = os.getenv('CRON_SECRET', '79bed7eab2dc420069685af5cc24908a399ff47ed45c23ec1b9688311dcc81e1')
    ADMIN_USER_ID = os.getenv('ADMIN_USER_ID', '')
    TIMEZONE = 'Europe/Rome'
    
    @classmethod
    def validate(cls):
        """Validate configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("❌ ERROR: BOT_TOKEN is required. Please set it in Render environment variables.")
        logger.info(f"✅ Configuration loaded: BOT_TOKEN length = {len(cls.BOT_TOKEN)}")
        return True

# Validate configuration immediately
try:
    Config.validate()
except ValueError as e:
    logger.error(str(e))

# ========== DATABASE FUNCTIONS (compatibili con bot_core.py) ==========
DB_PATH = 'users.db'
DB_LOCK = Lock()

def init_database():
    """Initialize database tables."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                language TEXT DEFAULT 'en',
                city TEXT,
                rain_alerts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Rain alerts log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rain_alerts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                city TEXT,
                alert_time TIMESTAMP,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")

def get_user_language(user_id):
    """Get user's preferred language."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT language FROM users WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 'en'
    except Exception as e:
        logger.error(f"Error getting user language: {e}")
        return 'en'

def set_user_language(user_id, lang):
    """Set user's language preference."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (str(user_id),))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing user
            cursor.execute('''
                UPDATE users 
                SET language = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (lang, str(user_id)))
        else:
            # Create new user
            cursor.execute('''
                INSERT INTO users (user_id, language)
                VALUES (?, ?)
            ''', (str(user_id), lang))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error setting user language: {e}")
        return False

def get_user_city(user_id):
    """Get user's saved city."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT city FROM users WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting user city: {e}")
        return None

def save_user_city(user_id, city):
    """Save user's city."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (str(user_id),))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing user
            cursor.execute('''
                UPDATE users 
                SET city = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (city, str(user_id)))
        else:
            # Create new user
            cursor.execute('''
                INSERT INTO users (user_id, city)
                VALUES (?, ?)
            ''', (str(user_id), city))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving user city: {e}")
        return False

def get_rain_alerts_status(user_id):
    """Get user's rain alerts status."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT rain_alerts FROM users WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()
        conn.close()
        return bool(result[0]) if result else False
    except Exception as e:
        logger.error(f"Error getting rain alerts status: {e}")
        return False

def set_rain_alerts_status(user_id, status):
    """Set user's rain alerts status."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (str(user_id),))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing user
            cursor.execute('''
                UPDATE users 
                SET rain_alerts = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (1 if status else 0, str(user_id)))
        else:
            # Create new user
            cursor.execute('''
                INSERT INTO users (user_id, rain_alerts)
                VALUES (?, ?)
            ''', (str(user_id), 1 if status else 0))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error setting rain alerts status: {e}")
        return False

def get_all_users_with_cities():
    """Get all users with saved cities."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, city FROM users WHERE city IS NOT NULL AND city != ""')
        users = cursor.fetchall()
        conn.close()
        return {str(user[0]): user[1] for user in users}
    except Exception as e:
        logger.error(f"Error getting users with cities: {e}")
        return {}

def get_all_users_with_rain_alerts():
    """Get all users with rain alerts enabled."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE rain_alerts = 1 AND city IS NOT NULL AND city != ""')
        users = cursor.fetchall()
        conn.close()
        return {str(user[0]): True for user in users}
    except Exception as e:
        logger.error(f"Error getting users with rain alerts: {e}")
        return {}

# ========== WEATHER SERVICE IMPORT ==========
try:
    from weather_service import (
        get_complete_weather_report,
        get_detailed_rain_forecast
    )
    logger.info("✅ Weather service imported successfully")
except ImportError as e:
    logger.error(f"❌ Cannot import weather_service: {e}")
    
    # Fallback functions
    def get_complete_weather_report(city, lang):
        return {'success': False, 'message': f"Weather service not available: {city}"}
    
    def get_detailed_rain_forecast(city, lang):
        return {'success': False, 'message': f"Rain forecast not available: {city}"}

# ========== CRON JOB FUNCTIONS ==========
def run_check_rain_alerts():
    """Run rain alerts check."""
    try:
        # Import here to avoid circular imports
        from check_rain_alerts import check_and_send_rain_alerts
        logger.info("🌧️ Starting rain alerts check from webhook...")
        check_and_send_rain_alerts()
        return True
    except Exception as e:
        logger.error(f"❌ Error in rain alerts check: {e}")
        return False

def run_send_morning_reports():
    """Send morning reports."""
    try:
        # Import here to avoid circular imports
        from send_morning_report import send_morning_reports
        logger.info("🌅 Starting morning reports from webhook...")
        send_morning_reports()
        return True
    except Exception as e:
        logger.error(f"❌ Error in morning reports: {e}")
        return False

# ========== TELEGRAM WEBHOOK HANDLER ==========
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Handle Telegram webhook."""
    
    if request.method == 'GET':
        return "✅ Webhook endpoint active!", 200
    
    # Verify webhook secret
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if Config.WEBHOOK_SECRET and secret_token != Config.WEBHOOK_SECRET:
        logger.warning(f"Invalid webhook secret: {secret_token}")
        return 'Unauthorized', 403
    
    try:
        update = request.get_json()
        
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            text = update['message'].get('text', '').strip()
            
            logger.info(f"Message from {chat_id}: {text}")
            
            lang = get_user_language(chat_id)
            
            # Handle commands
            if text == '/start':
                if lang == 'en':
                    welcome = """Hello! I'm your Weather Bot 🌤️

Send me a city name or use these commands:
/weather <city> - Get full forecast (current, 24h, 5-day)
/rain <city> - Get rain forecast
/save <city> - Save your preferred city
/myweather - Get forecast for saved city
/rainalerts - Toggle rain notifications
/myalerts - Check your rain alerts status
/language - Change language

Try sending: Rome"""
                else:
                    welcome = """Ciao! Sono il tuo Bot Meteo 🌤️

Inviami un nome di città o usa questi comandi:
/meteo <città> - Previsioni complete (attuali, 24h, 5 giorni)
/pioggia <città> - Previsioni pioggia
/salva <città> - Salva la tua città preferita
/miometeo - Previsioni per città salvata
/avvisipioggia - Attiva notifiche pioggia
/mieiavvisi - Controlla i tuoi avvisi pioggia
/lingua - Cambia lingua

Prova a inviare: Roma"""
                
                send_message(chat_id, welcome)
                
            elif text in ['/language', '/lingua']:
                keyboard = {
                    'keyboard': [[{'text': '🇬🇧 English'}, {'text': '🇮🇹 Italiano'}]],
                    'resize_keyboard': True,
                    'one_time_keyboard': True
                }
                send_message(chat_id, "Choose language / Scegli lingua:", keyboard)
                
            elif text in ['🇬🇧 English', '🇮🇹 Italiano']:
                if 'Italiano' in text:
                    set_user_language(chat_id, 'it')
                    send_message(chat_id, "✅ Lingua impostata su Italiano!")
                else:
                    set_user_language(chat_id, 'en')
                    send_message(chat_id, "✅ Language set to English!")
                    
            elif text.startswith(('/weather ', '/meteo ')):
                if ' ' in text:
                    city = text.split(' ', 1)[1]
                    result = get_complete_weather_report(city, lang)
                    send_message(chat_id, result['message'])
                    
                    # Ask to save
                    if result['success'] and not get_user_city(chat_id):
                        if lang == 'en':
                            prompt = f"\n💡 Save '{city}' as your default city? Use /save {city}"
                        else:
                            prompt = f"\n💡 Salvare '{city}' come tua città predefinita? Usa /salva {city}"
                        send_message(chat_id, prompt)
                else:
                    if lang == 'en':
                        send_message(chat_id, "Please specify a city. Example: /weather Rome")
                    else:
                        send_message(chat_id, "Specifica una città. Esempio: /meteo Roma")
            
            elif text.startswith(('/rain ', '/pioggia ')):
                if ' ' in text:
                    city = text.split(' ', 1)[1]
                    result = get_detailed_rain_forecast(city, lang)
                    if result['success']:
                        send_message(chat_id, result['message'])
                    else:
                        if lang == 'en':
                            send_message(chat_id, f"❌ Could not get rain data for {city}")
                        else:
                            send_message(chat_id, f"❌ Impossibile ottenere dati pioggia per {city}")
                    
                    # Ask to save
                    if result['success'] and not get_user_city(chat_id):
                        if lang == 'en':
                            prompt = f"\n💡 Save '{city}' as your default city? Use /save {city}"
                        else:
                            prompt = f"\n💡 Salvare '{city}' come tua città predefinita? Usa /salva {city}"
                        send_message(chat_id, prompt)
                else:
                    if lang == 'en':
                        send_message(chat_id, "Please specify a city. Example: /rain Rome")
                    else:
                        send_message(chat_id, "Specifica una città. Esempio: /pioggia Roma")
                    
            elif text.startswith(('/save ', '/salva ')):
                if ' ' in text:
                    city = text.split(' ', 1)[1]
                    save_user_city(chat_id, city)
                    if lang == 'en':
                        send_message(chat_id, f"✅ City '{city}' saved!\n\nNow use:\n/myweather - Get forecast\n/rainalerts - Enable rain alerts\n/myalerts - Check alerts status")
                    else:
                        send_message(chat_id, f"✅ Città '{city}' salvata!\n\nOra usa:\n/miometeo - Previsioni\n/avvisipioggia - Attiva avvisi pioggia\n/mieiavvisi - Controlla avvisi")
                else:
                    if lang == 'en':
                        send_message(chat_id, "Please specify a city. Example: /save Rome")
                    else:
                        send_message(chat_id, "Specifica una città. Esempio: /salva Roma")
                    
            elif text in ['/myweather', '/miometeo']:
                city = get_user_city(chat_id)
                if city:
                    result = get_complete_weather_report(city, lang)
                    send_message(chat_id, result['message'])
                else:
                    if lang == 'en':
                        send_message(chat_id, "❌ No city saved. Use /save <city> first.")
                    else:
                        send_message(chat_id, "❌ Nessuna città salvata. Usa prima /salva <città>.")
                        
            elif text in ['/myrain', '/miapioggia']:
                city = get_user_city(chat_id)
                if city:
                    result = get_detailed_rain_forecast(city, lang)
                    if result['success']:
                        send_message(chat_id, result['message'])
                    else:
                        if lang == 'en':
                            send_message(chat_id, f"❌ Could not get rain data for {city}")
                        else:
                            send_message(chat_id, f"❌ Impossibile ottenere dati pioggia per {city}")
                else:
                    if lang == 'en':
                        send_message(chat_id, "❌ No city saved. Use /save <city> first.")
                    else:
                        send_message(chat_id, "❌ Nessuna città salvata. Usa prima /salva <città>.")
            
            elif text in ['/rainalerts', '/avvisipioggia']:
                saved_city = get_user_city(chat_id)
                if not saved_city:
                    if lang == 'en':
                        send_message(chat_id, "❌ No city saved. Use /save <city> first.")
                    else:
                        send_message(chat_id, "❌ Nessuna città salvata. Usa prima /salva <città>.")
                    return
                
                current = get_rain_alerts_status(chat_id)
                new_status = not current
                set_rain_alerts_status(chat_id, new_status)
                
                if new_status:
                    if lang == 'en':
                        message = f"✅ Rain alerts ACTIVATED for {saved_city}!\n\n"
                        message += "You'll receive alerts when rain is expected.\n"
                        message += "• Active: 24/7\n"
                        message += "• Cooldown: 6 hours between alerts\n"
                        message += "• Data: Saved in database ✅\n\n"
                        message += "Use /myalerts to check status"
                    else:
                        message = f"✅ Avvisi pioggia ATTIVATI per {saved_city}!\n\n"
                        message += "Riceverai avvisi quando è prevista pioggia.\n"
                        message += "• Attivi: 24/7\n"
                        message += "• Pausa: 6 ore tra gli avvisi\n"
                        message += "• Dati: Salvati su database ✅\n\n"
                        message += "Usa /mieiavvisi per controllare lo stato"
                else:
                    if lang == 'en':
                        message = "❌ Rain alerts DEACTIVATED."
                    else:
                        message = "❌ Avvisi pioggia DISATTIVATI."
                
                send_message(chat_id, message)
            
            elif text in ['/myalerts', '/mieiavvisi']:
                alerts_enabled = get_rain_alerts_status(chat_id)
                city = get_user_city(chat_id)
                
                if lang == 'en':
                    message = "🔔 *Your Rain Alerts Status*\n\n"
                    if alerts_enabled and city:
                        message += f"✅ **ACTIVE** for {city}\n"
                        message += "You'll receive alerts when rain is expected.\n\n"
                    elif city:
                        message += f"❌ **INACTIVE** for {city}\n\n"
                        message += "Enable alerts with /rainalerts"
                    else:
                        message += "❌ No city saved\n\n"
                        message += "Save a city first with /save <city>"
                else:
                    message = "🔔 *Stato Avvisi Pioggia*\n\n"
                    if alerts_enabled and city:
                        message += f"✅ **ATTIVI** per {city}\n"
                        message += "Riceverai avvisi quando è prevista pioggia.\n\n"
                    elif city:
                        message += f"❌ **DISATTIVI** per {city}\n\n"
                        message += "Attiva gli avvisi con /avvisipioggia"
                    else:
                        message += "❌ Nessuna città salvata\n\n"
                        message += "Salva prima una città con /salva <città>"
                
                send_message(chat_id, message)
            
            elif text in ['/help', '/aiuto']:
                if lang == 'en':
                    help_text = """🌤️ **Weather Bot Help**

**Commands:**
/weather <city> - Get full forecast (current, 24h, 5-day)
/rain <city> - Get rain forecast
/save <city> - Save city  
/myweather - Forecast for saved city
/myrain - Rain forecast for saved city
/rainalerts - Toggle rain notifications
/myalerts - Check rain alerts status
/language - Change language

**Tips:**
• Data is saved in database (won't be lost!)
• Rain alerts have 6-hour cooldown
• Alerts are active 24/7
• Just send a city name for quick forecast!"""
                else:
                    help_text = """🌤️ **Aiuto Bot Meteo**

**Comandi:**
/meteo <città> - Previsioni complete (attuali, 24h, 5 giorni)
/pioggia <città> - Previsioni pioggia
/salva <città> - Salva città
/miometeo - Previsioni città salvata
/miapioggia - Previsioni pioggia città salvata
/avvisipioggia - Attiva notifiche pioggia
/mieiavvisi - Controlla avvisi pioggia
/lingua - Cambia lingua

**Consigli:**
• I dati sono salvati su database (non si perdono!)
• Avvisi pioggia hanno pausa di 6 ore
• Avvisi attivi 24/7
• Invia solo un nome di città per previsioni rapide!"""
                send_message(chat_id, help_text)
                
            else:
                # Assume it's a city name (not a command)
                if text and len(text) < 50 and not text.startswith('/'):
                    result = get_complete_weather_report(text, lang)
                    send_message(chat_id, result['message'])
                    
                    if result['success'] and not get_user_city(chat_id):
                        if lang == 'en':
                            prompt = f"\n💡 Save '{text}' as your city? Use /save {text}"
                        else:
                            prompt = f"\n💡 Salvare '{text}' come tua città? Usa /salva {text}"
                        send_message(chat_id, prompt)
                elif text:
                    if lang == 'en':
                        send_message(chat_id, "Send me a city name (e.g. 'Rome') or use /help")
                    else:
                        send_message(chat_id, "Inviami un nome di città (es. 'Roma') o usa /aiuto")
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return 'OK', 200

def send_message(chat_id, text, reply_markup=None):
    """Send message to Telegram."""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        if reply_markup:
            data['reply_markup'] = reply_markup
        
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return None

# ========== CRON JOB ENDPOINTS ==========
def verify_cron_signature(request):
    """Verify cron job signature."""
    received_signature = request.headers.get('X-Cron-Signature')
    if not received_signature:
        return False
    
    # Il segreto è hardcoded come richiesto
    expected_signature = "79bed7eab2dc420069685af5cc24908a399ff47ed45c23ec1b9688311dcc81e1"
    
    # Compare directly since we're using hardcoded secret
    return received_signature == expected_signature

@app.route('/trigger-rain-check', methods=['POST'])
def trigger_rain_check():
    """Endpoint for rain alerts cron job."""
    if not verify_cron_signature(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    logger.info("🌧️ Triggering rain check via cron job")
    
    try:
        # Run rain check synchronously
        success = run_check_rain_alerts()
        if success:
            return jsonify({'status': 'success', 'message': 'Rain check completed'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Rain check failed'}), 500
    except Exception as e:
        logger.error(f"Error in rain check: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/trigger-morning-reports', methods=['POST'])
def trigger_morning_reports():
    """Endpoint for morning reports cron job."""
    if not verify_cron_signature(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    logger.info("🌅 Triggering morning reports via cron job")
    
    try:
        # Run morning reports synchronously
        success = run_send_morning_reports()
        if success:
            return jsonify({'status': 'success', 'message': 'Morning reports sent'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Morning reports failed'}), 500
    except Exception as e:
        logger.error(f"Error in morning reports: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ========== DEBUG & DIAGNOSTICS ENDPOINTS ==========
@app.route('/debug/database-stats', methods=['GET'])
def debug_database_stats():
    """Debug endpoint to check database statistics (no personal data)."""
    try:
        # Get stats
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE city IS NOT NULL AND city != ""')
        users_with_cities = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE rain_alerts = 1')
        users_with_alerts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM rain_alerts_log')
        total_alerts = cursor.fetchone()[0]
        
        # Get city distribution (anonymized)
        cursor.execute('''
            SELECT city, COUNT(*) as user_count 
            FROM users 
            WHERE city IS NOT NULL AND city != ""
            GROUP BY city 
            ORDER BY user_count DESC
        ''')
        city_distribution = cursor.fetchall()
        
        # Get languages distribution
        cursor.execute('SELECT language, COUNT(*) FROM users GROUP BY language')
        language_distribution = cursor.fetchall()
        
        # Get recent activity (anonymized)
        cursor.execute('''
            SELECT COUNT(*) as recent_users 
            FROM users 
            WHERE datetime(updated_at) > datetime('now', '-1 day')
        ''')
        recent_users = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'database': {
                'total_users': total_users,
                'users_with_saved_cities': users_with_cities,
                'users_with_rain_alerts': users_with_alerts,
                'total_rain_alerts_sent': total_alerts,
                'recently_active_users': recent_users
            },
            'city_distribution': [
                {'city': city, 'users': count} 
                for city, count in city_distribution
            ],
            'languages': {
                lang: count for lang, count in language_distribution
            },
            'privacy_note': 'No personal user data exposed'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/weather-test/<city>', methods=['GET'])
def debug_weather_test(city):
    """Test weather service for any city."""
    try:
        from weather_service import get_complete_weather_report
        
        result = get_complete_weather_report(city, 'en')
        
        return jsonify({
            'city': city,
            'weather_service_ok': result['success'],
            'message_preview': result['message'][:200] if result['success'] else result['message'],
            'note': 'Test weather data only'
        })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/system-health', methods=['GET'])
def system_health():
    """Comprehensive system health check."""
    try:
        # Database health
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE city IS NOT NULL AND city != ""')
        users_with_cities = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE rain_alerts = 1')
        users_with_alerts = cursor.fetchone()[0]
        
        conn.close()
        
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        
        # Weather service health
        from weather_service import get_coordinates
        lat, lon, region = get_coordinates("Rome")
        weather_service_ok = lat is not None
        
        # Current time
        rome_tz = pytz.timezone('Europe/Rome')
        current_time = datetime.now(rome_tz)
        
        return jsonify({
            'status': 'healthy',
            'timestamp': current_time.isoformat(),
            'timezone': 'Europe/Rome',
            'current_time': current_time.strftime('%H:%M %d/%m/%Y'),
            
            'database': {
                'exists': os.path.exists(DB_PATH),
                'size_bytes': db_size,
                'total_users': total_users,
                'users_with_cities': users_with_cities,
                'users_with_rain_alerts': users_with_alerts
            },
            
            'services': {
                'weather_api': weather_service_ok,
                'telegram_bot': bool(Config.BOT_TOKEN),
                'webhook_active': Config.IS_RENDER
            },
            
            'cron_jobs': {
                'rain_alerts': {
                    'endpoint': '/trigger-rain-check',
                    'method': 'POST',
                    'frequency': 'every 30 minutes',
                    'active': True
                },
                'morning_reports': {
                    'endpoint': '/trigger-morning-reports',
                    'method': 'POST',
                    'frequency': 'daily at 8:00 AM',
                    'active': True
                }
            },
            
            'features': {
                'rain_alerts_24_7': True,
                'morning_reports': True,
                'multi_language': True,
                'persistent_database': True,
                'complete_weather_format': True
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== HEALTH ENDPOINTS ==========
@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>🌤️ Weather Bot</title>
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
            <h1>🌤️ Weather Bot</h1>
            <p class="status">✅ Service is running on Render!</p>
            <p>Telegram weather bot with persistent database storage.</p>
            
            <div class="endpoint">
                <h3>📊 Bot Status</h3>
                <p><strong>Health Check:</strong> <a href="/health">/health</a></p>
                <p><strong>Database Stats:</strong> <a href="/debug/database-stats">/debug/database-stats</a></p>
                <p><strong>System Health:</strong> <a href="/debug/system-health">/debug/system-health</a></p>
                <p><strong>Ping:</strong> <a href="/ping">/ping</a></p>
            </div>
            
            <div class="endpoint">
                <h3>🔧 Features</h3>
                <p><strong>✓ Complete forecast (current + 24h + 5 days)</strong></p>
                <p><strong>✓ Rain alerts active 24/7</strong></p>
                <p><strong>✓ Morning reports at 8:00 AM</strong></p>
                <p><strong>✓ Persistent database</strong></p>
                <p><strong>✓ Multi-language (EN/IT)</strong></p>
                <p><strong>✓ Secure cron jobs with signature</strong></p>
            </div>
            
            <hr>
            <p><small>Powered by Open-Meteo API | Running on Render | Database: SQLite | Version: 2.0</small></p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE city IS NOT NULL AND city != ""')
        users_with_cities = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE rain_alerts = 1')
        users_with_alerts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM rain_alerts_log')
        total_alerts = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'service': 'telegram-weather-bot',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'total_users': total_users,
                'users_with_cities': users_with_cities,
                'users_with_rain_alerts': users_with_alerts,
                'total_rain_alerts_sent': total_alerts
            },
            'bot_token_configured': bool(Config.BOT_TOKEN),
            'rain_alerts_active': '24/7',
            'cron_jobs': 'active'
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/ping')
def ping():
    return jsonify({'status': 'pong', 'timestamp': datetime.now().isoformat()}), 200

# ========== START SERVER ==========
if __name__ == '__main__':
    # Initialize database
    init_database()
    
    if not Config.BOT_TOKEN:
        logger.error("❌ CRITICAL ERROR: BOT_TOKEN is not set!")
        @app.route('/')
        def error_home():
            return """
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h1>❌ Configuration Error</h1>
                <p>BOT_TOKEN is not set in environment variables.</p>
            </body>
            </html>
            """
    else:
        logger.info(f"✅ BOT_TOKEN is set (length: {len(Config.BOT_TOKEN)})")
        logger.info(f"🚀 Starting server on port {Config.PORT}")
        logger.info(f"💾 Database initialized: users.db")
        logger.info(f"🌧️ Rain alerts active 24/7")
        logger.info(f"⏰ Morning reports at 8:00 AM")
        logger.info(f"🌐 Webhook mode active")
        logger.info(f"🔒 Cron job signature configured")
    
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)