"""
Weather Service Module with Enhanced Rain Alerts
Provides complete weather reports and detailed rain forecasts
"""

import requests
from datetime import datetime, timedelta
import pytz

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
        'accumulation': "Accumulation"
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
        'accumulation': "Accumulo"
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

def get_coordinates(city_name):
    """Convert city name to geographic coordinates using Italian language preference"""
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
            
            if precip >= 0.5 and prob >= 40:  # 0.5mm e 40% 
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

def get_extended_rain_forecast(hourly_data, lang='en'):
    """Get extended rain forecast for 48 hours (for detailed rain report)"""
    if not hourly_data or 'time' not in hourly_data or 'precipitation' not in hourly_data:
        return []
    
    now = datetime.now(pytz.utc)
    times = hourly_data['time']
    precipitation = hourly_data['precipitation']
    rain_probability = hourly_data.get('precipitation_probability', [])
    
    rain_events = []
    
    for i in range(min(96, len(times))):  # Check 96 hours (4 days)
        try:
            hour_time = datetime.fromisoformat(times[i].replace('Z', '+00:00')).replace(tzinfo=pytz.UTC)
            
            # Skip past hours
            if hour_time <= now:
                continue
                
            # Stop after 48 hours
            if hour_time > now + timedelta(hours=48):
                break
                
            precip = precipitation[i] if i < len(precipitation) else 0
            prob = rain_probability[i] if i < len(rain_probability) else 0
            
            # Significant rain: > 0.1mm
            if precip > 0.1:
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
                    'precipitation': precip,
                    'probability': prob,
                    'intensity': intensity,
                    'date': local_time.date()
                })
                
        except Exception:
            continue
    
    return rain_events

def create_weather_message(city, region, weather_data, lang='en'):
    """Format weather data into a user-friendly message with rain alert"""
    if not weather_data:
        return TRANSLATIONS[lang]['error_service']
    
    current = weather_data.get('current', {})
    daily = weather_data.get('daily', {})
    hourly = weather_data.get('hourly', {})
    T = TRANSLATIONS[lang]
    
    # DEBUG: Print data structure
    print(f"DEBUG create_weather_message for {city}:")
    print(f"  current keys: {list(current.keys())}")
    print(f"  daily keys: {list(daily.keys())}")
    
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
    
    # Update time - FIXED
    update_time = current.get('time', '')
    if update_time and isinstance(update_time, str) and len(update_time) > 10:
        try:
            # Example: "2026-01-14T18:00" -> "18:00"
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
    
    # Current Conditions - FIXED: Use get() with defaults
    message_parts.append(f"**{T['current_conditions']}**")
    message_parts.append(f"{current_desc}")
    
    # Get values safely
    temp = current.get('temperature_2m', 'N/A')
    feels_like = current.get('apparent_temperature', 'N/A')
    wind = current.get('wind_speed_10m', 'N/A')
    
    # DEBUG
    print(f"  Temperature values - temp: {temp}, feels: {feels_like}, wind: {wind}")
    
    if lang == 'it':
        message_parts.append(f"• Temperatura: **{temp}°C**")
        message_parts.append(f"• {T['feels_like']}: **{feels_like}°C**")
        message_parts.append(f"• {T['wind']}: **{wind} km/h**")
    else:
        message_parts.append(f"• Temperature: **{temp}°C**")
        message_parts.append(f"• {T['feels_like']}: **{feels_like}°C**")
        message_parts.append(f"• {T['wind']}: **{wind} km/h**")
    
    message_parts.append("")
    
    # 5-Day Forecast - FIXED: Check if data exists
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
                # Handle different date formats
                if 'T' in date_str:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    # Format: "2026-01-14"
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            except Exception as e:
                print(f"  Date parsing error: {e}")
                date_obj = datetime.now() + timedelta(days=i)
            
            day_name = day_names[date_obj.weekday()]
            date_formatted = date_obj.strftime('%d/%m')
            
            # Get weather code safely
            day_code = daily_weather_code[i] if i < len(daily_weather_code) else 0
            day_icon = WEATHER_ICONS.get(day_code, '🌈')
            
            # Get temperatures safely
            temp_min = daily_temp_min[i] if i < len(daily_temp_min) else 'N/A'
            temp_max = daily_temp_max[i] if i < len(daily_temp_max) else 'N/A'
            
            if i == 0:
                day_prefix = f"**{T['today']}:** "
            else:
                day_prefix = ""
            
            # Format temperature text
            if temp_min != 'N/A' and temp_max != 'N/A':
                try:
                    # Try to format as numbers
                    if isinstance(temp_min, (int, float)) and isinstance(temp_max, (int, float)):
                        if lang == 'it':
                            temp_text = f"{T['min']} {temp_min:.0f}° → {T['max']} **{temp_max:.0f}°**"
                        else:
                            temp_text = f"{T['min']} {temp_min:.0f}° → {T['max']} **{temp_max:.0f}°**"
                    else:
                        # Fallback to string
                        temp_text = f"{temp_min}° / {temp_max}°"
                except:
                    temp_text = f"{temp_min}° / {temp_max}°"
            else:
                temp_text = f"{temp_min}° / {temp_max}°"
            
            message_parts.append(f"{day_prefix}{day_name} {date_formatted} {day_icon} {temp_text}")
    else:
        # No daily data available
        if lang == 'it':
            message_parts.append("⚠️ Previsioni giornaliere temporaneamente non disponibili")
        else:
            message_parts.append("⚠️ Daily forecast temporarily unavailable")
    
    message_parts.append("")
    message_parts.append(f"_{T['data_source']}_")
    
    return "\n".join(message_parts)

def create_detailed_rain_message(city, region, weather_data, lang='en'):
    """Create detailed rain forecast message for 48 hours"""
    if not weather_data:
        return TRANSLATIONS[lang]['error_service']
    
    hourly = weather_data.get('hourly', {})
    T = TRANSLATIONS[lang]
    
    # Get extended rain forecast
    rain_events = get_extended_rain_forecast(hourly, lang)
    
    message_parts = []
    
    # Title
    if lang == 'it':
        message_parts.append(f"🌧️ **Previsione Pioggia per {city}**")
    else:
        message_parts.append(f"🌧️ **Rain Forecast for {city}**")
    
    if region:
        message_parts.append(f"*{region}*")
    
    message_parts.append("")
    
    if not rain_events:
        if lang == 'it':
            message_parts.append(f"✅ {T['no_significant_rain']} nei prossimi 48 ore.")
            message_parts.append("Al massimo qualche pioviggine o rovescio isolato.")
        else:
            message_parts.append(f"✅ {T['no_significant_rain']} in the next 48 hours.")
            message_parts.append("Only light drizzle or isolated showers possible.")
        
        message_parts.append("")
        message_parts.append(f"_{T['data_source']}_")
        return "\n".join(message_parts)
    
    # Group by date
    from collections import defaultdict
    rain_by_date = defaultdict(list)
    
    for event in rain_events:
        rain_by_date[event['date']].append(event)
    
    # Get today and tomorrow
    rome_tz = pytz.timezone('Europe/Rome')
    today = datetime.now(rome_tz).date()
    tomorrow = today + timedelta(days=1)
    
    # Today's rain
    if today in rain_by_date:
        today_events = rain_by_date[today]
        if lang == 'it':
            message_parts.append(f"**{T['today']} ({today.strftime('%d/%m')})**")
        else:
            message_parts.append(f"**{T['today']} ({today.strftime('%d/%m')})**")
        
        # Group by intensity and time period
        morning = [e for e in today_events if 6 <= e['time'].hour < 12]
        afternoon = [e for e in today_events if 12 <= e['time'].hour < 18]
        evening = [e for e in today_events if 18 <= e['time'].hour < 24]
        night = [e for e in today_events if e['time'].hour < 6]
        
        if morning:
            total = sum(e['precipitation'] for e in morning)
            if lang == 'it':
                message_parts.append(f"• **Mattina**: Pioggia {morning[0]['intensity']} (~{total:.1f} mm)")
            else:
                message_parts.append(f"• **Morning**: {morning[0]['intensity']} rain (~{total:.1f} mm)")
        
        if afternoon:
            total = sum(e['precipitation'] for e in afternoon)
            if lang == 'it':
                message_parts.append(f"• **Pomeriggio**: Pioggia {afternoon[0]['intensity']} (~{total:.1f} mm)")
            else:
                message_parts.append(f"• **Afternoon**: {afternoon[0]['intensity']} rain (~{total:.1f} mm)")
        
        if evening:
            total = sum(e['precipitation'] for e in evening)
            if lang == 'it':
                message_parts.append(f"• **Sera**: Pioggia {evening[0]['intensity']} (~{total:.1f} mm)")
            else:
                message_parts.append(f"• **Evening**: {evening[0]['intensity']} rain (~{total:.1f} mm)")
        
        if night:
            total = sum(e['precipitation'] for e in night)
            if lang == 'it':
                message_parts.append(f"• **Notte**: Pioggia {night[0]['intensity']} (~{total:.1f} mm)")
            else:
                message_parts.append(f"• **Night**: {night[0]['intensity']} rain (~{total:.1f} mm)")
        
        today_total = sum(e['precipitation'] for e in today_events)
        if lang == 'it':
            message_parts.append(f"  *Totale oggi: {today_total:.1f} mm*")
        else:
            message_parts.append(f"  *Today total: {today_total:.1f} mm*")
        
        message_parts.append("")
    
    # Tomorrow's rain
    if tomorrow in rain_by_date:
        tomorrow_events = rain_by_date[tomorrow]
        if lang == 'it':
            message_parts.append(f"**{T['tomorrow']} ({tomorrow.strftime('%d/%m')})**")
        else:
            message_parts.append(f"**{T['tomorrow']} ({tomorrow.strftime('%d/%m')})**")
        
        # Group by intensity
        morning = [e for e in tomorrow_events if 6 <= e['time'].hour < 12]
        afternoon = [e for e in tomorrow_events if 12 <= e['time'].hour < 18]
        evening = [e for e in tomorrow_events if 18 <= e['time'].hour < 24]
        night = [e for e in tomorrow_events if e['time'].hour < 6]
        
        if morning:
            total = sum(e['precipitation'] for e in morning)
            if lang == 'it':
                message_parts.append(f"• **Mattina**: Pioggia {morning[0]['intensity']} (~{total:.1f} mm)")
            else:
                message_parts.append(f"• **Morning**: {morning[0]['intensity']} rain (~{total:.1f} mm)")
        
        if afternoon:
            total = sum(e['precipitation'] for e in afternoon)
            if lang == 'it':
                message_parts.append(f"• **Pomeriggio**: Pioggia {afternoon[0]['intensity']} (~{total:.1f} mm)")
            else:
                message_parts.append(f"• **Afternoon**: {afternoon[0]['intensity']} rain (~{total:.1f} mm)")
        
        if evening:
            total = sum(e['precipitation'] for e in evening)
            if lang == 'it':
                message_parts.append(f"• **Sera**: Pioggia {evening[0]['intensity']} (~{total:.1f} mm)")
            else:
                message_parts.append(f"• **Evening**: {evening[0]['intensity']} rain (~{total:.1f} mm)")
        
        if night:
            total = sum(e['precipitation'] for e in night)
            if lang == 'it':
                message_parts.append(f"• **Notte**: Pioggia {night[0]['intensity']} (~{total:.1f} mm)")
            else:
                message_parts.append(f"• **Night**: {night[0]['intensity']} rain (~{total:.1f} mm)")
        
        tomorrow_total = sum(e['precipitation'] for e in tomorrow_events)
        if lang == 'it':
            message_parts.append(f"  *Totale domani: {tomorrow_total:.1f} mm*")
        else:
            message_parts.append(f"  *Tomorrow total: {tomorrow_total:.1f} mm*")
        
        message_parts.append("")
    
    # Total accumulation
    total_precip = sum(e['precipitation'] for e in rain_events)
    if lang == 'it':
        message_parts.append(f"**{T['accumulation']} totale (48h): {total_precip:.1f} mm**")
    else:
        message_parts.append(f"**Total {T['accumulation'].lower()} (48h): {total_precip:.1f} mm**")
    
    message_parts.append("")
    
    # Rain probability info
    if rain_events:
        max_prob = max(e['probability'] for e in rain_events)
        if lang == 'it':
            message_parts.append(f"*Probabilità massima pioggia: {max_prob}%*")
        else:
            message_parts.append(f"*Maximum rain probability: {max_prob}%*")
    
    message_parts.append("")
    message_parts.append(f"_{T['data_source']}_")
    
    # Tips based on rain intensity
    if total_precip > 15:
        if lang == 'it':
            message_parts.append("")
            message_parts.append("💡 **Consiglio**: Pioggia abbondante prevista. Considera di rimandare attività all'aperto.")
        else:
            message_parts.append("")
            message_parts.append("💡 **Tip**: Heavy rain expected. Consider postponing outdoor activities.")
    
    return "\n".join(message_parts)

def get_complete_weather_report(city, lang='en'):
    """Main function to get complete weather report for a city"""
    print(f"🌍 Getting weather for: {city}")
    
    lat, lon, region = get_coordinates(city)
    
    if lat is None:
        print(f"❌ Coordinates not found for: {city}")
        return {'success': False, 'message': TRANSLATIONS[lang]['error_city']}
    
    print(f"📍 Coordinates: {lat}, {lon}, Region: {region}")
    
    weather_data = get_weather_forecast(lat, lon)
    
    if not weather_data:
        print(f"❌ No weather data returned for: {city}")
        return {'success': False, 'message': TRANSLATIONS[lang]['error_service']}
    
    print(f"✅ Weather data received for: {city}")
    
    message = create_weather_message(city, region, weather_data, lang)
    return {'success': True, 'message': message}

def get_detailed_rain_forecast(city, lang='en'):
    """Get detailed rain forecast for a city"""
    lat, lon, region = get_coordinates(city)
    
    if lat is None:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_city']}
    
    weather_data = get_weather_forecast(lat, lon)
    
    if not weather_data:
        return {'success': False, 'message': TRANSLATIONS[lang]['error_service']}
    
    message = create_detailed_rain_message(city, region, weather_data, lang)
    return {'success': True, 'message': message}