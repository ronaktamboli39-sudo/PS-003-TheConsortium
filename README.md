# 🌾 FarmWise AI — Smart Farming Assistant

> AI-powered pest prediction, government scheme discovery, and audio read-aloud for Indian farmers.
> Built with **Flask + Groq (Llama 3.3) + OpenWeatherMap**.

---

## ✨ Features

| Module | Tech |
|---|---|
| 🔐 Auth | Register / Login — SQLite + Flask sessions |
| 🐛 Pest Prediction | Groq Llama 3.3-70B analyses crop + live weather |
| 🌦️ Weather | OpenWeatherMap — current + 5-day forecast |
| 📍 Location | Browser Geolocation + Nominatim geocoding (free) |
| 🏛️ Gov Schemes | Groq AI dynamically finds eligible schemes |
| 🔊 Audio | Browser SpeechSynthesis API (English + Hindi) |
| 📋 History | All past predictions stored in SQLite |

---

## 🚀 Quick Start

### 1. Unzip & enter directory

```bash
cd farmer_app
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set environment variables

```bash
cp .env.example .env
```

Open `.env` and add your two API keys:

```env
SECRET_KEY=my-random-secret
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
OWM_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

### 5. Get your API keys (both are FREE)

#### Groq API key
1. Visit **https://console.groq.com**
2. Sign up → Dashboard → API Keys → Create Key
3. Copy the key starting with `gsk_`

#### OpenWeatherMap key
1. Visit **https://home.openweathermap.org/users/sign_up**
2. Sign up free → Go to **API keys** tab
3. Copy the default key (32-char hex string)
4. ⚠️ New keys activate within **10 minutes**

### 6. Initialise the database

```bash
python database.py
```

### 7. Run the app

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## 📁 Project Structure

```
farmer_app/
├── app.py                      ← Flask backend (Groq + OWM)
├── database.py                 ← SQLite init script
├── requirements.txt
├── .env.example                ← API key template
├── farmer.db                   ← SQLite DB (auto-created)
│
├── templates/
│   ├── base.html               ← Navbar, flash messages, footer
│   ├── index.html              ← Landing page
│   ├── login.html
│   ├── register.html
│   ├── pest_prediction.html    ← Crop grid + GPS location + weather preview
│   ├── prediction_result.html  ← Weather cards + AI output + 🔊 TTS
│   ├── history.html            ← Past predictions grid
│   ├── schemes.html            ← Farmer profile form
│   └── schemes_result.html     ← Scheme cards + 🔊 TTS
│
└── static/
    ├── css/style.css
    └── js/main.js
```

---

## 🔌 API Reference

### Groq  (AI engine)
| | |
|---|---|
| **URL** | `https://api.groq.com/openai/v1/chat/completions` |
| **Model** | `llama-3.3-70b-versatile` |
| **Free tier** | Yes — generous free limits |
| **Sign up** | https://console.groq.com |

### OpenWeatherMap  (weather)
| | |
|---|---|
| **Current weather** | `/data/2.5/weather` |
| **Forecast (5-day/3h)** | `/data/2.5/forecast` |
| **Free tier** | 60 req/min, 1M req/month |
| **Sign up** | https://home.openweathermap.org |

### Nominatim  (reverse geocoding)
- Completely free, no key needed
- Converts GPS → city/state name

### Browser SpeechSynthesis  (text-to-speech)
- Built into Chrome, Edge, Firefox, Safari
- No API key — works offline
- Supports English (en-IN) and Hindi (hi-IN)

---

## 🗄️ Database Schema

```sql
CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    email    TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL          -- SHA-256 hashed
);

CREATE TABLE predictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    crop          TEXT NOT NULL,
    location      TEXT NOT NULL,
    weather_data  TEXT,             -- JSON: normalised OWM response
    ai_prediction TEXT,            -- Groq AI markdown output
    date          TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 🔊 Audio Read-Aloud

Works via `window.speechSynthesis` — no external API needed:

- **▶ Play** — starts reading the AI advisory aloud
- **⏸ Pause / ▶ Resume** — pause and continue
- **⏹ Stop** — cancels speech
- **Language** — toggle between English and Hindi

Best voice support: **Chrome** or **Edge** on desktop.

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `AI unavailable` | Verify `GROQ_API_KEY` in `.env`; check https://console.groq.com |
| `Weather unavailable` | Verify `OWM_API_KEY`; new keys take up to 10 min to activate |
| `Location not detected` | Allow browser location permission; use HTTPS in production |
| `Audio silent` | Use Chrome/Edge; click page first (browsers require user gesture) |
| `No schemes found` | Fill all form fields; check GROQ_API_KEY |

---

## 🚢 Production

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

Set `SECRET_KEY` to a cryptographically random value in production.

---

*Built with ❤️ for Indian Farmers | Groq × OpenWeatherMap × Flask*
