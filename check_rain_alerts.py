import logging
from datetime import datetime, timedelta
import pytz
import time
from telegram import Bot
from user_prefs import get_all_users_with_rain_alerts, get_user_language, get_user_city
from weather_service import get_coordinates, get_weather_forecast, get_detailed_rain_alert
from config import Config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def check_and_send_rain_alerts():
    """Check rain for all users with alerts enabled and send notifications."""
    try:
        bot = Bot(token=Config.BOT_TOKEN)
        
        # Get all users with rain alerts enabled
        users_with_alerts = get_all_users_with_rain_alerts()
        
        if not users_with_alerts:
            logger.info("ℹ️ No users with rain alerts enabled")
            return
        
        # Italian timezone
        rome_tz = pytz.timezone(Config.TIMEZONE)
        current_time = datetime.now(rome_tz)
        current_hour = current_time.hour
        
        # Only send alerts during daytime hours
        if current_hour < Config.RAIN_ALERT_WINDOW_START or current_hour > Config.RAIN_ALERT_WINDOW_END:
            logger.info(f"⏰ Skipping rain alerts at {current_hour}:00 (outside {Config.RAIN_ALERT_WINDOW_START}:00-{Config.RAIN_ALERT_WINDOW_END}:00 window)")
            return
        
        logger.info(f"🌧️ Checking rain alerts for {len(users_with_alerts)} users at {current_time.strftime('%H:%M')}")
        
        alerts_sent = 0
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
                
                hourly = weather_data.get('hourly', {})
                rain_events = get_detailed_rain_alert(hourly, lang)
                
                if not rain_events:
                    continue
                
                # Check if rain is coming soon (next 60 minutes)
                now = datetime.now(rome_tz)
                
                upcoming_rain = []
                for event in rain_events:
                    time_diff = event['time'] - now
                    # Rain in next 60 minutes and not in the past
                    if timedelta(minutes=0) < time_diff < timedelta(minutes=60):
                        upcoming_rain.append(event)
                
                if upcoming_rain:
                    # Send alert
                    first_rain = upcoming_rain[0]
                    minutes_to_rain = int((first_rain['time'] - now).total_seconds() / 60)
                    
                    # Don't send if less than 5 minutes (might be ending)
                    if minutes_to_rain < 5:
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
                    
                    if lang == 'it':
                        message = (
                            f"🌧️ *AVVISO PIOGGIA IMMINENTE!*\n\n"
                            f"A {city} inizierà a piovere tra circa {minutes_to_rain} minuti!\n\n"
                            f"• Orario: {first_rain['time'].strftime('%H:%M')}\n"
                            f"• Intensità: {intensity_desc}\n"
                            f"• Precipitazioni: {first_rain['precipitation']:.1f} mm\n\n"
                            f"Preparati! ☔"
                        )
                    else:
                        message = (
                            f"🌧️ *RAIN ALERT!*\n\n"
                            f"In {city} rain will start in about {minutes_to_rain} minutes!\n\n"
                            f"• Time: {first_rain['time'].strftime('%I:%M %p')}\n"
                            f"• Intensity: {intensity_desc}\n"
                            f"• Precipitation: {first_rain['precipitation']:.1f} mm\n\n"
                            f"Be prepared! ☔"
                        )
                    
                    bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    
                    alerts_sent += 1
                    logger.info(f"✅ Sent rain alert to user {user_id} for {city} (in {minutes_to_rain} min)")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.3)
                    
            except Exception as e:
                errors += 1
                logger.error(f"❌ Error checking rain for user {user_id_str}: {e}")
        
        logger.info(f"📊 Rain alerts check completed:")
        logger.info(f"   ✅ Alerts sent: {alerts_sent}")
        logger.info(f"   ❌ Errors: {errors}")
        
        # Send admin notification if configured
        if Config.ADMIN_USER_ID and (alerts_sent > 0 or errors > 0):
            try:
                admin_msg = (
                    f"🌧️ *Rain Alerts Summary*\n"
                    f"Time: {current_time.strftime('%H:%M %d/%m/%Y')}\n"
                    f"Users checked: {len(users_with_alerts)}\n"
                    f"✅ Alerts sent: {alerts_sent}\n"
                    f"❌ Errors: {errors}"
                )
                
                bot.send_message(
                    chat_id=int(Config.ADMIN_USER_ID),
                    text=admin_msg,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send admin notification: {e}")
                
    except Exception as e:
        logger.error(f"❌ Critical error in rain alerts check: {e}")

if __name__ == '__main__':
    logger.info("🌧️ Starting rain alerts check...")
    check_and_send_rain_alerts()
    logger.info("🌧️ Rain alerts check completed!")