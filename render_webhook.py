import os
import logging
import hmac
import hashlib
import threading
import time
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import requests
import pytz
from threading import Lock

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
    RAIN_ALERT_WINDOW_START = 7
    RAIN_ALERT_WINDOW_END = 22
    
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
            
            # Rain alerts log (per evitare duplicati)
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

# ========== USER PREFERENCES FUNCTIONS (USING DATABASE) ==========
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

# ========== WEATHER SERVICE (SIMPLIFIED) ==========
def get_coordinates(city_name):
    """Get coordinates for a city."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=it"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get('results'):
            loc = data['results'][0]
            return loc['latitude'], loc['longitude'], loc.get('admin1', '')
    except:
        pass
    return None, None, None

def get_weather_data(lat, lon):
    """Get weather data from Open-Meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'current': 'temperature_2m,apparent_temperature,wind_speed_10m,weather_code',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
        'hourly': 'precipitation,precipitation_probability,weather_code',
        'timezone': 'auto',
        'forecast_days': 5
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        return response.json()
    except:
        return None

def get_weather_icon(code):
    icons = {
        0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
        45: '🌫️', 48: '🌫️',
        51: '🌦️', 53: '🌦️', 55: '🌦️',
        61: '🌧️', 63: '🌧️', 65: '🌧️',
        71: '❄️', 73: '❄️', 75: '❄️',
        80: '🌦️', 81: '🌦️', 82: '🌦️',
        95: '⛈️', 96: '⛈️', 99: '⛈️'
    }
    return icons.get(code, '🌈')

def get_weather_description(code, lang):
    descriptions = {
        'en': {
            0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
            45: 'Fog', 48: 'Fog',
            51: 'Light drizzle', 53: 'Moderate drizzle', 55: 'Heavy drizzle',
            61: 'Light rain', 63: 'Moderate rain', 65: 'Heavy rain',
            71: 'Light snow', 73: 'Moderate snow', 75: 'Heavy snow',
            80: 'Light showers', 81: 'Moderate showers', 82: 'Heavy showers',
            95: 'Thunderstorm', 96: 'Thunderstorm with hail', 99: 'Heavy thunderstorm'
        },
        'it': {
            0: 'Cielo sereno', 1: 'Prevalentemente sereno', 2: 'Parzialmente nuvoloso', 3: 'Nuvoloso',
            45: 'Nebbia', 48: 'Nebbia',
            51: 'Pioviggine leggera', 53: 'Pioviggine moderata', 55: 'Pioviggine forte',
            61: 'Pioggia leggera', 63: 'Pioggia moderata', 65: 'Pioggia forte',
            71: 'Neve leggera', 73: 'Neve moderata', 75: 'Neve forte',
            80: 'Rovesci leggeri', 81: 'Rovesci moderati', 82: 'Rovesci forti',
            95: 'Temporale', 96: 'Temporale con grandine', 99: 'Temporale forte con grandine'
        }
    }
    return descriptions[lang].get(code, '')

def create_weather_message(city, region, weather_data, lang):
    """Create weather message from data."""
    if not weather_data:
        return "❌ Weather data not available" if lang == 'en' else "❌ Dati meteo non disponibili"
    
    current = weather_data.get('current', {})
    daily = weather_data.get('daily', {})
    
    # Build message
    icon = get_weather_icon(current.get('weather_code', 0))
    description = get_weather_description(current.get('weather_code', 0), lang)
    
    if lang == 'en':
        message = f"{icon} **Weather for {city}**\n"
        if region:
            message += f"*{region}*\n"
        message += "\n"
        message += f"**Current Conditions**\n"
        message += f"{description}\n"
        message += f"• Temperature: **{current.get('temperature_2m', 'N/A')}°C**\n"
        message += f"• Feels like: **{current.get('apparent_temperature', 'N/A')}°C**\n"
        message += f"• Wind: **{current.get('wind_speed_10m', 'N/A')} km/h**\n"
        message += "\n"
        message += "**5-Day Forecast**\n"
    else:
        message = f"{icon} **Meteo per {city}**\n"
        if region:
            message += f"*{region}*\n"
        message += "\n"
        message += f"**Condizioni Attuali**\n"
        message += f"{description}\n"
        message += f"• Temperatura: **{current.get('temperature_2m', 'N/A')}°C**\n"
        message += f"• Percepita: **{current.get('apparent_temperature', 'N/A')}°C**\n"
        message += f"• Vento: **{current.get('wind_speed_10m', 'N/A')} km/h**\n"
        message += "\n"
        message += "**Previsioni 5 Giorni**\n"
    
    # Add daily forecast
    days = daily.get('time', [])[:5]
    temp_max = daily.get('temperature_2m_max', [])
    temp_min = daily.get('temperature_2m_min', [])
    codes = daily.get('weather_code', [])
    
    day_names_en = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_names_it = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
    day_names = day_names_it if lang == 'it' else day_names_en
    
    for i in range(min(len(days), 5)):
        day_str = days[i]
        try:
            date_obj = datetime.strptime(day_str, '%Y-%m-%d')
            day_name = day_names[date_obj.weekday()]
            date_formatted = date_obj.strftime('%d/%m')
            
            icon_day = get_weather_icon(codes[i] if i < len(codes) else 0)
            
            if i < len(temp_max) and i < len(temp_min):
                if lang == 'en':
                    message += f"{day_name} {date_formatted} {icon_day} Min {temp_min[i]:.0f}° → Max **{temp_max[i]:.0f}°**\n"
                else:
                    message += f"{day_name} {date_formatted} {icon_day} Min {temp_min[i]:.0f}° → Max **{temp_max[i]:.0f}°**\n"
            else:
                message += f"{day_name} {date_formatted} {icon_day} N/A\n"
        except:
            continue
    
    message += "\n_Data source: Open-Meteo_"
    return message

def get_complete_weather_report(city, lang):
    """Main weather report function."""
    lat, lon, region = get_coordinates(city)
    
    if lat is None:
        if lang == 'en':
            return {'success': False, 'message': f"❌ City '{city}' not found"}
        else:
            return {'success': False, 'message': f"❌ Città '{city}' non trovata"}
    
    weather_data = get_weather_data(lat, lon)
    
    if not weather_data:
        if lang == 'en':
            return {'success': False, 'message': "❌ Weather service unavailable"}
        else:
            return {'success': False, 'message': "❌ Servizio meteo non disponibile"}
    
    message = create_weather_message(city, region, weather_data, lang)
    return {'success': True, 'message': message}

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
                    welcome = "Hello! I'm your Weather Bot 🌤️\n\nSend me a city name or use:\n/weather <city> - Get forecast\n/save <city> - Save your city\n/myweather - Get forecast for saved city\n/rainalerts - Toggle rain notifications\n/myalerts - Check rain alerts status\n/language - Change language"
                else:
                    welcome = "Ciao! Sono il tuo Bot Meteo 🌤️\n\nInviami un nome di città o usa:\n/meteo <città> - Previsioni\n/salva <città> - Salva città\n/miometeo - Previsioni città salvata\n/avvisipioggia - Attiva notifiche pioggia\n/mieiavvisi - Controlla avvisi pioggia\n/lingua - Cambia lingua"
                
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
                city = text.split(' ', 1)[1]
                result = get_complete_weather_report(city, lang)
                send_message(chat_id, result['message'])
                
                # Ask to save
                if result['success'] and not get_user_city(chat_id):
                    if lang == 'en':
                        prompt = f"\n💡 Save '{city}' as your city? Use /save {city}"
                    else:
                        prompt = f"\n💡 Salvare '{city}' come tua città? Usa /salva {city}"
                    send_message(chat_id, prompt)
                    
            elif text.startswith(('/save ', '/salva ')):
                city = text.split(' ', 1)[1]
                save_user_city(chat_id, city)
                if lang == 'en':
                    send_message(chat_id, f"✅ City '{city}' saved! Now use:\n/myweather - Get forecast\n/rainalerts - Enable rain alerts\n/myalerts - Check alerts status")
                else:
                    send_message(chat_id, f"✅ Città '{city}' salvata! Ora usa:\n/miometeo - Previsioni\n/avvisipioggia - Attiva avvisi pioggia\n/mieiavvisi - Controlla avvisi")
                    
            elif text in ['/myweather', '/miometeo']:
                city = get_user_city(chat_id)
                if city:
                    result = get_complete_weather_report(city, lang)
                    send_message(chat_id, result['message'])
                else:
                    if lang == 'en':
                        send_message(chat_id, "❌ No city saved. Use /save <city>")
                    else:
                        send_message(chat_id, "❌ Nessuna città salvata. Usa /salva <città>")
                        
            elif text in ['/help', '/aiuto']:
                if lang == 'en':
                    help_text = """🌤️ **Weather Bot Help**

**Commands:**
/weather <city> - Get forecast
/save <city> - Save city  
/myweather - Forecast for saved city
/rainalerts - Toggle rain notifications
/myalerts - Check rain alerts status
/language - Change language

**Tips:**
• Data is now saved in database (won't be lost!)
• Rain alerts have 6-hour cooldown
• Alerts only 7:00-22:00"""
                else:
                    help_text = """🌤️ **Aiuto Bot Meteo**

**Comandi:**
/meteo <città> - Previsioni
/salva <città> - Salva città
/miometeo - Previsioni città salvata
/avvisipioggia - Attiva notifiche pioggia
/mieiavvisi - Controlla avvisi pioggia
/lingua - Cambia lingua

**Consigli:**
• I dati ora sono salvati su database (non si perdono!)
• Avvisi pioggia hanno pausa di 6 ore
• Avvisi solo 7:00-22:00"""
                send_message(chat_id, help_text)
                
            # ===== NUOVO COMANDO: /myalerts /mieiavvisi =====
            elif text in ['/myalerts', '/mieiavvisi']:
                # Get user's recent alerts status
                alerts_enabled = get_rain_alerts_status(chat_id)
                city = get_user_city(chat_id)
                
                if lang == 'en':
                    message = "🔔 *Your Rain Alerts Status*\n\n"
                    if alerts_enabled and city:
                        message += f"✅ **ACTIVE** for {city}\n"
                        message += "You'll receive alerts when rain is expected.\n\n"
                        
                        # Get recent alerts from database
                        recent_alerts = db.get_recent_rain_alerts(str(chat_id), hours=24)
                        if recent_alerts:
                            message += "*Recent alerts:*\n"
                            for alert in recent_alerts[:5]:  # Show last 5
                                alert_time = datetime.fromisoformat(alert['sent_at'].replace('Z', '+00:00'))
                                message += f"• {alert_time.strftime('%H:%M')} - {alert['city']}\n"
                        else:
                            message += "*Recent alerts:* None in last 24h\n"
                        
                        message += f"\n*Settings:*\n• Time: 7:00-22:00\n• Cooldown: 6 hours\n• Data: Saved in database ✅"
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
                        
                        # Get recent alerts from database
                        recent_alerts = db.get_recent_rain_alerts(str(chat_id), hours=24)
                        if recent_alerts:
                            message += "*Avvisi recenti:*\n"
                            for alert in recent_alerts[:5]:
                                alert_time = datetime.fromisoformat(alert['sent_at'].replace('Z', '+00:00'))
                                message += f"• {alert_time.strftime('%H:%M')} - {alert['city']}\n"
                        else:
                            message += "*Avvisi recenti:* Nessuno nelle ultime 24h\n"
                        
                        message += f"\n*Impostazioni:*\n• Orario: 7:00-22:00\n• Pausa: 6 ore\n• Dati: Salvati su database ✅"
                    elif city:
                        message += f"❌ **DISATTIVI** per {city}\n\n"
                        message += "Attiva gli avvisi con /avvisipioggia"
                    else:
                        message += "❌ Nessuna città salvata\n\n"
                        message += "Salva prima una città con /salva <città>"
                
                send_message(chat_id, message)
                
            # ===== COMANDO RAINALERTS MODIFICATO =====
            elif text in ['/rainalerts', '/avvisipioggia']:
                saved_city = get_user_city(chat_id)
                if not saved_city:
                    if lang == 'en':
                        send_message(chat_id, "❌ No city saved. Use /save <city> first.")
                    else:
                        send_message(chat_id, "❌ Nessuna città salvata. Usa prima /salva <città>.")
                    return
                
                # Toggle rain alerts
                current = get_rain_alerts_status(chat_id)
                new_status = not current
                set_rain_alerts_status(chat_id, new_status)
                
                if new_status:
                    if lang == 'en':
                        message = f"✅ Rain alerts ACTIVATED for {saved_city}!\n\n"
                        message += "You'll receive alerts when rain is expected.\n"
                        message += "• Time: 7:00 AM - 10:00 PM\n"
                        message += "• Cooldown: 6 hours between alerts\n"
                        message += "• Data: Saved in database ✅\n\n"
                        message += "Use /myalerts to check status"
                    else:
                        message = f"✅ Avvisi pioggia ATTIVATI per {saved_city}!\n\n"
                        message += "Riceverai avvisi quando è prevista pioggia.\n"
                        message += "• Orario: 7:00 - 22:00\n"
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
                else:
                    if lang == 'en':
                        send_message(chat_id, "Send me a city name (e.g. 'Rome') or use /help")
                    else:
                        send_message(chat_id, "Inviami un nome di città (es. 'Roma') o usa /aiuto")
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"Error: {e}")
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
        
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

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
                <p><strong>Database Stats:</strong> <a href="/db-stats">/db-stats</a></p>
                <p><strong>Ping:</strong> <a href="/ping">/ping</a></p>
            </div>
            
            <div class="endpoint">
                <h3>🔧 Database Info</h3>
                <p><strong>Type:</strong> SQLite (persistent)</p>
                <p><strong>File:</strong> users.db</p>
                <p><strong>Features:</strong> Cities saved permanently, rain alerts cooldown, alert history</p>
            </div>
            
            <hr>
            <p><small>Powered by Open-Meteo API | Running on Render | Database: SQLite</small></p>
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
        'bot_token_configured': bool(Config.BOT_TOKEN)
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

# ========== DATABASE BACKUP ENDPOINT ==========
@app.route('/admin/backup')
def backup_database():
    """Create a backup of the database."""
    try:
        import shutil
        from datetime import datetime
        
        if not os.path.exists('users.db'):
            return jsonify({'error': 'Database file not found'}), 404
        
        # Create backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'users_backup_{timestamp}.db'
        
        # Copy database file
        shutil.copy2('users.db', backup_file)
        
        return jsonify({
            'status': 'success',
            'message': f'Backup created: {backup_file}',
            'backup_file': backup_file,
            'file_size': os.path.getsize(backup_file)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== START SERVER ==========
if __name__ == '__main__':
    # Check if BOT_TOKEN is set
    if not Config.BOT_TOKEN:
        logger.error("❌ CRITICAL ERROR: BOT_TOKEN is not set!")
        logger.error("Please set BOT_TOKEN environment variable in Render:")
        logger.error("1. Go to your Render dashboard")
        logger.error("2. Click on your service")
        logger.error("3. Go to 'Environment'")
        logger.error("4. Add variable: BOT_TOKEN=your_bot_token_here")
        logger.error("5. Restart the service")
        
        @app.route('/')
        def error_home():
            return """
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h1>❌ Configuration Error</h1>
                <p>BOT_TOKEN is not set in environment variables.</p>
                <h3>Steps to fix:</h3>
                <ol>
                    <li>Go to your Render dashboard</li>
                    <li>Click on your service</li>
                    <li>Go to 'Environment' section</li>
                    <li>Add variable: <code>BOT_TOKEN=your_bot_token_here</code></li>
                    <li>Restart the service</li>
                </ol>
            </body>
            </html>
            """
    else:
        logger.info(f"✅ BOT_TOKEN is set (length: {len(Config.BOT_TOKEN)})")
        logger.info(f"🚀 Starting server on port {Config.PORT}")
        logger.info(f"💾 Database initialized: users.db")
        logger.info(f"🌧️ Rain alerts with 6-hour cooldown and persistent storage")
    
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)