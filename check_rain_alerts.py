"""
Check for imminent rain and send alerts to users who opted in
Runs every 30 minutes via Cron Job on Render
"""

import json
import os
import logging
from datetime import datetime, timedelta
import pytz
import time
from telegram import Bot
from weather_service import get_coordinates, get_weather_forecast, get_detailed_rain_alert

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_PREFS_FILE = 'user_preferences.json'

def load_user_prefs():
    if os.path.exists(USER_PREFS_FILE):
        with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def check_and_send_rain_alerts():
    """Check rain for all users with alerts enabled and send notifications."""
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found")
        return
    
    prefs = load_user_prefs()
    
    # Check if users have rain alerts enabled
    if 'rain_alerts' not in prefs or 'cities' not in prefs:
        logger.info("ℹ️ No users with rain alerts enabled")
        return
    
    bot = Bot(token=BOT_TOKEN)
    users_with_alerts = prefs['rain_alerts']
    users_with_cities = prefs['cities']
    
    # Italian timezone
    rome_tz = pytz.timezone('Europe/Rome')
    current_time = datetime.now(rome_tz)
    current_hour = current_time.hour
    
    # Only send alerts between 7:00 and 22:00 (to not disturb at night)
    if current_hour < 7 or current_hour > 22:
        logger.info(f"⏰ Skipping rain alerts at {current_hour}:00 (outside 7:00-22:00 window)")
        return
    
    logger.info(f"🌧️ Checking rain alerts for {len(users_with_alerts)} users at {current_time.strftime('%H:%M')}")
    
    alerts_sent = 0
    
    for user_id_str, alerts_enabled in users_with_alerts.items():
        if not alerts_enabled:
            continue
        
        # Check if user has a saved city
        city = users_with_cities.get(user_id_str)
        if not city:
            continue
        
        try:
            user_id = int(user_id_str)
            lang = prefs.get(user_id_str, 'en')
            
            # Get weather data
            lat, lon, region = get_coordinates(city)
            if lat is None:
                continue
            
            weather_data = get_weather_forecast(lat, lon)
            if not weather_data:
                continue
            
            hourly = weather_data.get('hourly', {})
            rain_events = get_detailed_rain_alert(hourly, lang)
            
            if rain_events:
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
                    if lang == 'it':
                        intensity_desc = {
                            'leggera': 'leggera',
                            'moderata': 'moderata', 
                            'forte': 'forte'
                        }.get(first_rain['intensity'], first_rain['intensity'])
                        
                        message = (
                            f"🌧️ *AVVISO PIOGGIA IMMINENTE!*\n\n"
                            f"A {city} inizierà a piovere tra circa {minutes_to_rain} minuti!\n\n"
                            f"• Orario: {first_rain['time'].strftime('%H:%M')}\n"
                            f"• Intensità: {intensity_desc}\n"
                            f"• Precipitazioni: {first_rain['precipitation']:.1f} mm\n\n"
                            f"Preparati! ☔"
                        )
                    else:
                        intensity_desc = {
                            'light': 'light',
                            'moderate': 'moderate',
                            'heavy': 'heavy'
                        }.get(first_rain['intensity'], first_rain['intensity'])
                        
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
                    time.sleep(0.5)  # Avoid rate limiting
            
        except Exception as e:
            logger.error(f"❌ Error checking rain for user {user_id_str}: {e}")
    
    logger.info(f"📊 Rain alerts sent: {alerts_sent}")

if __name__ == '__main__':
    check_and_send_rain_alerts()