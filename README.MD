A bilingual (English/Italian) Telegram bot providing 5-day weather forecasts, current conditions with "feels like" temperature, and rain start alerts.

---

## 1. ✨ Features

*   **Bilingual Interface**: Full support for English (`/language`) and Italian (`/lingua`).
*   **5-Day Forecast**: Daily minimum and maximum temperatures with weather icons.
*   **Current Conditions**: Real-time temperature, "feels like" temperature, and wind speed.
*   **Rain Start Alert**: Notifies if rain is expected within the next 24 hours.
*   **Local City Names**: Correctly finds cities like "Genova" instead of "Genoa".
*   **Morning Reports**: Optional automatic daily forecast at 8:00 AM via Cron Job.

---

## 2. 🛠️ Setup & Installation

1.  **Clone the repository** (if applicable) and navigate into the project folder.
    ```bash
    cd weather-report-bot
    ```

2.  **Create and activate a Python virtual environment**.
    ```bash
    python -m venv venv
    # On Linux/macOS:
    source venv/bin/activate
    # On Windows:
    venv\Scripts\activate
    ```

3.  **Install the required Python packages**.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure your Bot Token**.
    *   Get a token from [@BotFather](https://t.me/botfather) on Telegram.
    *   Create a file named `.env` in the project root.
    *   Add your token to it:
        ```env
        BOT_TOKEN=your_actual_bot_token_here
        ```
    *   **⚠️ Important**: Never commit the `.env` file to public Git.

5.  **Run the bot**.
    ```bash
    python bot_core.py
    ```

---

## 3. 🤖 Usage & Commands

*   **`/start`**: Initialize the bot and see the welcome message.
*   **`/weather <city>`** or **`/meteo <città>`**: Get the weather forecast for a specific city.
*   **`/language`** or **`/lingua`**: Switch the bot's interface language.
*   **Direct Message**: Simply type and send a city name (e.g., `London` or `Roma`) to get its forecast.

---

## 4. 📁 Project File Structure

    weather_report_bot/
    ├── bot_core.py              # Main bot logic (polling mode)
    ├── render_webhook.py        # Flask server for Render deployment
    ├── weather_service.py       # Open-Meteo API integration
    ├── user_prefs.py           # User preferences management
    ├── send_morning_report.py  # Automated morning reports
    ├── check_rain_alerts.py    # Rain alerts checker
    ├── config.py              # Configuration management
    ├── requirements.txt       # Python dependencies
    ├── .env.example          # Example environment variables
    ├── README.md            # This file
    └── user_preferences.json # Auto-generated user data

#API Integration

This bot uses the Open-Meteo API for weather data:

    Free tier with no API key required

    Global coverage with high accuracy

    5-day forecasts with hourly data

    Multiple weather parameters

Monitoring
Health Check
text

https://<YOUR_RENDER_URL>/health

Returns: {"status": "healthy"}
Admin Dashboard
text

https://<YOUR_RENDER_URL>/admin/stats

Shows user statistics and bot metrics
Debug Endpoints

    /debug-user-prefs - View user preferences

    /test-cron - Generate cron signature for testing

Troubleshooting
Common Issues

Bot not responding

    Check webhook status: https://api.telegram.org/bot<TOKEN>/getWebhookInfo

    Verify Render service is "Live"

    Check logs in Render dashboard

"City not found" error

    Use English city names (e.g., "Rome" instead of "Roma")

    Try with country code (e.g., "London, UK")

    Check spelling

Cron jobs not running

    Verify cron job is enabled in Render

    Check cron job logs

    Test manually with curl command

Rain alerts not sending

    Ensure user has saved a city with /savecity

    Rain alerts are enabled with /rainalerts

    Precipitation must be >0.3mm in next 2 hours

Logs Location

    Render: Dashboard → Service → Logs

    Local: Console output when running python bot_core.py

Development
Local Development
bash

# Run in polling mode (no webhook needed)
python bot_core.py

Testing Cron Jobs Locally
bash

# Generate signature
echo -n "" | openssl sha256 -hmac "your_cron_secret" | awk '{print $2}'

# Test endpoint
curl -X POST http://localhost:10000/trigger-morning-reports \
  -H "X-Cron-Signature: generated_signature_here"

Adding New Features

    Modify bot_core.py for new commands

    Update weather_service.py for new weather data

    Add translations in render_webhook.py TRANSLATIONS dictionary

    Test locally before deploying

Contributing

    Fork the repository

    Create a feature branch

    Make your changes

    Test thoroughly

    Submit a pull request