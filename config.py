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
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')
    
    # Cron job security
    CRON_SECRET = os.getenv('CRON_SECRET')
    
    # Admin user ID for notifications
    ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')
    
    # Timezone settings
    TIMEZONE = 'Europe/Rome'
    
    # Rain alert settings - 
    RAIN_CHECK_INTERVAL = 30  # minutes
    MORNING_REPORT_HOUR = 8   # 8:00 AM
    RAIN_ALERT_WINDOW_START = 8    
    RAIN_ALERT_WINDOW_END = 24    
    
    # per rain alerts
    RAIN_ALERT_MIN_MINUTES = 15   
    RAIN_ALERT_MAX_MINUTES = 90   
    RAIN_ALERT_COOLDOWN_HOURS = 6 
    RAIN_MIN_INTENSITY_MM = 0.3   
    
    @classmethod
    def validate(cls):
        """Validate all required configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        
        if cls.WEBHOOK_MODE and not cls.RENDER_EXTERNAL_URL:
            raise ValueError("RENDER_EXTERNAL_URL is required for webhook mode")
        
        if not cls.WEBHOOK_SECRET:
            print("⚠️  WARNING: WEBHOOK_SECRET is not set")
        
        if not cls.CRON_SECRET:
            print("⚠️  WARNING: CRON_SECRET is not set")
        
        return True