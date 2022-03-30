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
    SMS = "sms", "SMS"
    # Implement email/WhatsApp later
    # WHATSAPP = "whatsapp", "WhatsApp"
    # EMAIL = 'email', 'e-mail'


class UserAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    alert_type = models.CharField(
        max_length=8, choices=AlertType.choices, default=AlertType.SMS
    )
    phone_number = models.ForeignKey(
        UserPhoneNumber, blank=True, on_delete=models.CASCADE
    )
    location = models.PolygonField()
    verified = models.BooleanField(default=False)

    # Keep existing phone number so we re-verify if it changes
    __original_phone_number = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_phone_number_id = self.phone_number_id

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        if self.phone_number_id != self.__original_phone_number_id:
            self.verified = False

        super().save(force_insert, force_update, *args, **kwargs)
        self.__original_phone_number_id = self.phone_number_id
