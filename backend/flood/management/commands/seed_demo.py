import numpy as np
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from flood.models import Station, Reading
from flood.tasks import run_for_station

STATIONS = [("Ganga Ghat", "Ganga", 25.31, 83.01, 7.0), ("Yamuna Barrage", "Yamuna", 28.66, 77.25, 6.0),
            ("Pandu Gauge", "Brahmaputra", 26.18, 91.70, 8.0)]

class Command(BaseCommand):
    help = "Create demo stations with 72 h of synthetic readings and a first prediction"
    def handle(self, *a, **o):
        rng = np.random.default_rng(1); now = timezone.now().replace(minute=0, second=0, microsecond=0)
        for name, river, lat, lon, danger in STATIONS:
            st, _ = Station.objects.get_or_create(name=name, defaults=dict(river=river, lat=lat, lon=lon, danger_level=danger))
            st.readings.all().delete(); k = danger / 5; lvl = 2 * k
            storm = rng.integers(30, 60)  # rain event near the end of the window
            for h in range(72, 0, -1):
                rain = float(rng.gamma(2, 4) if storm - 12 < 72 - h < storm else rng.random() < 0.1)
                lvl = (0.97 * lvl / k + 0.06 + 0.06 * rain) * k
                Reading.objects.create(station=st, timestamp=now - timedelta(hours=h), rainfall=rain, water_level=lvl)
            run_for_station(st, ingest=False)
            self.stdout.write(f"seeded {name}")
