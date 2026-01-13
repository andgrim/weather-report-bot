import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Bot Token
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is required in .env file")
    
    # Render deployment settings
    PORT = int(os.environ.get('PORT', 10000))
    RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
    
    # Determine if we're running on Render
    IS_RENDER = os.environ.get('RENDER', '').lower() == 'true'
    
    # Webhook settings (for Render deployment)
    WEBHOOK_MODE = IS_RENDER and bool(RENDER_EXTERNAL_URL)
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-webhook-secret')
    
    # Cron job security
    CRON_SECRET = os.getenv('CRON_SECRET')
    
    # Admin user ID for notifications
    ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')
    
    # API settings
    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    
    # Timezone settings
    TIMEZONE = 'Europe/Rome'
    
    # Rain alert settings
    RAIN_CHECK_INTERVAL = 30  # minutes
    MORNING_REPORT_HOUR = 8   # 8:00 AM
    RAIN_ALERT_WINDOW_START = 7   # 7:00 AM
    RAIN_ALERT_WINDOW_END = 22    # 10:00 PM
    
    # Weather thresholds
    MIN_RAIN_THRESHOLD = 0.3  # mm - minimum precipitation to trigger alert
    RAIN_PROBABILITY_THRESHOLD = 50  # % - minimum probability to trigger alert
    
    @classmethod
    def validate(cls):
        """Validate all required configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        
        if cls.WEBHOOK_MODE and not cls.RENDER_EXTERNAL_URL:
            raise ValueError("RENDER_EXTERNAL_URL is required for webhook mode")
        
        if cls.CRON_SECRET == 'your-secret-token-here':
            print("⚠️  WARNING: Using default CRON_SECRET. Change it in production!")
        
        return True