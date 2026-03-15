from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import hashlib
import os
import requests
import json
from datetime import datetime
from functools import wraps
from collections import defaultdict
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'farmwise-secret-key-2024')

# ---------------------------------------------------------------------------
# API Configuration
# ---------------------------------------------------------------------------

GROQ_API_KEY  = os.getenv('GROQ_API_KEY')
GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = "llama-3.3-70b-versatile"

OWM_API_KEY   = os.getenv('OWM_API_KEY', 'your-openweathermap-api-key-here')
OWM_CURRENT   = "https://api.openweathermap.org/data/2.5/weather"
OWM_FORECAST  = "https://api.openweathermap.org/data/2.5/forecast"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = sqlite3.connect('farmer.db')
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL,
                email    TEXT    UNIQUE NOT NULL,
                password TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                crop          TEXT    NOT NULL,
                location      TEXT    NOT NULL,
                weather_data  TEXT,
                ai_prediction TEXT,
                date          TEXT    NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# OpenWeatherMap helpers
# ---------------------------------------------------------------------------

def owm_desc_to_friendly(desc):
    mapping = {
        "clear sky":               "Clear sky ☀️",
        "few clouds":              "Few clouds 🌤️",
        "scattered clouds":        "Partly cloudy ⛅",
        "broken clouds":           "Mostly cloudy 🌥️",
        "overcast clouds":         "Overcast ☁️",
        "light rain":              "Light rain 🌦️",
        "moderate rain":           "Moderate rain 🌧️",
        "heavy intensity rain":    "Heavy rain 🌧️",
        "very heavy rain":         "Very heavy rain ⛈️",
        "light thunderstorm":      "Thunderstorm ⛈️",
        "thunderstorm":            "Thunderstorm ⛈️",
        "drizzle":                 "Drizzle 🌦️",
        "light intensity drizzle": "Light drizzle 🌦️",
        "mist":                    "Mist 🌫️",
        "fog":                     "Fog 🌫️",
        "haze":                    "Haze 🌫️",
        "light snow":              "Light snow ❄️",
        "snow":                    "Snow ❄️",
    }
    return mapping.get((desc or "").lower(), (desc or "N/A").title())


def fetch_weather(lat, lon):
    """
    Returns a normalised weather dict:
    {
      "current": { temp, humidity, precip, wind, condition },
      "daily":   [{ date, max_temp, min_temp, rain_prob, precip, wind, condition }, ...]
    }
    Returns None on failure.
    """
    if OWM_API_KEY in ('', 'your-openweathermap-api-key-here'):
        print("OWM_API_KEY not configured.")
        return None

    try:
        # Current weather
        cur_r = requests.get(
            OWM_CURRENT,
            params={"lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric"},
            timeout=10
        )
        cur_r.raise_for_status()
        cur = cur_r.json()

        current = {
            "temp":      round(cur["main"]["temp"], 1),
            "humidity":  cur["main"]["humidity"],
            "precip":    cur.get("rain", {}).get("1h", 0.0),
            "wind":      round(cur["wind"]["speed"] * 3.6, 1),  # m/s -> km/h
            "condition": owm_desc_to_friendly(
                             cur["weather"][0]["description"] if cur.get("weather") else ""),
        }

        # 5-day / 3-hour forecast
        fc_r = requests.get(
            OWM_FORECAST,
            params={"lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric", "cnt": 40},
            timeout=10
        )
        fc_r.raise_for_status()
        fc = fc_r.json()

        buckets = defaultdict(lambda: {
            "temps": [], "winds": [], "pops": [], "precip": 0.0, "descs": []
        })
        for item in fc.get("list", []):
            day = item["dt_txt"][:10]
            b   = buckets[day]
            b["temps"].append(item["main"]["temp"])
            b["winds"].append(item["wind"]["speed"] * 3.6)
            b["pops"].append(item.get("pop", 0) * 100)
            b["precip"] += item.get("rain", {}).get("3h", 0.0)
            if item.get("weather"):
                b["descs"].append(item["weather"][0]["description"])

        daily = []
        for day in sorted(buckets.keys()):
            if len(daily) >= 7:
                break
            b = buckets[day]
            if not b["temps"]:
                continue
            # Most common condition
            cnt = defaultdict(int)
            for d in b["descs"]: cnt[d] += 1
            top = max(cnt, key=cnt.get) if cnt else "N/A"
            daily.append({
                "date":      day,
                "max_temp":  round(max(b["temps"]), 1),
                "min_temp":  round(min(b["temps"]), 1),
                "rain_prob": round(max(b["pops"])),
                "precip":    round(b["precip"], 1),
                "wind":      round(max(b["winds"]), 1),
                "condition": owm_desc_to_friendly(top),
            })

        return {"current": current, "daily": daily}

    except requests.exceptions.HTTPError as e:
        print(f"OWM HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"OWM error: {e}")
        return None


def format_weather_for_ai(weather, location_name):
    if not weather:
        return "Weather data unavailable. Base prediction on crop type and location."

    c = weather.get("current", {})
    lines = [
        f"Location: {location_name}",
        "--- Current Weather ---",
        f"Temperature : {c.get('temp','N/A')} °C",
        f"Humidity    : {c.get('humidity','N/A')} %",
        f"Precipitation : {c.get('precip', 0)} mm",
        f"Wind Speed  : {c.get('wind','N/A')} km/h",
        f"Condition   : {c.get('condition','N/A')}",
        "",
        "--- Day-by-Day Forecast ---",
    ]
    for i, d in enumerate(weather.get("daily", []), 1):
        lines.append(
            f"Day {i} ({d['date']}): Max {d['max_temp']}°C / Min {d['min_temp']}°C, "
            f"Rain prob {d['rain_prob']}%, Precip {d['precip']} mm, "
            f"Wind {d['wind']} km/h, Condition: {d['condition']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Groq AI helpers
# ---------------------------------------------------------------------------

def call_groq(system_prompt, user_prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model":       GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens":  2048,
        "temperature": 0.45,
        "top_p":       0.9,
    }
    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        print(f"Groq HTTP {e.response.status_code}: {e.response.text[:300]}")
        return None
    except Exception as e:
        print(f"Groq error: {e}")
        return None


def get_pest_prediction(crop, location, weather_summary):
    system_prompt = (
        "You are FarmWise AI, a highly experienced agricultural advisor for Indian farmers. "
        "Analyse the crop, location, and real-time weather data to generate a pest risk report. "
        "Every crop has a UNIQUE pest profile — be specific to the crop provided. "
        "Use these exact section headers:\n\n"
        "## 🌾 Crop & Location Summary\n"
        "## ⚠️ Pest Attack Probability (Next 7 Days)\n"
        "## 🐛 Possible Pest Types\n"
        "## 🔴 Severity Level\n"
        "## 🕐 Best Time to Spray Pesticide\n"
        "## 🛡️ Preventive Measures\n"
        "## 📅 Weekly Advisory\n\n"
        "Write in simple language for farmers. Use bullet points within each section. "
        "Include specific pesticide/fungicide names and dosage where relevant."
    )
    user_prompt = (
        f"Crop: {crop}\nLocation: {location}\n\n"
        f"Live Weather:\n{weather_summary}\n\n"
        f"Generate a thorough 7-day pest prediction advisory."
    )
    return call_groq(system_prompt, user_prompt)


def get_government_schemes(farm_area, income, caste, gender, state, farmer_type):
    system_prompt = (
        "You are a Government Scheme Expert for Indian farmers. "
        "For the given farmer profile, dynamically identify ALL applicable central AND state government schemes. "
        "Do NOT use a hardcoded list — reason about eligibility from current Indian agricultural policies. "
        "For every eligible scheme output exactly:\n\n"
        "---SCHEME---\n"
        "Name: <official scheme name>\n"
        "Description: <2-3 sentence description>\n"
        "Benefits: <key benefits as comma-separated list>\n"
        "Eligibility Reason: <specific reason this farmer qualifies>\n"
        "Apply Link: <official government URL>\n"
        "---END---\n\n"
        "Identify 6–10 schemes. Include both central and state-specific schemes."
    )
    user_prompt = (
        f"Farmer Profile:\n"
        f"Farm Area: {farm_area} acres | Annual Income: ₹{income}\n"
        f"Caste: {caste} | Gender: {gender} | State: {state} | Type: {farmer_type}\n\n"
        f"Find all eligible schemes with official apply links."
    )
    return call_groq(system_prompt, user_prompt)


def parse_schemes(raw_text):
    if not raw_text:
        return []
    schemes = []
    for block in raw_text.split("---SCHEME---"):
        block = block.strip()
        if "---END---" not in block:
            continue
        block = block.split("---END---")[0].strip()
        s = {}
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("Name:"):
                s["name"]        = line[5:].strip()
            elif line.startswith("Description:"):
                s["description"] = line[12:].strip()
            elif line.startswith("Benefits:"):
                s["benefits"]    = line[9:].strip()
            elif line.startswith("Eligibility Reason:"):
                s["reason"]      = line[19:].strip()
            elif line.startswith("Apply Link:"):
                s["link"]        = line[11:].strip()
        if s.get("name"):
            schemes.append(s)
    return schemes


# ---------------------------------------------------------------------------
# Reverse geocoding (Nominatim — free, no key)
# ---------------------------------------------------------------------------

@app.route('/api/reverse-geocode')
def reverse_geocode():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return jsonify({'error': 'Missing lat/lon'}), 400
    try:
        resp = requests.get(
            f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json",
            headers={'User-Agent': 'FarmWise-App/2.0'},
            timeout=10
        )
        resp.raise_for_status()
        data  = resp.json()
        addr  = data.get("address", {})
        city  = (addr.get("city") or addr.get("town") or
                 addr.get("village") or addr.get("county") or "")
        state = addr.get("state", "")
        return jsonify({'location': f"{city}, {state}".strip(", "), 'city': city, 'state': state})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Weather API endpoint (returns normalised dict for JS preview)
# ---------------------------------------------------------------------------

@app.route('/api/weather')
def weather_api():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return jsonify({'error': 'Missing lat/lon'}), 400
    data = fetch_weather(lat, lon)
    if not data:
        return jsonify({'error': 'Weather unavailable — check OWM_API_KEY'}), 500
    return jsonify(data)


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not all([name, email, password, confirm]):
            flash('All fields are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        else:
            with get_db() as db:
                if db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
                    flash('Email already registered.', 'error')
                else:
                    db.execute(
                        'INSERT INTO users (name,email,password) VALUES (?,?,?)',
                        (name, email, hash_password(password))
                    )
                    flash('Account created! Please login.', 'success')
                    return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        with get_db() as db:
            user = db.execute(
                'SELECT * FROM users WHERE email=? AND password=?',
                (email, hash_password(password))
            ).fetchone()
        if user:
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(request.args.get('next', url_for('index')))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Pest Prediction
# ---------------------------------------------------------------------------

@app.route('/pest-prediction', methods=['GET', 'POST'])
@login_required
def pest_prediction():
    if request.method == 'POST':
        crop     = request.form.get('crop', '').strip()
        location = request.form.get('location', '').strip()
        lat      = request.form.get('lat', '').strip()
        lon      = request.form.get('lon', '').strip()

        if not crop or not location:
            flash('Please select a crop and detect your location.', 'error')
            return render_template('pest_prediction.html')

        weather_data    = fetch_weather(lat, lon) if lat and lon else None
        weather_summary = format_weather_for_ai(weather_data, location)
        ai_result       = get_pest_prediction(crop, location, weather_summary)

        if not ai_result:
            flash('AI prediction unavailable — check GROQ_API_KEY.', 'error')
            return render_template('pest_prediction.html')

        with get_db() as db:
            db.execute(
                'INSERT INTO predictions (user_id,crop,location,weather_data,ai_prediction,date) '
                'VALUES (?,?,?,?,?,?)',
                (session['user_id'], crop, location,
                 json.dumps(weather_data), ai_result,
                 datetime.now().strftime('%Y-%m-%d %H:%M'))
            )

        return render_template(
            'prediction_result.html',
            crop=crop, location=location,
            ai_prediction=ai_result, weather=weather_data,
        )

    return render_template('pest_prediction.html')


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@app.route('/history')
@login_required
def history():
    with get_db() as db:
        rows = db.execute(
            'SELECT * FROM predictions WHERE user_id=? ORDER BY date DESC',
            (session['user_id'],)
        ).fetchall()
    return render_template('history.html', predictions=rows)


@app.route('/history/<int:pred_id>')
@login_required
def history_detail(pred_id):
    with get_db() as db:
        row = db.execute(
            'SELECT * FROM predictions WHERE id=? AND user_id=?',
            (pred_id, session['user_id'])
        ).fetchone()
    if not row:
        flash('Prediction not found.', 'error')
        return redirect(url_for('history'))

    weather = None
    if row['weather_data']:
        try:
            weather = json.loads(row['weather_data'])
        except Exception:
            pass

    return render_template(
        'prediction_result.html',
        crop=row['crop'], location=row['location'],
        ai_prediction=row['ai_prediction'],
        weather=weather, from_history=True,
    )


# ---------------------------------------------------------------------------
# Government Schemes
# ---------------------------------------------------------------------------

@app.route('/schemes', methods=['GET', 'POST'])
@login_required
def schemes():
    if request.method == 'POST':
        farm_area   = request.form.get('farm_area', '').strip()
        income      = request.form.get('income', '').strip()
        caste       = request.form.get('caste', '').strip()
        gender      = request.form.get('gender', '').strip()
        state       = request.form.get('state', '').strip()
        farmer_type = request.form.get('farmer_type', '').strip()

        if not all([farm_area, income, caste, gender, state, farmer_type]):
            flash('Please fill in all fields.', 'error')
            return render_template('schemes.html')

        raw = get_government_schemes(farm_area, income, caste, gender, state, farmer_type)
        if not raw:
            flash('AI service unavailable — check GROQ_API_KEY.', 'error')
            return render_template('schemes.html')

        return render_template(
            'schemes_result.html',
            schemes=parse_schemes(raw),
            raw_text=raw,
            profile={
                "farm_area": farm_area, "income": income, "caste": caste,
                "gender": gender, "state": state, "farmer_type": farmer_type,
            }
        )

    return render_template('schemes.html')


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
