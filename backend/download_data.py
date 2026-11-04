"""Download REAL daily data for every station in stations.json into data/<slug>.csv
  rainfall  : Open-Meteo Historical Weather API (ERA5 reanalysis), 1940-present
  discharge : Open-Meteo Flood API (Copernicus GloFAS v4 reanalysis, m3/s), 1984-present
Free, no API key. Needs internet. Run: python download_data.py"""
import json, time, requests, pandas as pd
from pathlib import Path

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
SPANS = [(f"{y}-01-01", f"{min(y + 9, 2024)}-12-31") for y in range(1984, 2025, 10)]
Path("data").mkdir(exist_ok=True)

def get(url, params):
    for i in range(5):
        r = requests.get(url, params=params, timeout=90)
        if r.status_code == 200:
            return r.json()
        print("  retry", r.status_code, r.text[:120]); time.sleep(15 * (i + 1))
    r.raise_for_status()

for st in json.load(open("stations.json")):
    print("Downloading", st["name"])
    rain, dis = [], []
    for s, e in SPANS:
        p = {"latitude": st["lat"], "longitude": st["lon"], "start_date": s, "end_date": e, "timezone": "UTC"}
        a = get(ARCHIVE, {**p, "daily": "precipitation_sum"})["daily"]
        f = get(FLOOD, {**p, "daily": "river_discharge"})["daily"]
        rain.append(pd.DataFrame({"date": a["time"], "rain": a["precipitation_sum"]}))
        dis.append(pd.DataFrame({"date": f["time"], "discharge": f["river_discharge"]}))
        time.sleep(2)
    df = pd.concat(rain).merge(pd.concat(dis), on="date").dropna().sort_values("date")
    df.to_csv(f"data/{st['slug']}.csv", index=False)
    print(f"  {len(df)} days, discharge {df.discharge.min():.0f}..{df.discharge.max():.0f} m3/s")
    if len(df) < 5000 or df.discharge.median() < 1:
        print("  WARNING: little/odd data. Move lat/lon in stations.json onto the main river channel.")
