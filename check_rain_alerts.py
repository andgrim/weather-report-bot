import logging
from datetime import datetime, timedelta
import pytz
import time
import sqlite3
import asyncio
from telegram import Bot
from weather_service import get_coordinates, get_weather_forecast, get_detailed_rain_alert
from config import Config
from rain_alerts_tracker import has_alert_been_sent_recently, mark_alert_as_sent

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_all_users_with_rain_alerts():
    """Ottieni tutti gli utenti con allerta pioggia abilitata."""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE rain_alerts = 1 AND city IS NOT NULL AND city != ""')
        users = cursor.fetchall()
        conn.close()
        return {str(user[0]): True for user in users}
    except Exception as e:
        logger.error(f"Errore nel recupero utenti con allerta: {e}")
        return {}

def get_user_language(user_id):
    """Ottieni lingua utente."""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT language FROM users WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 'en'
    except Exception as e:
        logger.error(f"Errore nel recupero lingua: {e}")
        return 'en'

def get_user_city(user_id):
    """Ottieni città utente."""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT city FROM users WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Errore nel recupero città: {e}")
        return None

def send_message_sync(bot, chat_id, text):
    """Invia un messaggio in modo sincrono, gestendo il loop asincrono."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Usa run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(
            bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown'),
            loop
        )
        future.result()  # Attendi il completamento
    else:
        # Crea un nuovo loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')
            )
        finally:
            loop.close()

def check_and_send_rain_alerts():
    """Check rain for all users with alerts enabled and send notifications (24/7)."""
    try:
        bot = Bot(token=Config.BOT_TOKEN)
        
        # Get all users with rain alerts enabled FROM DATABASE
        users_with_alerts = get_all_users_with_rain_alerts()
        
        if not users_with_alerts:
            logger.info("ℹ️ No users with rain alerts enabled in database")
            return
        
        # Italian timezone
        rome_tz = pytz.timezone(Config.TIMEZONE)
        current_time = datetime.now(rome_tz)
        
        logger.info(f"🌧️ Checking rain alerts for {len(users_with_alerts)} users at {current_time.strftime('%H:%M')}")
        
        alerts_sent = 0
        skipped_alerts = 0
        errors = 0
        
        for user_id_str in users_with_alerts.keys():
            try:
                user_id = int(user_id_str)
                lang = get_user_language(user_id_str)
                city = get_user_city(user_id_str)
                
                if not city:
                    logger.warning(f"User {user_id_str} has alerts enabled but no city saved")
                    continue
                
                # Get weather data
                lat, lon, region = get_coordinates(city)
                if lat is None:
                    logger.warning(f"Could not get coordinates for city: {city}")
                    continue
                
                weather_data = get_weather_forecast(lat, lon)
                if not weather_data:
                    logger.warning(f"Could not get weather data for: {city}")
                    continue
                
                timezone = weather_data.get('timezone', 'Europe/Rome')
                hourly = weather_data.get('hourly', {})
                rain_events = get_detailed_rain_alert(hourly, timezone, lang)
                
                if not rain_events:
                    continue
                
                # Check if rain is coming soon (next 90 minutes, not too soon) - 24/7
                now = datetime.now(rome_tz)
                
                upcoming_rain = []
                for event in rain_events:
                    time_diff = event['time'] - now
                    # Rain between 15 and 90 minutes from now (24/7, no time restrictions)
                    if timedelta(minutes=15) < time_diff < timedelta(minutes=90):
                        upcoming_rain.append(event)
                
                if upcoming_rain:
                    # Take the first upcoming rain event
                    first_rain = upcoming_rain[0]
                    rain_time_str = first_rain['time'].strftime('%H:%M')
                    minutes_to_rain = int((first_rain['time'] - now).total_seconds() / 60)
                    
                    # Check if we've already sent an alert for this rain event recently
                    if has_alert_been_sent_recently(user_id_str, city, rain_time_str, cooldown_hours=6):
                        logger.info(f"⏸️ Skipping alert for user {user_id_str} - already notified about rain at {rain_time_str}")
                        skipped_alerts += 1
                        continue
                    
                    # Format intensity description
                    intensity_map = {
                        'light': {'en': 'light', 'it': 'leggera'},
                        'moderate': {'en': 'moderate', 'it': 'moderata'},
                        'heavy': {'en': 'heavy', 'it': 'forte'},
                        'leggera': {'en': 'light', 'it': 'leggera'},
                        'moderata': {'en': 'moderate', 'it': 'moderata'},
                        'forte': {'en': 'heavy', 'it': 'forte'}
                    }
                    
                    intensity_key = first_rain['intensity']
                    intensity_desc = intensity_map.get(intensity_key, {}).get(lang, intensity_key)
                    
                    # Round minutes to nearest 5 for cleaner message
                    rounded_minutes = round(minutes_to_rain / 5) * 5
                    
                    if lang == 'it':
                        message = (
                            f"🌧️ *AVVISO PIOGGIA!*\n\n"
                            f"A {city} inizierà a piovere tra circa {rounded_minutes} minuti ({rain_time_str}).\n\n"
                            f"• Intensità: {intensity_desc}\n"
                            f"• Precipitazioni: {first_rain['precipitation']:.1f} mm\n"
                            f"• Probabilità: {first_rain.get('probability', 0)}%\n\n"
                            f"Preparati! ☔"
                        )
                    else:
                        message = (
                            f"🌧️ *RAIN ALERT!*\n\n"
                            f"In {city} rain will start in about {rounded_minutes} minutes ({rain_time_str}).\n\n"
                            f"• Intensity: {intensity_desc}\n"
                            f"• Precipitation: {first_rain['precipitation']:.1f} mm\n"
                            f"• Probability: {first_rain.get('probability', 0)}%\n\n"
                            f"Be prepared! ☔"
                        )
                    
                    send_message_sync(bot, user_id, message)
                    
                    # Mark this alert as sent
                    mark_alert_as_sent(user_id_str, city, rain_time_str)
                    
                    alerts_sent += 1
                    logger.info(f"✅ Sent rain alert to user {user_id} for {city} (at {rain_time_str}, in ~{rounded_minutes} min)")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                    
            except Exception as e:
                errors += 1
                logger.error(f"❌ Error checking rain for user {user_id_str}: {e}")
        
        logger.info(f"📊 Rain alerts check completed:")
        logger.info(f"   ✅ Alerts sent: {alerts_sent}")
        logger.info(f"   ⏸️ Skipped (duplicates): {skipped_alerts}")
        logger.info(f"   ❌ Errors: {errors}")
        
        # Send admin notification if configured
        if Config.ADMIN_USER_ID and (alerts_sent > 0 or errors > 0 or skipped_alerts > 0):
            try:
                admin_msg = (
                    f"🌧️ *Rain Alerts Summary*\n"
                    f"Time: {current_time.strftime('%H:%M %d/%m/%Y')}\n"
                    f"Users checked: {len(users_with_alerts)}\n"
                    f"✅ Alerts sent: {alerts_sent}\n"
                    f"⏸️ Skipped (duplicates): {skipped_alerts}\n"
                    f"❌ Errors: {errors}"
                )
                
                send_message_sync(bot, int(Config.ADMIN_USER_ID), admin_msg)
            except Exception as e:
                logger.error(f"Failed to send admin notification: {e}")
                
    except Exception as e:
        logger.error(f"❌ Critical error in rain alerts check: {e}")

if __name__ == '__main__':
    logger.info("🌧️ Starting rain alerts check (24/7)...")
    check_and_send_rain_alerts()
    logger.info("🌧️ Rain alerts check completed!")