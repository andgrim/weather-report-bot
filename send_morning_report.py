import logging
import time
import pytz
from datetime import datetime
from telegram import Bot
from config import Config
from database_utils import get_all_users_with_cities, get_user_language
from weather_service import get_complete_weather_report

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def send_morning_reports():
    """Send morning weather reports to all users with saved cities."""
    try:
        bot = Bot(token=Config.BOT_TOKEN)
        
        # Get all users with saved cities FROM DATABASE
        users_with_cities = get_all_users_with_cities()
        
        if not users_with_cities:
            logger.info("ℹ️ No users with saved cities found in database")
            return
        
        # Italian timezone
        rome_tz = pytz.timezone(Config.TIMEZONE)
        current_time = datetime.now(rome_tz)
        
        logger.info(f"📨 Preparing to send morning reports to {len(users_with_cities)} users")
        
        successful_sends = 0
        failed_sends = 0
        
        for user_id_str, city in users_with_cities.items():
            try:
                user_id = int(user_id_str)
                lang = get_user_language(user_id_str)
                
                logger.info(f"📧 Processing user {user_id} for city {city}, language {lang}")
                
                # Get weather report (includes current + 24h + 5-day)
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
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.3)
                    
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
                            text=error_msg.get(lang, error_msg['en'])
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
        if Config.ADMIN_USER_ID and (successful_sends + failed_sends) > 0:
            try:
                summary_msg = (
                    f"📊 *Morning Report Summary*\n"
                    f"Time: {current_time.strftime('%H:%M %d/%m/%Y')}\n"
                    f"Users with saved cities: {len(users_with_cities)}\n"
                    f"✅ Successful: {successful_sends}\n"
                    f"❌ Failed: {failed_sends}\n"
                    f"📨 Total attempted: {successful_sends + failed_sends}"
                )
                
                bot.send_message(
                    chat_id=int(Config.ADMIN_USER_ID),
                    text=summary_msg,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"❌ Failed to send admin summary: {e}")
                
    except Exception as e:
        logger.error(f"❌ Critical error in morning reports: {e}")

if __name__ == '__main__':
    logger.info("🌅 Starting morning report sender...")
    send_morning_reports()
    logger.info("🌅 Morning reports completed!")