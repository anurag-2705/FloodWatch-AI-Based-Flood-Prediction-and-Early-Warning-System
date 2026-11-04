import logging, os, requests
from datetime import date, timedelta
from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from . import ml
from .models import Station, Reading, Prediction, Alert

log = logging.getLogger(__name__)
FORECAST = "https://api.open-meteo.com/v1/forecast"
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
PAST_DAYS = 45

def fetch_recent(st):
    """Returns (observed {date: (rain, discharge)}, rain_by_date incl. forecast days)."""
    p = {"latitude": st.lat, "longitude": st.lon, "past_days": PAST_DAYS, "timezone": "UTC"}
    rain = requests.get(FORECAST, params={**p, "forecast_days": ml.HORIZON + 1, "daily": "precipitation_sum"}, timeout=30).json()["daily"]
    dis = requests.get(FLOOD, params={**p, "forecast_days": 0, "daily": "river_discharge"}, timeout=30).json()["daily"]
    r, d, today = dict(zip(rain["time"], rain["precipitation_sum"])), dict(zip(dis["time"], dis["river_discharge"])), date.today().isoformat()
    obs = {k: (r[k], d[k]) for k in sorted(r) if k in d and k < today and r[k] is not None and d[k] is not None}
    return obs, r

# ---------- delivery ----------
def send_email(to, subject, body):
    try:
        send_mail(subject, body, None, [to], fail_silently=False); return True
    except Exception as e:
        log.error("Email to %s failed: %s", to, e); return False

def send_sms(to, body):
    """Twilio REST API. Without TWILIO_* env vars it only prints (stub)."""
    sid = os.environ.get("TWILIO_SID")
    if not sid:
        print(f"[SMS not configured] to {to}: {body}"); return False
    try:
        r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", timeout=20,
                          auth=(sid, os.environ["TWILIO_TOKEN"]),
                          data={"To": to, "From": os.environ["TWILIO_FROM"], "Body": body[:600]})
        if r.status_code >= 300:
            log.error("SMS to %s failed: %s", to, r.text[:200])
        return r.status_code < 300
    except Exception as e:
        log.error("SMS to %s failed: %s", to, e); return False

def deliver(s, subject, body):
    if s.email: send_email(s.email, subject, body)
    if s.phone: send_sms(s.phone, body)

def notify_subscribers(st, pred):
    """Alert on a new/changed risk (or once per 24 h while it persists); send an all-clear when it drops."""
    now = timezone.now()
    for s in st.subscribers.all():
        if ORDER[pred.risk_level] >= ORDER[s.min_risk]:
            if s.last_risk != pred.risk_level or not s.last_alert_at or now - s.last_alert_at > timedelta(hours=24):
                deliver(s, f"Flood alert: {st.name} ({pred.risk_level})", alert_text(st, pred))
                s.last_risk, s.last_alert_at = pred.risk_level, now; s.save()
        elif s.last_risk:
            deliver(s, f"All clear: {st.name}", f"All clear: flood risk at {st.name} has dropped to {pred.risk_level}.")
            s.last_risk = ""; s.save()

def alert_text(st, pred):
    return (f"{pred.risk_level} flood risk at {st.name}. Forecast discharge {pred.predicted_discharge:,.0f} m3/s by "
            f"{pred.forecast_time} (flood threshold {st.danger_level:,.0f} m3/s). Expected rain next {ml.HORIZON} days: "
            f"{pred.forecast_rain_mm:.0f} mm.")

def run_for_station(st):
    obs, rain = fetch_recent(st)
    for day, (rn, ds) in obs.items():
        Reading.objects.update_or_create(station=st, date=day, defaults={"rainfall": rn, "discharge": ds})
    recent = list(st.readings.order_by("-date")[:ml.WINDOW])[::-1]
    if len(recent) < ml.WINDOW:
        return None
    last = recent[-1].date
    fut = [rain.get((last + timedelta(days=i)).isoformat()) or 0 for i in range(1, ml.HORIZON + 1)]
    q, risk, p = ml.predict([r.rainfall for r in recent], [r.discharge for r in recent], st.danger_level, fut)
    pred = Prediction.objects.create(station=st, forecast_time=last + timedelta(days=ml.HORIZON), predicted_discharge=q,
                                     risk_level=risk, probability=p, model_version=ml.VERSION, forecast_rain_mm=sum(fut))
    if risk != "LOW":
        Alert.objects.create(prediction=pred, severity=risk, message=alert_text(st, pred))
    notify_subscribers(st, pred)
    return pred

@shared_task
def run_cycle():
    return [str(run_for_station(s)) for s in Station.objects.all()]
