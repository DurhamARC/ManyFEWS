from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point, Polygon
from phonenumber_field.modelfields import PhoneNumberField


class UserPhoneNumber(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    phone_number = PhoneNumberField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "phone_number"], name="unique_user_phone_number"
            )
        ]


class AlertType(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    SMS = "sms", "SMS"
    # Implement email later
    # EMAIL = 'email', 'e-mail'


class UserAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    alert_type = models.CharField(
        max_length=8, choices=AlertType.choices, default=AlertType.WHATSAPP
    )
    phone_number = models.ForeignKey(
        UserPhoneNumber, blank=True, on_delete=models.CASCADE
    )
    location = models.PolygonField()

    def get_alert_type():
        # Get value from choices enum
        return AlertType[self.alert_type]
