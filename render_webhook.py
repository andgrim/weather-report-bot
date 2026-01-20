import os
import logging
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
import requests
import pytz
from threading import Lock
import hashlib

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
    CRON_SECRET = os.getenv('CRON_SECRET', '')
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

# ========== DATABASE SETUP ==========
class UserDatabase:
    """SQLite database for persistent user data storage."""
    
    def __init__(self, db_path='users.db'):
        self.db_path = db_path
        self.lock = Lock()
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
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
    
    def get_user(self, user_id):
        """Get user data."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (str(user_id),))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                return {
                    'user_id': user[0],
                    'language': user[1],
                    'city': user[2],
                    'rain_alerts': bool(user[3]),
                    'created_at': user[4],
                    'updated_at': user[5]
                }
            return None
    
    def create_or_update_user(self, user_id, language='en', city=None, rain_alerts=False):
        """Create or update user data."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (str(user_id),))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing user
                cursor.execute('''
                    UPDATE users 
                    SET language = ?, city = ?, rain_alerts = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (language, city, 1 if rain_alerts else 0, str(user_id)))
            else:
                # Create new user
                cursor.execute('''
                    INSERT INTO users (user_id, language, city, rain_alerts)
                    VALUES (?, ?, ?, ?)
                ''', (str(user_id), language, city, 1 if rain_alerts else 0))
            
            conn.commit()
            conn.close()
            return True
    
    def set_user_language(self, user_id, language):
        """Set user language."""
        user = self.get_user(user_id)
        if user:
            return self.create_or_update_user(
                user_id, language, user.get('city'), user.get('rain_alerts', False)
            )
        else:
            return self.create_or_update_user(user_id, language)
    
    def set_user_city(self, user_id, city):
        """Set user city."""
        user = self.get_user(user_id)
        if user:
            return self.create_or_update_user(
                user_id, user.get('language', 'en'), city, user.get('rain_alerts', False)
            )
        else:
            return self.create_or_update_user(user_id, city=city)
    
    def set_rain_alerts(self, user_id, enabled):
        """Enable/disable rain alerts."""
        user = self.get_user(user_id)
        if user:
            return self.create_or_update_user(
                user_id, user.get('language', 'en'), user.get('city'), enabled
            )
        else:
            return self.create_or_update_user(user_id, rain_alerts=enabled)
    
    def log_rain_alert(self, user_id, city):
        """Log a rain alert sent to user."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO rain_alerts_log (user_id, city, alert_time)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (str(user_id), city))
            conn.commit()
            conn.close()
            return True
    
    def get_recent_rain_alerts(self, user_id, hours=24):
        """Get recent rain alerts for a user."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT city, alert_time, sent_at
                FROM rain_alerts_log 
                WHERE user_id = ? 
                AND datetime(sent_at) > datetime('now', ?)
                ORDER BY sent_at DESC
            ''', (str(user_id), f'-{hours} hours'))
            alerts = cursor.fetchall()
            conn.close()
            
            return [
                {'city': a[0], 'alert_time': a[1], 'sent_at': a[2]}
                for a in alerts
            ]
    
    def should_send_rain_alert(self, user_id, cooldown_hours=6):
        """Check if we should send rain alert (cooldown)."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sent_at 
                FROM rain_alerts_log 
                WHERE user_id = ? 
                ORDER BY sent_at DESC 
                LIMIT 1
            ''', (str(user_id),))
            last_alert = cursor.fetchone()
            conn.close()
            
            if not last_alert:
                return True
            
            # Calculate hours since last alert
            last_time = datetime.fromisoformat(last_alert[0].replace('Z', '+00:00'))
            hours_since = (datetime.utcnow() - last_time).total_seconds() / 3600
            
            return hours_since >= cooldown_hours
    
    def get_all_users_with_cities(self):
        """Get all users with saved cities."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, city FROM users WHERE city IS NOT NULL')
            users = cursor.fetchall()
            conn.close()
            
            return {str(user[0]): user[1] for user in users}
    
    def get_all_users_with_rain_alerts(self):
        """Get all users with rain alerts enabled."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE rain_alerts = 1 AND city IS NOT NULL')
            users = cursor.fetchall()
            conn.close()
            
            return {str(user[0]): True for user in users}
    
    def get_stats(self):
        """Get database statistics."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM users WHERE city IS NOT NULL')
            users_with_cities = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM users WHERE rain_alerts = 1')
            users_with_alerts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM rain_alerts_log')
            total_alerts = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_users': total_users,
                'users_with_cities': users_with_cities,
                'users_with_rain_alerts': users_with_alerts,
                'total_rain_alerts_sent': total_alerts
            }

# Initialize database
db = UserDatabase()

# ========== USER PREFERENCES FUNCTIONS ==========
def get_user_language(user_id):
    user = db.get_user(str(user_id))
    return user.get('language', 'en') if user else 'en'

def set_user_language(user_id, lang):
    return db.set_user_language(str(user_id), lang)

def get_user_city(user_id):
    user = db.get_user(str(user_id))
    return user.get('city') if user else None

def save_user_city(user_id, city):
    return db.set_user_city(str(user_id), city)

def get_rain_alerts_status(user_id):
    user = db.get_user(str(user_id))
    return user.get('rain_alerts', False) if user else False

def set_rain_alerts_status(user_id, status):
    return db.set_rain_alerts(str(user_id), status)

def get_all_users_with_cities():
    return db.get_all_users_with_cities()

def get_all_users_with_rain_alerts():
    return db.get_all_users_with_rain_alerts()

def should_send_rain_alert(user_id):
    return db.should_send_rain_alert(str(user_id), cooldown_hours=6)

def log_rain_alert_sent(user_id, city):
    return db.log_rain_alert(str(user_id), city)

# ========== WEATHER SERVICE IMPORT ==========
try:
    from weather_service import (
        get_complete_weather_report,
        get_detailed_rain_forecast
    )
except ImportError:
    logger.error("❌ Cannot import weather_service. Make sure weather_service.py exists.")
    
    def get_complete_weather_report(city, lang):
        return {'success': False, 'message': "Weather service not available"}
    
    def get_detailed_rain_forecast(city, lang):
        return {'success': False, 'message': "Rain forecast not available"}

# ========== TELEGRAM WEBHOOK HANDLER ==========
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Handle Telegram webhook."""
    
    if request.method == 'GET':
        return "✅ Webhook endpoint active!", 200
    
    # Verify webhook secret
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if Config.WEBHOOK_SECRET and secret_token != Config.WEBHOOK_SECRET:
        logger.warning("Invalid webhook secret")
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
                        
            elif text in ['/help', '/aiuto']:
                if lang == 'en':
                    help_text = """🌤️ **Weather Bot Help**

**Commands:**
/weather <city> - Get full forecast (current, 24h, 5-day)
/rain <city> - Get rain forecast
/save <city> - Save city  
/myweather - Forecast for saved city
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
/avvisipioggia - Attiva notifiche pioggia
/mieiavvisi - Controlla avvisi pioggia
/lingua - Cambia lingua

**Consigli:**
• I dati sono salvati su database (non si perdono!)
• Avvisi pioggia hanno pausa di 6 ore
• Avvisi attivi 24/7
• Invia solo un nome di città per previsioni rapide!"""
                send_message(chat_id, help_text)
                
            elif text in ['/myalerts', '/mieiavvisi']:
                alerts_enabled = get_rain_alerts_status(chat_id)
                city = get_user_city(chat_id)
                
                if lang == 'en':
                    message = "🔔 *Your Rain Alerts Status*\n\n"
                    if alerts_enabled and city:
                        message += f"✅ **ACTIVE** for {city}\n"
                        message += "You'll receive alerts when rain is expected.\n\n"
                        
                        recent_alerts = db.get_recent_rain_alerts(str(chat_id), hours=24)
                        if recent_alerts:
                            message += "*Recent alerts:*\n"
                            for alert in recent_alerts[:5]:
                                alert_time = datetime.fromisoformat(alert['sent_at'].replace('Z', '+00:00'))
                                message += f"• {alert_time.strftime('%H:%M')} - {alert['city']}\n"
                        else:
                            message += "*Recent alerts:* None in last 24h\n"
                        
                        message += f"\n*Settings:*\n• Cooldown: 6 hours\n• Data: Saved in database ✅"
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
                        
                        recent_alerts = db.get_recent_rain_alerts(str(chat_id), hours=24)
                        if recent_alerts:
                            message += "*Avvisi recenti:*\n"
                            for alert in recent_alerts[:5]:
                                alert_time = datetime.fromisoformat(alert['sent_at'].replace('Z', '+00:00'))
                                message += f"• {alert_time.strftime('%H:%M')} - {alert['city']}\n"
                        else:
                            message += "*Avvisi recenti:* Nessuno nelle ultime 24h\n"
                        
                        message += f"\n*Impostazioni:*\n• Pausa: 6 ore\n• Dati: Salvati su database ✅"
                    elif city:
                        message += f"❌ **DISATTIVI** per {city}\n\n"
                        message += "Attiva gli avvisi con /avvisipioggia"
                    else:
                        message += "❌ Nessuna città salvata\n\n"
                        message += "Salva prima una città con /salva <città>"
                
                send_message(chat_id, message)
                
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
    
    # Import and run rain check
    try:
        from check_rain_alerts import check_and_send_rain_alerts
        check_and_send_rain_alerts()
        return jsonify({'status': 'success', 'message': 'Rain check completed'}), 200
    except Exception as e:
        logger.error(f"Error in rain check: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/trigger-morning-reports', methods=['POST'])
def trigger_morning_reports():
    """Endpoint for morning reports cron job."""
    if not verify_cron_signature(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    logger.info("🌅 Triggering morning reports via cron job")
    
    # Import and run morning reports
    try:
        from send_morning_report import send_morning_reports
        send_morning_reports()
        return jsonify({'status': 'success', 'message': 'Morning reports sent'}), 200
    except Exception as e:
        logger.error(f"Error in morning reports: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ========== DEBUG & DIAGNOSTICS ENDPOINTS ==========
@app.route('/debug/database-stats', methods=['GET'])
def debug_database_stats():
    """Debug endpoint to check database statistics (no personal data)."""
    try:
        stats = db.get_stats()
        
        # Get anonymized data
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Get city distribution (anonymized)
        cursor.execute('''
            SELECT city, COUNT(*) as user_count 
            FROM users 
            WHERE city IS NOT NULL 
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
                'total_users': stats['total_users'],
                'users_with_saved_cities': stats['users_with_cities'],
                'users_with_rain_alerts': stats['users_with_rain_alerts'],
                'total_rain_alerts_sent': stats['total_rain_alerts_sent'],
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
        
        # Also check rain forecast
        from weather_service import get_detailed_rain_alert, get_coordinates, get_weather_forecast
        
        lat, lon, region = get_coordinates(city)
        if lat:
            weather_data = get_weather_forecast(lat, lon)
            hourly = weather_data.get('hourly', {}) if weather_data else {}
            rain_events = get_detailed_rain_alert(hourly, 'en')
            
            return jsonify({
                'city': city,
                'coordinates': {'lat': lat, 'lon': lon, 'region': region},
                'weather_service_ok': result['success'],
                'rain_events_count': len(rain_events) if rain_events else 0,
                'rain_events_next_24h': [
                    {
                        'time': event['time'].strftime('%H:%M'),
                        'precipitation': event['precipitation'],
                        'intensity': event['intensity']
                    }
                    for event in (rain_events[:3] if rain_events else [])
                ],
                'note': 'Test weather data only'
            })
        else:
            return jsonify({'error': 'Could not get coordinates'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/system-health', methods=['GET'])
def system_health():
    """Comprehensive system health check."""
    try:
        # Database health
        stats = db.get_stats()
        db_size = os.path.getsize('users.db') if os.path.exists('users.db') else 0
        
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
                'exists': os.path.exists('users.db'),
                'size_bytes': db_size,
                'total_users': stats['total_users'],
                'users_with_cities': stats['users_with_cities'],
                'users_with_rain_alerts': stats['users_with_rain_alerts']
            },
            
            'services': {
                'weather_api': weather_service_ok,
                'telegram_bot': bool(Config.BOT_TOKEN),
                'webhook_active': Config.WEBHOOK_MODE
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

@app.route('/debug/test-cron-interface', methods=['GET'])
def test_cron_interface():
    """HTML interface to test cron jobs (for development only)."""
    return '''
    <html>
    <head>
        <title>Cron Job Tester</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }
            .card { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 10px; }
            button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
            button:hover { background: #0056b3; }
            .result { margin-top: 10px; padding: 10px; background: white; border-radius: 5px; min-height: 100px; }
            .code { background: #333; color: #fff; padding: 10px; border-radius: 5px; font-family: monospace; }
        </style>
    </head>
    <body>
        <h1>Cron Job Test Interface</h1>
        <p><em>For development and testing purposes only</em></p>
        
        <div class="card">
            <h3>Test Rain Alerts</h3>
            <p>Manually trigger rain alerts check:</p>
            <button onclick="testEndpoint('rain-check')">Test Rain Check</button>
            <div id="rain-result" class="result"></div>
        </div>
        
        <div class="card">
            <h3>Test Morning Reports</h3>
            <p>Manually trigger morning reports:</p>
            <button onclick="testEndpoint('morning-reports')">Test Morning Reports</button>
            <div id="morning-result" class="result"></div>
        </div>
        
        <div class="card">
            <h3>cURL Commands</h3>
            <p>Use these commands to test from terminal:</p>
            <div class="code">
                # Test rain alerts<br>
                curl -X POST https://weather-report-bot-1.onrender.com/trigger-rain-check \<br>
                  -H "X-Cron-Signature: 79bed7eab2dc420069685af5cc24908a399ff47ed45c23ec1b9688311dcc81e1"<br><br>
                
                # Test morning reports<br>
                curl -X POST https://weather-report-bot-1.onrender.com/trigger-morning-reports \<br>
                  -H "X-Cron-Signature: 79bed7eab2dc420069685af5cc24908a399ff47ed45c23ec1b9688311dcc81e1"
            </div>
        </div>
        
        <script>
            async function testEndpoint(type) {
                const endpoint = type === 'rain-check' 
                    ? '/trigger-rain-check' 
                    : '/trigger-morning-reports';
                
                const resultDiv = type === 'rain-check' 
                    ? document.getElementById('rain-result') 
                    : document.getElementById('morning-result');
                
                resultDiv.innerHTML = 'Testing...';
                
                try {
                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: {
                            'X-Cron-Signature': '79bed7eab2dc420069685af5cc24908a399ff47ed45c23ec1b9688311dcc81e1'
                        }
                    });
                    
                    const data = await response.json();
                    resultDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
                } catch (error) {
                    resultDiv.innerHTML = `Error: ${error.message}`;
                }
            }
        </script>
    </body>
    </html>
    '''

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
                <p><strong>Test Cron Jobs:</strong> <a href="/debug/test-cron-interface">/debug/test-cron-interface</a></p>
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
    stats = db.get_stats()
    return jsonify({
        'status': 'healthy',
        'service': 'telegram-weather-bot',
        'timestamp': datetime.now().isoformat(),
        'database': {
            'total_users': stats['total_users'],
            'users_with_cities': stats['users_with_cities'],
            'users_with_rain_alerts': stats['users_with_rain_alerts'],
            'total_rain_alerts_sent': stats['total_rain_alerts_sent']
        },
        'bot_token_configured': bool(Config.BOT_TOKEN),
        'rain_alerts_active': '24/7',
        'cron_jobs': 'active'
    }), 200

@app.route('/db-stats')
def db_stats():
    """Get database statistics."""
    try:
        stats = db.get_stats()
        
        # Get some sample data
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Get top 5 cities
        cursor.execute('''
            SELECT city, COUNT(*) as count 
            FROM users 
            WHERE city IS NOT NULL 
            GROUP BY city 
            ORDER BY count DESC 
            LIMIT 5
        ''')
        top_cities = cursor.fetchall()
        
        # Get recent alerts
        cursor.execute('''
            SELECT user_id, city, sent_at 
            FROM rain_alerts_log 
            ORDER BY sent_at DESC 
            LIMIT 10
        ''')
        recent_alerts = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'database_stats': stats,
            'top_cities': [{'city': city, 'users': count} for city, count in top_cities],
            'recent_alerts': [
                {
                    'user_id': alert[0], 
                    'city': alert[1], 
                    'sent_at': alert[2]
                } 
                for alert in recent_alerts
            ],
            'database_file': 'users.db',
            'file_size': os.path.getsize('users.db') if os.path.exists('users.db') else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ping')
def ping():
    return jsonify({'status': 'pong', 'timestamp': datetime.now().isoformat()}), 200

@app.route('/admin/stats')
def admin_stats():
    """Get statistics for ALL users."""
    try:
        stats = db.get_stats()
        
        # Get all cities
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT city FROM users WHERE city IS NOT NULL')
        cities = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Count by city
        from collections import Counter
        city_counts = Counter(cities)
        
        return jsonify({
            'statistics': stats,
            'cities_distribution': dict(city_counts),
            'unique_cities': len(set(cities))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== START SERVER ==========
if __name__ == '__main__':
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