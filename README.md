# FloodWatch: AI-based flood prediction and early warning (real data)

Stack: Django + DRF + PostgreSQL, Celery/Redis, scikit-learn + TensorFlow, React (Vite).

## Data (real, free, no API key)
- Rainfall: Open-Meteo Historical Weather API (ERA5 reanalysis), daily.
- River discharge: Open-Meteo Flood API (Copernicus GloFAS v4 reanalysis, m3/s), daily, 1984-2024.
- 6 stations on major Indian rivers are listed in `backend/stations.json`. Edit lat/lon to add or move stations.

## Run
```bash
cd backend && pip install -r requirements.txt
python download_data.py      # ~40 years x 6 stations -> data/*.csv  (needs internet, a few minutes)
python train.py              # prints test metrics vs a persistence baseline; saves ml_models/
cd .. && docker compose up --build
docker compose exec api python manage.py sync_data   # create stations, pull latest real data, predict
```
Dashboard: http://localhost:5173   API: http://localhost:8000/api/

## How it works
- Flood threshold per station = 95th percentile of historical discharge (HIGH >= 100% of it, MEDIUM >= 75%).
- LSTM: last 14 days of rain + discharge -> discharge 3 days ahead. RandomForest uses that forecast + rain totals -> LOW/MEDIUM/HIGH.
- Chronological split (train < 2015, test >= 2015). `train.py` compares against a persistence baseline; report that honestly.
- Celery beat runs daily at 06:00 UTC: fetch latest data, predict, create alerts, notify subscribers.

## Limitations (state these in your report)
- GloFAS discharge is a *modelled* reanalysis, not gauge measurements; labels are "high relative to history", not officially declared floods.
- Rain is taken at the station point, not averaged over the upstream catchment.
- Daily resolution: no sub-daily warnings. SMS is a stub; email prints to console until SMTP is set.
- For validation against real flood events, compare predictions with Dartmouth Flood Observatory / CWC records and, if you can get them, real gauge data.
