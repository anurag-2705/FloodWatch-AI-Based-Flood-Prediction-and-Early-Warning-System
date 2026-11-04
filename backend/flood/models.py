from django.db import models

class Station(models.Model):
    name = models.CharField(max_length=100, unique=True)
    river = models.CharField(max_length=100)
    lat = models.FloatField()
    lon = models.FloatField()
    danger_level = models.FloatField(help_text="Flood threshold: 95th-percentile discharge, m3/s")
    def __str__(self): return self.name

class Reading(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="readings")
    date = models.DateField(db_index=True)
    rainfall = models.FloatField(help_text="mm/day")
    discharge = models.FloatField(help_text="m3/s")
    class Meta:
        unique_together = ("station", "date")
        ordering = ["date"]

class Prediction(models.Model):
    RISK = [("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High")]
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="predictions")
    created_at = models.DateTimeField(auto_now_add=True)
    forecast_time = models.DateField()
    predicted_discharge = models.FloatField()
    risk_level = models.CharField(max_length=6, choices=RISK)
    probability = models.FloatField(help_text="Probability of HIGH risk")
    model_version = models.CharField(max_length=30, default="v3-forecast-rain")
    forecast_rain_mm = models.FloatField(default=0)
    class Meta: ordering = ["-created_at"]

class Alert(models.Model):
    prediction = models.ForeignKey(Prediction, on_delete=models.CASCADE, related_name="alerts")
    severity = models.CharField(max_length=6)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-sent_at"]

class Subscriber(models.Model):
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="subscribers")
    min_risk = models.CharField(max_length=6, default="HIGH", choices=[("MEDIUM", "Medium"), ("HIGH", "High")])
    last_risk = models.CharField(max_length=6, blank=True, default="")
    last_alert_at = models.DateTimeField(null=True, blank=True)
