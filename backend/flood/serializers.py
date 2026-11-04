from rest_framework import serializers
from .models import *

class PredictionSerializer(serializers.ModelSerializer):
    class Meta: model = Prediction; fields = "__all__"

class ReadingSerializer(serializers.ModelSerializer):
    class Meta: model = Reading; exclude = ["station"]

class StationSerializer(serializers.ModelSerializer):
    latest = serializers.SerializerMethodField()
    class Meta: model = Station; fields = ["id", "name", "river", "lat", "lon", "danger_level", "latest"]
    def get_latest(self, o):
        p = o.predictions.first()
        return PredictionSerializer(p).data if p else None

class AlertSerializer(serializers.ModelSerializer):
    station = serializers.CharField(source="prediction.station.name")
    class Meta: model = Alert; fields = ["id", "station", "severity", "message", "sent_at"]

class SubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber; fields = "__all__"; read_only_fields = ["last_risk", "last_alert_at"]
    def validate_phone(self, v):
        if v and not (v.startswith("+") and v[1:].isdigit()):
            raise serializers.ValidationError("Use international format, e.g. +919876543210")
        return v
    def validate(self, d):
        if not d.get("email") and not d.get("phone"):
            raise serializers.ValidationError("Provide an email or a phone number.")
        return d
