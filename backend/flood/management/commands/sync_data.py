import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from flood.models import Station
from flood.tasks import run_for_station
from flood.ml import MODEL_DIR

class Command(BaseCommand):
    help = "Create stations from stations.json (thresholds from training), pull recent real data, run predictions"
    def handle(self, *a, **o):
        thr = json.load(open(MODEL_DIR / "thresholds.json"))
        for s in json.load(open(Path(settings.BASE_DIR) / "stations.json")):
            st, _ = Station.objects.update_or_create(name=s["name"], defaults=dict(
                river=s["river"], lat=s["lat"], lon=s["lon"], danger_level=thr[s["name"]]))
            p = run_for_station(st)
            self.stdout.write(f"{st.name}: {p.risk_level if p else 'not enough data'}")
