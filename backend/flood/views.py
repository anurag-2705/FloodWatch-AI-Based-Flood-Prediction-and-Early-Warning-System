import json
from functools import lru_cache
from pathlib import Path
import pandas as pd
from django.conf import settings
from rest_framework import viewsets, generics
from rest_framework.decorators import api_view
from rest_framework.response import Response
from . import ml
from .models import Station, Alert
from .serializers import *

class StationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Station.objects.all(); serializer_class = StationSerializer

class AlertList(generics.ListAPIView):
    queryset = Alert.objects.all()[:50]; serializer_class = AlertSerializer

class Subscribe(generics.CreateAPIView):
    serializer_class = SubscriberSerializer

@api_view(["GET"])
def forecast(request, pk):
    st = Station.objects.get(pk=pk)
    return Response({
        "station": StationSerializer(st).data,
        "readings": ReadingSerializer(st.readings.order_by("-date")[:60][::-1], many=True).data,
        "predictions": PredictionSerializer(st.predictions.all()[:24][::-1], many=True).data})

@api_view(["POST"])
def what_if(request):
    """Body: {discharge, rain_3d, rain_next3, danger}. Past rain spread over the last 3 days; rain_next3 = forecast rain."""
    d = request.data
    q, rain, thr, nxt = float(d["discharge"]), float(d["rain_3d"]), float(d["danger"]), float(d.get("rain_next3", 0))
    out, risk, p = ml.predict([0] * 11 + [rain / 3] * 3, [q] * 14, thr, [nxt / 3] * 3)
    return Response({"predicted_discharge": round(out), "risk_level": risk, "probability": round(p, 3)})

# ---------------- Replay: re-run the model on real past dates ----------------
@lru_cache(maxsize=16)
def _series(name):
    base = Path(settings.BASE_DIR)
    slug = next(x["slug"] for x in json.load(open(base / "stations.json")) if x["name"] == name)
    return pd.read_csv(base / "data" / f"{slug}.csv", parse_dates=["date"])

def _label(ratio):
    return "HIGH" if ratio >= ml.HIGH_AT else "MEDIUM" if ratio >= ml.MEDIUM_AT else "LOW"

def _replay(st, df, i):
    """Forecast issued on day i, using only data up to i (plus the actual next-3-day rain as a 'perfect rain forecast')."""
    W, H = ml.WINDOW, ml.HORIZON
    win, fut = df.iloc[i - W + 1: i + 1], df.iloc[i + 1: i + 1 + H]
    q, risk, p = ml.predict(win.rain.tolist(), win.discharge.tolist(), st.danger_level, fut.rain.tolist())
    rows = pd.concat([win, fut])
    return {"issue_date": str(df.date[i].date()), "forecast_date": str(fut.date.iloc[-1].date()),
            "series": [{"date": str(r.date.date()), "discharge": float(r.discharge)} for r in rows.itertuples()],
            "threshold": st.danger_level, "predicted_discharge": q, "predicted_risk": risk, "probability": p,
            "actual_discharge": float(fut.discharge.iloc[-1]), "actual_risk": _label(float(fut.discharge.max()) / st.danger_level)}

@api_view(["GET"])
def replay(request, pk):
    st, df = Station.objects.get(pk=pk), None
    df = _series(st.name)
    try:
        hits = df.index[df.date == pd.Timestamp(request.query_params.get("date", ""))]
    except Exception:
        return Response({"error": "Use a date like 2019-08-14."}, status=400)
    if not len(hits) or hits[0] < ml.WINDOW - 1 or hits[0] + ml.HORIZON >= len(df):
        return Response({"error": "No data for that date. Valid range is 1984 to 2024."}, status=400)
    return Response(_replay(st, df, int(hits[0])))

@api_view(["GET"])
def replay_events(request, pk):
    """Biggest past flood peaks (discharge >= threshold) with the forecast the model would have issued 3 days before."""
    st = Station.objects.get(pk=pk); df = _series(st.name); ev, last = [], None
    for r in df[df.discharge >= st.danger_level].itertuples():
        if last is None or (r.date - last).days > 30: ev.append(r.Index)
        elif r.discharge > df.discharge[ev[-1]]: ev[-1] = r.Index
        last = r.date
    cut = pd.Timestamp("2015-01-01"); big = lambda L: sorted(L, key=lambda i: -df.discharge[i])
    pick = big([i for i in ev if df.date[i] >= cut])[:8] + big([i for i in ev if df.date[i] < cut])[:4]
    out = []
    for pk_i in pick:
        i = pk_i - ml.HORIZON
        if i < ml.WINDOW - 1: continue
        r = _replay(st, df, i)
        out.append({"peak_date": str(df.date[pk_i].date()), "peak_discharge": round(float(df.discharge[pk_i])), "issue_date": r["issue_date"],
                    "predicted": r["predicted_risk"], "actual": r["actual_risk"], "unseen": bool(df.date[i] >= cut)})
    return Response({"events": sorted(out, key=lambda e: e["issue_date"], reverse=True)})
