from django.contrib import admin
from .models import *
for m in (Station, Reading, Prediction, Alert, Subscriber): admin.site.register(m)
