"""
Send automatic morning weather reports to users with saved cities
Runs daily at 8:00 AM via Cron Job on Render
"""

import json
import logging
import os
from datetime import datetime, time as dt_time
import pytz
from telegram import Bot
from weather_service import get_complete_weather_report

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# File to store user preferences
USER_PREFS_FILE = 'user_preferences.json'

def load_user_prefs():
    """Load user preferences from file."""
    if os.path.exists(USER_PREFS_FILE):
        with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def send_morning_reports():
    """Send morning weather reports to all users with saved cities."""
    # Load bot token from environment
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in environment variables")
        return
    
    # Load user preferences
    prefs = load_user_prefs()
    
    # Get all users with saved cities
    if 'cities' not in prefs or not prefs['cities']:
        logger.info("ℹ️ No users with saved cities found")
        return
    
    users_with_cities = prefs['cities']
    
    logger.info(f"📨 Preparing to send morning reports to {len(users_with_cities)} users")
    
    # Initialize bot
    bot = Bot(token=BOT_TOKEN)
    
    # Italian timezone
    rome_tz = pytz.timezone('Europe/Rome')
    current_time = datetime.now(rome_tz)
    
    # Check if it's a reasonable time to send (between 6:00 and 10:00)
    current_hour = current_time.hour
    if current_hour < 6 or current_hour > 10:
        logger.warning(f"⚠️ Not sending morning reports at {current_hour}:00 (outside 6:00-10:00 window)")
        # But continue anyway for testing
    
    successful_sends = 0
    failed_sends = 0
    
    for user_id_str, city in users_with_cities.items():
        try:
            user_id = int(user_id_str)
            
            # Get user's language preference
            lang = prefs.get(user_id_str, 'en')
            
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
                bot.send_message(
                    chat_id=user_id,
                    text=full_message,
                    parse_mode='Markdown'
                )
                
                successful_sends += 1
                logger.info(f"✅ Sent morning report to user {user_id} for {city}")
                
                # Add small delay to avoid rate limiting
                import time
                time.sleep(0.5)
                
            else:
                logger.warning(f"⚠️ Could not get weather for {city} (user {user_id})")
                failed_sends += 1
                
                # Send error message to user
                error_msg = {
                    'it': f"⚠️ Non sono riuscito a recuperare le previsioni per {city} questa mattina.\n\n"
                          f"Controlla che il nome della città sia corretto o salva una nuova città con /salvacitta",
                    'en': f"⚠️ I couldn't retrieve the forecast for {city} this morning.\n\n"
                          f"Please check if the city name is correct or save a new city with /savecity"
                }
                
                try:
                    bot.send_message(
                        chat_id=user_id,
                        text=error_msg[lang]
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to send error message to user {user_id}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error processing user {user_id_str}: {e}")
            failed_sends += 1
    
    # Log summary
    logger.info(f"📊 Morning report summary:")
    logger.info(f"   ✅ Successful: {successful_sends}")
    logger.info(f"   ❌ Failed: {failed_sends}")
    logger.info(f"   🕒 Time: {current_time.strftime('%H:%M %d/%m/%Y')}")
    
    # Send admin summary if enabled
    admin_id = os.getenv('ADMIN_USER_ID')
    if admin_id and successful_sends + failed_sends > 0:
        try:
            summary_msg = (
                f"📊 *Morning Report Summary*\n"
                f"Time: {current_time.strftime('%H:%M %d/%m/%Y')}\n"
                f"Users with saved cities: {len(users_with_cities)}\n"
                f"✅ Successful: {successful_sends}\n"
                f"❌ Failed: {failed_sends}\n"
                f"📨 Total sent: {successful_sends + failed_sends}"
            )
            
            bot.send_message(
                chat_id=int(admin_id),
                text=summary_msg,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Failed to send admin summary: {e}")

if __name__ == '__main__':
    logger.info("🌅 Starting morning report sender...")
    send_morning_reports()
    logger.info("🌅 Morning reports completed!")