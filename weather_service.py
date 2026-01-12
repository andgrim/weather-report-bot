import requests
from datetime import datetime

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
        'error_service': "Weather service unavailable"
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
        'error_service': "Servizio meteo non disponibile"
    }
}

WEATHER_ICONS = {
    0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
    45: '🌫️', 48: '🌫️',
    51: '🌦️', 53: '🌦️', 55: '🌦️',
    61: '🌧️', 63: '🌧️', 65: '🌧️',
    71: '❄️', 73: '❄️', 75: '❄️',
    80: '🌦️', 81: '🌦️', 82: '🌦️',
    95: '⛈️', 96: '⛈️', 99: '⛈️'
}

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

def get_coordinates(city_name):
    """Convert city name to geographic coordinates - Using Italian language"""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=it"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get('results'):
            location = data['results'][0]
            return location['latitude'], location['longitude'], location.get('admin1', '')
    except Exception as e:
        print(f"Geocoding error: {e}")
    return None, None, None

def get_weather_forecast(lat, lon):
    """Get 5-day weather forecast with hourly data for rain prediction"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'current': 'temperature_2m,apparent_temperature,wind_speed_10m,weather_code',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min',
        'hourly': 'precipitation,precipitation_probability,weather_code',
        'timezone': 'auto',
        'forecast_days': 5
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Weather API error: {e}")
    return None

def create_weather_message(city, region, weather_data, lang='en'):
    """Format weather data into a user-friendly message with rain alert"""
    if not weather_data:
        return TRANSLATIONS[lang]['error_service']
    
    current = weather_data.get('current', {})
    daily = weather_data.get('daily', {})
    hourly = weather_data.get('hourly', {})
    T = TRANSLATIONS[lang]
    
    # Get rain start time
    rain_start = get_rain_start_time(hourly, lang)
    
    current_code = current.get('weather_code', 0)
    current_icon = WEATHER_ICONS.get(current_code, '🌈')
    current_desc = WEATHER_DESCRIPTIONS[lang].get(current_code, '')
    
    message_parts = []
    message_parts.append(f"**{current_icon} Meteo per {city}**" if lang == 'it' else f"**{current_icon} Weather for {city}**")
    
    if region:
        message_parts.append(f"*{region}*")
    
    update_time = current.get('time', 'N/A')[11:16] if current.get('time') else 'N/A'
    message_parts.append(f"*Aggiornato alle {update_time}*" if lang == 'it' else f"*Updated at {update_time}*")
    message_parts.append("")
    
    # Add rain alert if rain is coming
    if rain_start:
        rain_alert = {
            'it': f"⚠️ **Avviso Pioggia**: Inizierà a piovere verso le **{rain_start}**",
            'en': f"⚠️ **Rain Alert**: Rain will start around **{rain_start}**"
        }
        message_parts.append(rain_alert[lang])
        message_parts.append("")
    
    message_parts.append(f"**{T['current_conditions']}**")
    message_parts.append(f"{current_desc}")
    message_parts.append(f"• Temperatura: **{current.get('temperature_2m', 'N/A')}°C**" if lang == 'it' else f"• Temperature: **{current.get('temperature_2m', 'N/A')}°C**")
    message_parts.append(f"• {T['feels_like']}: **{current.get('apparent_temperature', 'N/A')}°C**")
    message_parts.append(f"• {T['wind']}: **{current.get('wind_speed_10m', 'N/A')} km/h**")
    message_parts.append("")
    
    message_parts.append(f"**{T['forecast']}**")
    
    day_names_it = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
    day_names_en = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_names = day_names_it if lang == 'it' else day_names_en
    
    for i in range(min(5, len(daily.get('time', [])))):
        date_str = daily['time'][i]
        date_obj = datetime.fromisoformat(date_str)
        
        day_name = day_names[date_obj.weekday()]
        date_formatted = date_obj.strftime('%d/%m')
        
        day_code = daily['weather_code'][i]
        day_icon = WEATHER_ICONS.get(day_code, '🌈')
        
        temp_min = daily['temperature_2m_min'][i]
        temp_max = daily['temperature_2m_max'][i]
        
        day_prefix = f"**{T['today']}:** " if i == 0 else ""
        temp_text = f"{T['min']} {temp_min:.0f}° → {T['max']} **{temp_max:.0f}°**"
        message_parts.append(f"{day_prefix}{day_name} {date_formatted} {day_icon} {temp_text}")
    
    message_parts.append("")
    message_parts.append(f"_{T['data_source']}_")
    
    return "\n".join(message_parts)

def get_complete_weather_report(city, lang='en'):
    """Main function to get weather report for a city"""
    lat, lon, region = get_coordinates(city)
    
    if lat is None:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_city']}
    
    weather_data = get_weather_forecast(lat, lon)
    
    if not weather_data:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_service']}
    
    message = create_weather_message(city, region, weather_data, lang)
    return {'success': True, 'message': message}

def get_rain_start_time(hourly_data, lang='en'):
    """Calculate when rain will start in the next 24 hours"""
    if not hourly_data or 'time' not in hourly_data or 'precipitation' not in hourly_data:
        return None
    
    from datetime import datetime, timedelta
    import pytz
    
    now = datetime.now(pytz.utc)
    times = hourly_data['time']
    precipitation = hourly_data['precipitation']
    rain_probability = hourly_data.get('precipitation_probability', [])
    
    for i in range(min(24, len(times))):
        try:
            hour_time = datetime.fromisoformat(times[i].replace('Z', '+00:00'))
            # Check if precipitation > 0.5mm and time is in future
            if (hour_time > now and 
                (precipitation[i] > 0.5 or 
                 (rain_probability and rain_probability[i] > 70))):
                
                # Format time in user's local timezone
                local_time = hour_time.astimezone(pytz.timezone('Europe/Rome'))
                
                # Return localized time string
                if lang == 'it':
                    return local_time.strftime("%H:%M")
                else:
                    return local_time.strftime("%I:%M %p").lstrip('0')
                
        except (ValueError, IndexError, TypeError) as e:
            continue
    
    return None