from django.core.management.base import BaseCommand
from flood.tasks import send_email, send_sms

class Command(BaseCommand):
    help = "Send a test message to check your email/SMS credentials: send_test_alert --email a@b.com --phone +919876543210"
    def add_arguments(self, p):
        p.add_argument("--email"); p.add_argument("--phone")
    def handle(self, *a, **o):
        msg = "FloodWatch test alert: your notification setup works."
        if o["email"]: self.stdout.write(f"email sent: {send_email(o['email'], 'FloodWatch test', msg)}")
        if o["phone"]: self.stdout.write(f"sms sent: {send_sms(o['phone'], msg)}")
