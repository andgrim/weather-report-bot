# 🌤️ Weather Report Bot

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
# 🌤️ Weather Report Bot

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
# 🌤️ Weather Report Bot

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
weather-report-bot/
├── .env # Bot token (SECRET, not in Git)
├── .gitignore # Files to ignore in version control
├── requirements.txt # Python dependencies
├── config.py # Loads configuration from .env
├── bot_core.py # Main bot logic and command handlers
├── weather_service.py # API calls to Open-Meteo and data formatting
├── user_preferences.json # Saves user language choice (auto-generated)
├── send_morning_report.py # Script for the scheduled 8 AM report
├── README.md # This file
└── LICENSE # MIT License file

## 5. 🚀 Deployment on Render.com

### A) Deploy the Main Bot (Web Service)
1.  Create a new **Web Service** on [Render](https://render.com).
2.  Connect your GitHub/GitLab repository.
3.  Configure the service:
    *   **Environment**: `Python 3`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `python bot_core.py`
4.  Add the `BOT_TOKEN` as an **Environment Variable** in the Render dashboard.


### B) Schedule the 8 AM Report (Cron Job)
1.  In your Render dashboard, create a new **Cron Job**.
2.  Connect the same repository.
3.  Configure the job:
    *   **Schedule**: `0 6 * * *` (This is 6:00 UTC, which is 8:00 AM Italian Time/CET).
    *   **Command**: `python send_morning_report.py`
4.  Add the same `BOT_TOKEN` environment variable to this Cron Job.
5.  The Cron Job will run the script daily, sending the forecast to all users who have set a language preference.

**Data Provider**: [Open-Meteo](https://open-meteo.com/) (Free Weather API)