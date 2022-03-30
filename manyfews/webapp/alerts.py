import os

from django.conf import settings
from twilio.rest import Client


class TwilioAlerts:
    def __init__(self):
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        self.client = Client(account_sid, auth_token)
        self.verification_sid = settings.TWILIO_VERIFICATION_SID

    def send_verification_message(self, phone_number, channel="sms"):
        verification = self.client.verify.services(
            self.verification_sid
        ).verifications.create(to=phone_number, channel=channel)
        return verification.status != "canceled"

    def check_verification_code(self, phone_number, code):
        verification_check = self.client.verify.services(
            self.verification_sid
        ).verification_checks.create(to=phone_number, code=code)
        return verification_check.status

    def send_alert_sms(self, phone_number, message):
        self._send_alert_message(settings.TWILIO_PHONE_NUMBER, phone_number, message)

    def send_alert_whatsapp(self, phone_number, message):
        self._send_alert_message(
            f"whatsapp:{settings.TWILIO_PHONE_NUMBER}",
            f"whatsapp:{phone_number}",
            message,
        )

    def _send_alert_message(self, from_number, to_number, message):
        try:
            message = self.client.messages.create(
                body=message, from_=from_number, to=to_number
            )
        except Exception as e:
            print(f"Unable to send message to {to_number}: {e}")


# Calculate alerts from flood depths
