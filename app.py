from flask import Flask, jsonify, request, send_from_directory
import requests
from datetime import datetime, timedelta
import sqlite3
from flask_cors import CORS
import os

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
API_KEY = "fqwierh32ury87328732"  # Replace with your actual API key
DB_NAME = "weather.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS historical_data
                 (location text, date text, temperature real, conditions text)''')
    conn.commit()
    conn.close()

def get_location_key(location_name):
    """Get location key for a city name"""
    try:
        search_url = f"http://dataservice.accuweather.com/locations/v1/cities/search?apikey={API_KEY}&q={location_name}"
        response = requests.get(search_url).json()
        if response:
            return response[0]['Key']
        return None
    except Exception as e:
        print(f"Error getting location key: {e}")
        return None

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    return "Not Found", 404

@app.route('/api/current', methods=['GET'])
def get_current_weather():
    location = request.args.get('location', 'Pune')  # Default to Pune
    
    try:
        location_key = get_location_key(location)
        if not location_key:
            return jsonify({
                'success': False,
                'message': 'Location not found'
            }), 404
        
        # Get current conditions
        current_url = f"http://dataservice.accuweather.com/currentconditions/v1/{location_key}?apikey={API_KEY}&details=true"
        current_resp = requests.get(current_url).json()[0]
        
        # Store in database
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO historical_data VALUES (?, ?, ?, ?)",
                  (location, 
                   datetime.now().strftime('%Y-%m-%d'),
                   current_resp['Temperature']['Metric']['Value'],
                   current_resp['WeatherText']))
        conn.commit()
        conn.close()
        
        return jsonify({
            'location': location,
            'temperature': current_resp['Temperature']['Metric']['Value'],
            'unit': 'C',
            'conditions': current_resp['WeatherText'],
            'icon': current_resp['WeatherIcon'],
            'success': True
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch current weather data'
        }), 500

@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    location = request.args.get('location', 'Pune')  # Default to Pune
    
    try:
        location_key = get_location_key(location)
        if not location_key:
            return jsonify({
                'success': False,
                'message': 'Location not found'
            }), 404
        
        # Get 5-day forecast
        forecast_url = f"http://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}?apikey={API_KEY}&metric=true"
        forecast_resp = requests.get(forecast_url).json()
        
        forecast = []
        for day in forecast_resp['DailyForecasts']:
            forecast.append({
                'date': day['Date'][:10],
                'min_temp': day['Temperature']['Minimum']['Value'],
                'max_temp': day['Temperature']['Maximum']['Value'],
                'day_icon': day['Day']['Icon'],
                'night_icon': day['Night']['Icon'],
                'day_conditions': day['Day']['IconPhrase'],
                'night_conditions': day['Night']['IconPhrase']
            })
        
        return jsonify({
            'success': True,
            'forecast': forecast,
            'location': location
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch forecast data'
        }), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    location = request.args.get('location', 'Pune')  # Default to Pune
    days = int(request.args.get('days', 30))
    
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            SELECT date, temperature, conditions 
            FROM historical_data 
            WHERE location=? 
            ORDER BY date DESC 
            LIMIT ?
        """, (location, days))
        data = c.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'history': [{
                'date': row[0], 
                'temperature': row[1], 
                'conditions': row[2]
            } for row in data]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch historical data'
        }), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)