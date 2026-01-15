"""
Weather Service Module with Enhanced Rain Alerts and 24-hour Forecast
Provides complete weather reports, detailed rain forecasts, and 24-hour hourly forecasts
"""

import requests
from datetime import datetime, timedelta
import pytz
import time
from functools import lru_cache

# Translation dictionaries
TRANSLATIONS = {
    'en': {
        'current_conditions': 'Current Conditions',
        'feels_like': 'Feels like',
        'wind': 'Wind',
        'forecast': '5-Day Forecast',
        'today': 'Today',
        'min': 'Min',
        'max': 'Max',
        'data_source': 'Data source: Open-Meteo',
        'error_city': "City not found",
        'error_service': "Weather service unavailable",
        'rain_alert': "⚠️ **RAIN ALERT** ⚠️",
        'next_24h': "In the next 24 hours:",
        'morning': "Morning",
        'afternoon': "Afternoon", 
        'evening': "Evening",
        'night': "Night",
        'total_expected': "Total expected",
        'no_significant_rain': "No significant rain expected",
        'rain_intensity_light': "light",
        'rain_intensity_moderate': "moderate",
        'rain_intensity_heavy': "heavy",
        'detailed_rain_title': "🌧️ **Detailed Rain Forecast**",
        'next_48h': "In the next 48 hours:",
        'tomorrow': "Tomorrow",
        'accumulation': "Accumulation",
        '24h_forecast_title': "🕐 **24-Hour Detailed Forecast**",
        'hour_by_hour': "Hour-by-Hour Forecast",
        'temperature': "Temp",
        'precipitation': "Precip",
        'humidity': "Humidity",
        'wind_speed': "Wind",
        'cloud_cover': "Clouds",
        'feels_like_temp': "Feels like"
    },
    'it': {
        'current_conditions': 'Condizioni Attuali',
        'feels_like': 'Percepita',
        'wind': 'Vento',
        'forecast': 'Previsioni 5 Giorni',
        'today': 'Oggi',
        'min': 'Min',
        'max': 'Max',
        'data_source': 'Fonte dati: Open-Meteo',
        'error_city': "Città non trovata",
        'error_service': "Servizio meteo non disponibile",
        'rain_alert': "⚠️ **AVVISO PIOGGIA** ⚠️",
        'next_24h': "Nei prossimi 24 ore:",
        'morning': "Mattina",
        'afternoon': "Pomeriggio",
        'evening': "Sera",
        'night': "Notte",
        'total_expected': "Accumulo previsto",
        'no_significant_rain': "Nessuna pioggia significativa prevista",
        'rain_intensity_light': "leggera",
        'rain_intensity_moderate': "moderata",
        'rain_intensity_heavy': "forte",
        'detailed_rain_title': "🌧️ **Previsione Pioggia Dettagliata**",
        'next_48h': "Nei prossimi 48 ore:",
        'tomorrow': "Domani",
        'accumulation': "Accumulo",
        '24h_forecast_title': "🕐 **Previsioni Dettagliate 24 Ore**",
        'hour_by_hour': "Previsioni Ora per Ora",
        'temperature': "Temp",
        'precipitation': "Precip",
        'humidity': "Umidità",
        'wind_speed': "Vento",
        'cloud_cover': "Nuvole",
        'feels_like_temp': "Percepita"
    }
}

# Weather icons mapping
WEATHER_ICONS = {
    0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
    45: '🌫️', 48: '🌫️',
    51: '🌦️', 53: '🌦️', 55: '🌦️',
    61: '🌧️', 63: '🌧️', 65: '🌧️',
    71: '❄️', 73: '❄️', 75: '❄️',
    80: '🌦️', 81: '🌦️', 82: '🌦️',
    95: '⛈️', 96: '⛈️', 99: '⛈️'
}

# Weather descriptions
WEATHER_DESCRIPTIONS = {
    'en': {
        0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
        45: 'Fog', 48: 'Rime fog',
        51: 'Light drizzle', 53: 'Moderate drizzle', 55: 'Dense drizzle',
        61: 'Light rain', 63: 'Moderate rain', 65: 'Heavy rain',
        71: 'Light snow', 73: 'Moderate snow', 75: 'Heavy snow',
        80: 'Light showers', 81: 'Moderate showers', 82: 'Violent showers',
        95: 'Thunderstorm', 96: 'Thunderstorm with hail', 99: 'Heavy thunderstorm with hail'
    },
    'it': {
        0: 'Cielo sereno', 1: 'Prevalentemente sereno', 2: 'Parzialmente nuvoloso', 3: 'Nuvoloso',
        45: 'Nebbia', 48: 'Nebbia gelata',
        51: 'Pioviggine leggera', 53: 'Pioviggine moderata', 55: 'Pioviggine fitta',
        61: 'Pioggia leggera', 63: 'Pioggia moderata', 65: 'Pioggia forte',
        71: 'Neve leggera', 73: 'Neve moderata', 75: 'Neve forte',
        80: 'Rovesci leggeri', 81: 'Rovesci moderati', 82: 'Rovesci violenti',
        95: 'Temporale', 96: 'Temporale con grandine leggera', 99: 'Temporale con grandine forte'
    }
}

# Cache per evitare troppe richieste
WEATHER_CACHE_DURATION = 300  # 5 minutes
COORDINATES_CACHE_DURATION = 3600  # 1 hour

class WeatherCache:
    def __init__(self):
        self.coordinates_cache = {}
        self.weather_cache = {}
    
    def get_coordinates(self, city_name):
        """Get cached coordinates or fetch new ones."""
        cache_key = city_name.lower().strip()
        
        if cache_key in self.coordinates_cache:
            data, timestamp = self.coordinates_cache[cache_key]
            if time.time() - timestamp < COORDINATES_CACHE_DURATION:
                return data
        
        # Fetch new coordinates
        lat, lon, region = self._fetch_coordinates(city_name)
        if lat is not None:
            self.coordinates_cache[cache_key] = ((lat, lon, region), time.time())
        
        return lat, lon, region
    
    def get_weather(self, lat, lon):
        """Get cached weather or fetch new data."""
        cache_key = f"{lat:.2f},{lon:.2f}"
        
        if cache_key in self.weather_cache:
            data, timestamp = self.weather_cache[cache_key]
            if time.time() - timestamp < WEATHER_CACHE_DURATION:
                return data
        
        # Fetch new weather
        weather_data = self._fetch_weather(lat, lon)
        if weather_data:
            self.weather_cache[cache_key] = (weather_data, time.time())
        
        return weather_data
    
    def _fetch_coordinates(self, city_name):
        """Fetch coordinates from API."""
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=it"
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            if data.get('results'):
                location = data['results'][0]
                return location['latitude'], location['longitude'], location.get('admin1', '')
        except Exception as e:
            print(f"Geocoding error: {e}")
            time.sleep(1)
        return None, None, None
    
    def _fetch_weather(self, lat, lon):
        """Fetch weather from API with retry logic."""
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code',
            'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
            'hourly': 'temperature_2m,apparent_temperature,precipitation,relative_humidity_2m,wind_speed_10m,weather_code,cloud_cover',
            'timezone': 'auto',
            'forecast_days': 5
        }
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=8)
                if response.status_code == 429:  # Too Many Requests
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    print(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                return response.json()
            except Exception as e:
                print(f"Weather API error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        return None

# Global cache instance
weather_cache = WeatherCache()

# Update existing functions to use cache
def get_coordinates(city_name):
    """Convert city name to geographic coordinates."""
    return weather_cache.get_coordinates(city_name)

def get_weather_forecast(lat, lon):
    """Get 5-day weather forecast with hourly data."""
    return weather_cache.get_weather(lat, lon)

def get_detailed_rain_alert(hourly_data, lang='en'):
    """Get detailed rain forecast for the next 24 hours"""
    if not hourly_data or 'time' not in hourly_data or 'precipitation' not in hourly_data:
        return []
    
    now = datetime.now(pytz.utc)
    times = hourly_data['time']
    precipitation = hourly_data['precipitation']
    rain_probability = hourly_data.get('precipitation_probability', [])
    
    rain_events = []
    
    for i in range(min(48, len(times))):  # Check 48 hours
        try:
            hour_time = datetime.fromisoformat(times[i].replace('Z', '+00:00')).replace(tzinfo=pytz.UTC)
            
            # Skip past hours
            if hour_time <= now:
                continue
                
            # Stop after 24 hours
            if hour_time > now + timedelta(hours=24):
                break
                
            precip = precipitation[i] if i < len(precipitation) else 0
            prob = rain_probability[i] if i < len(rain_probability) else 0
            
            # SOLO se la pioggia è significativa (soglia più alta)
            if precip >= 0.5 and prob >= 40:  # 0.5mm e 40% di probabilità
                # Convert to local time
                local_time = hour_time.astimezone(pytz.timezone('Europe/Rome'))
                
                # Determine intensity
                if precip <= 2.5:
                    intensity = TRANSLATIONS[lang]['rain_intensity_light']
                elif precip <= 7.5:
                    intensity = TRANSLATIONS[lang]['rain_intensity_moderate']
                else:
                    intensity = TRANSLATIONS[lang]['rain_intensity_heavy']
                
                rain_events.append({
                    'time': local_time,
                    'hour': local_time.hour,
                    'precipitation': precip,
                    'probability': prob,
                    'intensity': intensity
                })
                
        except Exception as e:
            continue
    
    return rain_events

def get_24h_hourly_forecast(hourly_data, lang='en'):
    """Get detailed hourly forecast for the next 24 hours."""
    if not hourly_data or 'time' not in hourly_data:
        return []
    
    now = datetime.now(pytz.utc)
    times = hourly_data.get('time', [])
    temperatures = hourly_data.get('temperature_2m', [])
    apparent_temps = hourly_data.get('apparent_temperature', [])
    precipitations = hourly_data.get('precipitation', [])
    humidities = hourly_data.get('relative_humidity_2m', [])
    wind_speeds = hourly_data.get('wind_speed_10m', [])
    weather_codes = hourly_data.get('weather_code', [])
    cloud_covers = hourly_data.get('cloud_cover', [])
    
    hourly_forecast = []
    
    for i in range(min(24, len(times))):
        try:
            hour_time = datetime.fromisoformat(times[i].replace('Z', '+00:00')).replace(tzinfo=pytz.UTC)
            
            # Skip past hours
            if hour_time <= now:
                continue
                
            # Convert to local time
            local_time = hour_time.astimezone(pytz.timezone('Europe/Rome'))
            
            hourly_forecast.append({
                'time': local_time,
                'hour': local_time.strftime('%H:%M'),
                'day_part': get_day_part(local_time.hour),
                'temperature': temperatures[i] if i < len(temperatures) else None,
                'apparent_temperature': apparent_temps[i] if i < len(apparent_temps) else None,
                'precipitation': precipitations[i] if i < len(precipitations) else 0,
                'humidity': humidities[i] if i < len(humidities) else None,
                'wind_speed': wind_speeds[i] if i < len(wind_speeds) else None,
                'weather_code': weather_codes[i] if i < len(weather_codes) else 0,
                'cloud_cover': cloud_covers[i] if i < len(cloud_covers) else None,
                'icon': WEATHER_ICONS.get(weather_codes[i] if i < len(weather_codes) else 0, '🌈')
            })
        except Exception as e:
            print(f"Error processing hourly data: {e}")
            continue
    
    return hourly_forecast

def get_day_part(hour):
    """Get part of day based on hour."""
    if 5 <= hour < 12:
        return 'morning'
    elif 12 <= hour < 17:
        return 'afternoon'
    elif 17 <= hour < 22:
        return 'evening'
    else:
        return 'night'

def create_24h_forecast_message(city, region, weather_data, lang):
    """Create detailed 24-hour forecast message."""
    if not weather_data:
        return "❌ Weather data not available" if lang == 'en' else "❌ Dati meteo non disponibili"
    
    hourly = weather_data.get('hourly', {})
    T = TRANSLATIONS[lang]
    
    # Get 24h forecast
    hourly_forecast = get_24h_hourly_forecast(hourly, lang)
    
    if not hourly_forecast:
        if lang == 'en':
            return "❌ Could not retrieve 24-hour forecast data."
        else:
            return "❌ Impossibile recuperare i dati delle previsioni 24 ore."
    
    # Current time
    current_time = datetime.now(pytz.timezone('Europe/Rome')).strftime('%H:%M')
    
    if lang == 'en':
        message = f"🕐 **24-Hour Detailed Forecast - {city}**\n"
        if region:
            message += f"*{region}*\n"
        message += f"*Updated at {current_time}*\n\n"
        
        # Summary section
        message += "**📊 24-Hour Summary**\n"
        
        # Calculate statistics
        temps = [h['temperature'] for h in hourly_forecast if h['temperature'] is not None]
        precip_total = sum(h['precipitation'] for h in hourly_forecast)
        
        if temps:
            avg_temp = sum(temps) / len(temps)
            max_temp = max(temps)
            min_temp = min(temps)
            message += f"• Avg temp: **{avg_temp:.1f}°C** (Max: {max_temp:.1f}°C, Min: {min_temp:.1f}°C)\n"
        
        message += f"• Total precipitation: **{precip_total:.1f} mm**\n\n"
        
        # Hour-by-hour forecast
        message += "**🕐 Hour-by-Hour Forecast**\n"
        message += "```\n"
        message += "Time  | Temp | Precip | Wind  | Clouds\n"
        message += "------|------|--------|-------|-------\n"
        
        for hour in hourly_forecast[:12]:  # Show first 12 hours
            time_str = hour['hour']
            temp = f"{hour['temperature']:.0f}°" if hour['temperature'] is not None else "N/A"
            precip = f"{hour['precipitation']:.1f}mm" if hour['precipitation'] > 0 else "0mm"
            wind = f"{hour['wind_speed']:.0f}km/h" if hour['wind_speed'] is not None else "N/A"
            clouds = f"{hour['cloud_cover']:.0f}%" if hour['cloud_cover'] is not None else "N/A"
            
            message += f"{time_str} | {temp:4} | {precip:6} | {wind:5} | {clouds:6}\n"
        
        message += "```\n\n"
        
        # Detailed breakdown by time of day
        morning = [h for h in hourly_forecast if h['day_part'] == 'morning']
        afternoon = [h for h in hourly_forecast if h['day_part'] == 'afternoon']
        evening = [h for h in hourly_forecast if h['day_part'] == 'evening']
        night = [h for h in hourly_forecast if h['day_part'] == 'night']
        
        if morning:
            morning_temps = [h['temperature'] for h in morning if h['temperature'] is not None]
            if morning_temps:
                morning_avg = sum(morning_temps) / len(morning_temps)
                message += f"• **{T['morning']} (6-12)**: ~{morning_avg:.0f}°C, "
            morning_precip = sum(h['precipitation'] for h in morning)
            message += f"{morning_precip:.1f}mm rain\n"
        
        if afternoon:
            afternoon_temps = [h['temperature'] for h in afternoon if h['temperature'] is not None]
            if afternoon_temps:
                afternoon_avg = sum(afternoon_temps) / len(afternoon_temps)
                message += f"• **{T['afternoon']} (12-18)**: ~{afternoon_avg:.0f}°C, "
            afternoon_precip = sum(h['precipitation'] for h in afternoon)
            message += f"{afternoon_precip:.1f}mm rain\n"
        
        if evening:
            evening_temps = [h['temperature'] for h in evening if h['temperature'] is not None]
            if evening_temps:
                evening_avg = sum(evening_temps) / len(evening_temps)
                message += f"• **{T['evening']} (18-22)**: ~{evening_avg:.0f}°C, "
            evening_precip = sum(h['precipitation'] for h in evening)
            message += f"{evening_precip:.1f}mm rain\n"
        
        if night:
            night_temps = [h['temperature'] for h in night if h['temperature'] is not None]
            if night_temps:
                night_avg = sum(night_temps) / len(night_temps)
                message += f"• **{T['night']} (22-6)**: ~{night_avg:.0f}°C, "
            night_precip = sum(h['precipitation'] for h in night)
            message += f"{night_precip:.1f}mm rain\n"
        
    else:  # Italian
        message = f"🕐 **Previsioni Dettagliate 24 Ore - {city}**\n"
        if region:
            message += f"*{region}*\n"
        message += f"*Aggiornato alle {current_time}*\n\n"
        
        # Summary section
        message += "**📊 Riepilogo 24 Ore**\n"
        
        # Calculate statistics
        temps = [h['temperature'] for h in hourly_forecast if h['temperature'] is not None]
        precip_total = sum(h['precipitation'] for h in hourly_forecast)
        
        if temps:
            avg_temp = sum(temps) / len(temps)
            max_temp = max(temps)
            min_temp = min(temps)
            message += f"• Temp media: **{avg_temp:.1f}°C** (Max: {max_temp:.1f}°C, Min: {min_temp:.1f}°C)\n"
        
        message += f"• Precipitazioni totali: **{precip_total:.1f} mm**\n\n"
        
        # Hour-by-hour forecast
        message += "**🕐 Previsioni Ora per Ora**\n"
        message += "```\n"
        message += "Ora   | Temp | Precip | Vento | Nuvole\n"
        message += "------|------|--------|-------|--------\n"
        
        for hour in hourly_forecast[:12]:  # Show first 12 hours
            time_str = hour['hour']
            temp = f"{hour['temperature']:.0f}°" if hour['temperature'] is not None else "N/A"
            precip = f"{hour['precipitation']:.1f}mm" if hour['precipitation'] > 0 else "0mm"
            wind = f"{hour['wind_speed']:.0f}km/h" if hour['wind_speed'] is not None else "N/A"
            clouds = f"{hour['cloud_cover']:.0f}%" if hour['cloud_cover'] is not None else "N/A"
            
            message += f"{time_str} | {temp:4} | {precip:6} | {wind:5} | {clouds:6}\n"
        
        message += "```\n\n"
        
        # Detailed breakdown by time of day
        morning = [h for h in hourly_forecast if h['day_part'] == 'morning']
        afternoon = [h for h in hourly_forecast if h['day_part'] == 'afternoon']
        evening = [h for h in hourly_forecast if h['day_part'] == 'evening']
        night = [h for h in hourly_forecast if h['day_part'] == 'night']
        
        if morning:
            morning_temps = [h['temperature'] for h in morning if h['temperature'] is not None]
            if morning_temps:
                morning_avg = sum(morning_temps) / len(morning_temps)
                message += f"• **{T['morning']} (6-12)**: ~{morning_avg:.0f}°C, "
            morning_precip = sum(h['precipitation'] for h in morning)
            message += f"{morning_precip:.1f}mm pioggia\n"
        
        if afternoon:
            afternoon_temps = [h['temperature'] for h in afternoon if h['temperature'] is not None]
            if afternoon_temps:
                afternoon_avg = sum(afternoon_temps) / len(afternoon_temps)
                message += f"• **{T['afternoon']} (12-18)**: ~{afternoon_avg:.0f}°C, "
            afternoon_precip = sum(h['precipitation'] for h in afternoon)
            message += f"{afternoon_precip:.1f}mm pioggia\n"
        
        if evening:
            evening_temps = [h['temperature'] for h in evening if h['temperature'] is not None]
            if evening_temps:
                evening_avg = sum(evening_temps) / len(evening_temps)
                message += f"• **{T['evening']} (18-22)**: ~{evening_avg:.0f}°C, "
            evening_precip = sum(h['precipitation'] for h in evening)
            message += f"{evening_precip:.1f}mm pioggia\n"
        
        if night:
            night_temps = [h['temperature'] for h in night if h['temperature'] is not None]
            if night_temps:
                night_avg = sum(night_temps) / len(night_temps)
                message += f"• **{T['night']} (22-6)**: ~{night_avg:.0f}°C, "
            night_precip = sum(h['precipitation'] for h in night)
            message += f"{night_precip:.1f}mm pioggia\n"
    
    message += f"\n_{T['data_source']}_"
    return message

def create_weather_message(city, region, weather_data, lang):
    """Format weather data into a user-friendly message with rain alert"""
    if not weather_data:
        return TRANSLATIONS[lang]['error_service']
    
    current = weather_data.get('current', {})
    daily = weather_data.get('daily', {})
    hourly = weather_data.get('hourly', {})
    T = TRANSLATIONS[lang]
    
    # Get detailed rain alert
    rain_events = get_detailed_rain_alert(hourly, lang)
    
    current_code = current.get('weather_code', 0)
    current_icon = WEATHER_ICONS.get(current_code, '🌈')
    current_desc = WEATHER_DESCRIPTIONS[lang].get(current_code, '')
    
    message_parts = []
    
    # Title
    if lang == 'it':
        message_parts.append(f"**{current_icon} Meteo per {city}**")
    else:
        message_parts.append(f"**{current_icon} Weather for {city}**")
    
    # Region
    if region:
        message_parts.append(f"*{region}*")
    
    # Update time
    update_time = current.get('time', '')
    if update_time and isinstance(update_time, str) and len(update_time) > 10:
        try:
            update_time = update_time.split('T')[1][:5] if 'T' in update_time else update_time[11:16]
        except:
            update_time = datetime.now().strftime('%H:%M')
    else:
        update_time = datetime.now().strftime('%H:%M')
    
    if lang == 'it':
        message_parts.append(f"*Aggiornato alle {update_time}*")
    else:
        message_parts.append(f"*Updated at {update_time}*")
    
    message_parts.append("")
    
    # Enhanced Rain Alert Section
    if rain_events:
        message_parts.append(T['rain_alert'])
        message_parts.append(f"*{T['next_24h']}*")
        
        # Group by time of day
        morning_rain = [e for e in rain_events if 6 <= e['hour'] < 12]
        afternoon_rain = [e for e in rain_events if 12 <= e['hour'] < 18]
        evening_rain = [e for e in rain_events if 18 <= e['hour'] < 24]
        night_rain = [e for e in rain_events if e['hour'] < 6]
        
        if morning_rain:
            first = morning_rain[0]
            if lang == 'it':
                message_parts.append(f"• 🌅 **{T['morning']}**: Pioggia {first['intensity']} verso le {first['time'].strftime('%H:%M')}")
            else:
                message_parts.append(f"• 🌅 **{T['morning']}**: {first['intensity']} rain around {first['time'].strftime('%I:%M %p').lstrip('0')}")
        
        if afternoon_rain:
            first = afternoon_rain[0]
            if lang == 'it':
                message_parts.append(f"• ☀️ **{T['afternoon']}**: Pioggia {first['intensity']} verso le {first['time'].strftime('%H:%M')}")
            else:
                message_parts.append(f"• ☀️ **{T['afternoon']}**: {first['intensity']} rain around {first['time'].strftime('%I:%M %p').lstrip('0')}")
        
        if evening_rain:
            first = evening_rain[0]
            if lang == 'it':
                message_parts.append(f"• 🌇 **{T['evening']}**: Pioggia {first['intensity']} verso le {first['time'].strftime('%H:%M')}")
            else:
                message_parts.append(f"• 🌇 **{T['evening']}**: {first['intensity']} rain around {first['time'].strftime('%I:%M %p').lstrip('0')}")
        
        if night_rain:
            first = night_rain[0]
            if lang == 'it':
                message_parts.append(f"• 🌙 **{T['night']}**: Pioggia {first['intensity']} verso le {first['time'].strftime('%H:%M')}")
            else:
                message_parts.append(f"• 🌙 **{T['night']}**: {first['intensity']} rain around {first['time'].strftime('%I:%M %p').lstrip('0')}")
        
        # Total accumulation
        total_precip = sum(e['precipitation'] for e in rain_events)
        if lang == 'it':
            message_parts.append(f"*{T['total_expected']}: ~{total_precip:.1f} mm*")
        else:
            message_parts.append(f"*{T['total_expected']}: ~{total_precip:.1f} mm*")
        
        message_parts.append("")
    else:
        # No rain expected
        if lang == 'it':
            message_parts.append(f"✅ {T['no_significant_rain']} nelle prossime 24 ore")
        else:
            message_parts.append(f"✅ {T['no_significant_rain']} in the next 24 hours")
        message_parts.append("")
    
    # Current Conditions
    message_parts.append(f"**{T['current_conditions']}**")
    message_parts.append(f"{current_desc}")
    
    # Get values safely
    temp = current.get('temperature_2m', 'N/A')
    feels_like = current.get('apparent_temperature', 'N/A')
    wind = current.get('wind_speed_10m', 'N/A')
    humidity = current.get('relative_humidity_2m', 'N/A')
    
    if lang == 'it':
        message_parts.append(f"• Temperatura: **{temp}°C**")
        message_parts.append(f"• {T['feels_like']}: **{feels_like}°C**")
        message_parts.append(f"• {T['wind']}: **{wind} km/h**")
        if humidity != 'N/A':
            message_parts.append(f"• Umidità: **{humidity}%**")
    else:
        message_parts.append(f"• Temperature: **{temp}°C**")
        message_parts.append(f"• {T['feels_like']}: **{feels_like}°C**")
        message_parts.append(f"• {T['wind']}: **{wind} km/h**")
        if humidity != 'N/A':
            message_parts.append(f"• Humidity: **{humidity}%**")
    
    message_parts.append("")
    
    # 5-Day Forecast
    message_parts.append(f"**{T['forecast']}**")
    
    # Day names
    day_names_it = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
    day_names_en = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_names = day_names_it if lang == 'it' else day_names_en
    
    # Check if we have daily data
    daily_time = daily.get('time', [])
    daily_temp_min = daily.get('temperature_2m_min', [])
    daily_temp_max = daily.get('temperature_2m_max', [])
    daily_weather_code = daily.get('weather_code', [])
    
    if daily_time and daily_temp_min and daily_temp_max:
        days_to_show = min(5, len(daily_time))
        
        for i in range(days_to_show):
            date_str = daily_time[i]
            try:
                if 'T' in date_str:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            except Exception as e:
                date_obj = datetime.now() + timedelta(days=i)
            
            day_name = day_names[date_obj.weekday()]
            date_formatted = date_obj.strftime('%d/%m')
            
            day_code = daily_weather_code[i] if i < len(daily_weather_code) else 0
            day_icon = WEATHER_ICONS.get(day_code, '🌈')
            
            temp_min = daily_temp_min[i] if i < len(daily_temp_min) else 'N/A'
            temp_max = daily_temp_max[i] if i < len(daily_temp_max) else 'N/A'
            
            if i == 0:
                day_prefix = f"**{T['today']}:** "
            else:
                day_prefix = ""
            
            if temp_min != 'N/A' and temp_max != 'N/A':
                try:
                    if isinstance(temp_min, (int, float)) and isinstance(temp_max, (int, float)):
                        if lang == 'it':
                            temp_text = f"{T['min']} {temp_min:.0f}° → {T['max']} **{temp_max:.0f}°**"
                        else:
                            temp_text = f"{T['min']} {temp_min:.0f}° → {T['max']} **{temp_max:.0f}°**"
                    else:
                        temp_text = f"{temp_min}° / {temp_max}°"
                except:
                    temp_text = f"{temp_min}° / {temp_max}°"
            else:
                temp_text = f"{temp_min}° / {temp_max}°"
            
            message_parts.append(f"{day_prefix}{day_name} {date_formatted} {day_icon} {temp_text}")
    else:
        if lang == 'it':
            message_parts.append("⚠️ Previsioni giornaliere temporaneamente non disponibili")
        else:
            message_parts.append("⚠️ Daily forecast temporarily unavailable")
    
    message_parts.append("")
    message_parts.append(f"_{T['data_source']}_")
    
    return "\n".join(message_parts)

def get_complete_weather_report(city, lang='en'):
    """Main function to get complete weather report for a city"""
    lat, lon, region = get_coordinates(city)
    
    if lat is None:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_city']}
    
    weather_data = get_weather_forecast(lat, lon)
    
    if not weather_data:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_service']}
    
    message = create_weather_message(city, region, weather_data, lang)
    return {'success': True, 'message': message}

def get_24h_detailed_forecast(city, lang='en'):
    """Get detailed 24-hour forecast for a city."""
    lat, lon, region = get_coordinates(city)
    
    if lat is None:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_city']}
    
    weather_data = get_weather_forecast(lat, lon)
    
    if not weather_data:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_service']}
    
    message = create_24h_forecast_message(city, region, weather_data, lang)
    return {'success': True, 'message': message}

def get_detailed_rain_forecast(city, lang='en'):
    """Get detailed rain forecast for a city"""
    lat, lon, region = get_coordinates(city)
    
    if lat is None:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_city']}
    
    weather_data = get_weather_forecast(lat, lon)
    
    if not weather_data:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_service']}
    
    # Usa la funzione esistente per la pioggia
    from weather_service import create_detailed_rain_message
    message = create_detailed_rain_message(city, region, weather_data, lang)
    return {'success': True, 'message': message}