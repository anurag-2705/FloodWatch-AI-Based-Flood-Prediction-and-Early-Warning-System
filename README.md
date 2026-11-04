# FloodWatch: AI-Based Flood Prediction and Early Warning System

FloodWatch forecasts river flood risk **3 days ahead** and warns subscribers by email and SMS. It combines 40 years of real rainfall and river-discharge data with two machine-learning models, a Django REST API, a React dashboard and a daily automated alert pipeline.

> **Status:** working prototype for study and demonstration. It is **not** an official warning service. See [Limitations](#limitations).

---

## Features

- **3-day river discharge forecast** from an LSTM (TensorFlow), using 14 days of history plus the rain forecast for the next 3 days.
- **Risk classification** (Low / Medium / High) from a Random Forest (scikit-learn), relative to each river's own flood threshold.
- **Live dashboard** (React): station map coloured by risk, observed-vs-forecast chart, alerts feed.
- **Replay past floods:** pick any date from 1984 to 2024, hide everything after it, and compare the model's forecast with what actually happened.
- **What-if simulator:** enter river flow and rainfall to see the predicted risk.
- **Real alerts:** email (SMTP) and SMS (Twilio) with change detection, 24-hour reminders and "all clear" messages.
- **Automated daily pipeline:** Celery fetches new data, predicts and notifies at 06:00 UTC.
- **One-command deployment** with Docker Compose.

## Architecture

```
Open-Meteo (ERA5 rain, GloFAS discharge, rain forecast)
        |
        v
download_data.py --> data/*.csv --> train.py --> ml_models/ (LSTM + Random Forest)
                                                        |
Celery beat (daily) --> tasks.py --fetch--> PostgreSQL <--+-- Django REST API <--> React dashboard
                           |                                   
                           +--> predict --> alerts --> Email (SMTP) / SMS (Twilio)
```

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 to 3.13 |
| ML | TensorFlow / Keras (LSTM), scikit-learn (Random Forest) |
| Backend | Django, Django REST Framework |
| Database | PostgreSQL |
| Scheduling | Celery, Redis |
| Frontend | React (Vite), Leaflet, Recharts |
| Deployment | Docker, Docker Compose |

## Data sources (free, no API key)

| Data | Source |
|---|---|
| Daily rainfall (history) | Open-Meteo Historical Weather API (ERA5 reanalysis) |
| Daily river discharge, m³/s | Open-Meteo Flood API (Copernicus GloFAS v4 reanalysis), 1984 to 2024 |
| Rain forecast (live) | Open-Meteo Forecast API |

Six stations are configured in `backend/stations.json`: Ganga at Varanasi, Yamuna at Delhi, Brahmaputra at Guwahati, Godavari at Rajahmundry, Krishna at Vijayawada and Mahanadi at Cuttack.

## How the models work

1. **Flood threshold per station** = the 95th percentile of that river's historical discharge. High risk means discharge reaches 100% of it, and Medium means 75%.
2. **LSTM:** inputs are the last 14 days of rain and discharge (scaled by the threshold) and the rain over the next 3 days. Output is the discharge 3 days ahead.
3. **Random Forest:** inputs are the LSTM forecast, rain totals (3, 7 and 14 days back and 3 days ahead), current discharge and its recent change. Output is Low, Medium or High, with class weights to handle rare floods.
4. **Evaluation:** chronological split (train before 2015, test from 2015 on) so the model never sees the future. `train.py` prints per-class metrics, PR-AUC for High risk, and a **persistence baseline** (risk from today's discharge) for comparison.

Training uses actual later rainfall as a stand-in for a perfect rain forecast. The live system uses Open-Meteo's real forecast, which is less accurate.

## Project structure

```
floodwatch/
├── docker-compose.yml
├── .env.example               # template for email / SMS credentials
├── backend/
│   ├── stations.json          # station list (edit to add rivers)
│   ├── download_data.py       # downloads real data to data/
│   ├── train.py               # trains models, saves to ml_models/
│   ├── requirements.txt
│   ├── config/                # Django settings, URLs, Celery schedule
│   └── flood/
│       ├── models.py          # Station, Reading, Prediction, Alert, Subscriber
│       ├── ml.py              # model loading and prediction
│       ├── tasks.py           # daily job, alert delivery
│       ├── views.py, urls.py, serializers.py   # REST API (incl. replay)
│       └── management/commands/   # sync_data, send_test_alert
└── frontend/
    └── src/App.jsx            # dashboard
```

## Getting started

### Prerequisites

- **Python 3.11 to 3.13**
- **Docker Desktop** (running)
- An internet connection

### 1. Create a Python environment and install packages

```bash
cd backend
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Windows (cmd):         .venv\Scripts\activate
# Mac/Linux:             source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Download the real data

```bash
python download_data.py
```

This creates `backend/data/*.csv` (a few minutes). If a station prints a warning about thin or odd data, move its `lat` / `lon` in `stations.json` onto the main river channel and run again.

### 3. Train the models

```bash
python train.py
```

Takes about 5 to 15 minutes. It saves `lstm.keras`, `rf.joblib` and `thresholds.json` to `backend/ml_models/`. Keep the printed metrics for your report.

### 4. Start the system

From the project root, with Docker Desktop running:

```bash
cd ..
docker compose up --build
```

Wait until the API log shows it is running on port 8000.

### 5. Load stations and first predictions

In a second terminal:

```bash
docker compose exec api python manage.py sync_data
```

### 6. Open the app

| What | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| API | http://localhost:8000/api/stations/ |
| Admin (optional) | http://localhost:8000/admin, after `docker compose exec api python manage.py createsuperuser` |

## Configuring alerts

Copy `.env.example` to `.env` (next to `docker-compose.yml`) and fill in what you have:

| Variable | Purpose |
|---|---|
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP login. For Gmail, use an **App Password** (needs 2-step verification). |
| `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM` | Twilio account and sender number (E.164 format, e.g. `+1415...`). |

Leave a variable blank to disable that channel. Without credentials, messages are printed in the API log instead of being sent. Restart Docker after editing `.env`, then test:

```bash
docker compose exec api python manage.py send_test_alert --email you@example.com --phone +919876543210
```

Never commit `.env`. Twilio trial accounts can only text verified numbers, and sending SMS to some countries needs extra sender registration.

## API reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/stations/` | Stations with their latest prediction |
| GET | `/api/forecast/<id>/` | Recent readings and predictions for a station |
| POST | `/api/predict/` | What-if: body `{discharge, rain_3d, rain_next3, danger}` |
| GET | `/api/alerts/` | Latest alerts |
| POST | `/api/subscribe/` | Subscribe: `{name, email, phone, station, min_risk}` (phone as `+<country><number>`) |
| GET | `/api/replay/<id>/?date=YYYY-MM-DD` | Replay the forecast issued on a past date |
| GET | `/api/replay/events/<id>/` | Biggest past flood peaks with the forecast made 3 days earlier |

## Everyday tasks

| I want to... | Do this |
|---|---|
| Add a station | Add it to `backend/stations.json`, then run `download_data.py`, `train.py`, and `docker compose exec api python manage.py sync_data` |
| Run the daily job now | `docker compose exec api python manage.py shell -c "from flood.tasks import run_cycle; run_cycle()"` |
| Retrain after changes | `python train.py` in the venv, then `docker compose restart api worker` |
| See logs | `docker compose logs api` (or `worker`, `beat`, `frontend`) |
| Stop everything | `docker compose down` |

Edits to `App.jsx`, `views.py`, `urls.py` and `serializers.py` reload automatically. After editing `tasks.py`, run `docker compose restart worker beat`. After editing `models.py`, run `docker compose restart api`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `failed to connect to the docker API` | Open Docker Desktop and wait for "Engine running". |
| `service "api" is not running` | Run `docker compose logs api` and read the last lines. `docker compose up` must stay running in the first terminal. |
| Dashboard empty | Run `sync_data` (step 5). |
| `pip install` fails on TensorFlow | Use Python 3.11 to 3.13 and a fresh virtual environment. |
| Model file not found | Run `python train.py` first. |
| Replay says no data | Valid dates are 1984 to 2024, and `backend/data/*.csv` must exist. |
| All stations show Low | Normal outside the monsoon season. Use the what-if simulator or the Replay page to see Medium and High cases. |

## Limitations

- **GloFAS discharge is modelled data, not gauge readings.** "High" means unusually high compared with the river's own history, not an officially declared flood.
- Rainfall is taken at a single point, not averaged over the whole upstream catchment.
- Data and forecasts are daily, so there are no sub-daily warnings.
- Training assumes a perfect rain forecast. Live accuracy will be lower.
- Station coordinates are approximate and should be checked against the river channel.
- Do not use this system for real safety decisions without checking official sources (Central Water Commission, IMD).

## Roadmap

- Train on government gauge data (India-WRIS, CWC) alongside GloFAS.
- Catchment-averaged rainfall and longer forecast horizons with uncertainty ranges.
- SHAP explanations and per-station evaluation reports.
- Location-based alerts with PostGIS, multilingual messages, user accounts and API authentication.
- Automated tests, model version tracking and cloud deployment with HTTPS.

## Acknowledgements

Data from [Open-Meteo](https://open-meteo.com) (ERA5 and Copernicus GloFAS). Maps by OpenStreetMap contributors.

## License

Add a license of your choice (for example MIT) before publishing.
